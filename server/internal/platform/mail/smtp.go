package mail

import (
	"context"
	"crypto/tls"
	"errors"
	"fmt"
	"net"
	"net/smtp"
	"strconv"
	"strings"
	"time"
)

// SMTPTimeout 是连接和读写的上限（设计 10.1）。服务商收下连接不说话，到点就放弃。
const SMTPTimeout = 20 * time.Second

// ErrNotConfigured 是还没填 SMTP。
var ErrNotConfigured = errors.New("后台尚未配置 SMTP，无法发信。请在「设置 → 全站设置」中填写 SMTP 服务器和发件地址。")

// SMTP 是发信要用的配置。Timeout 为零就用 SMTPTimeout。Allowlist 非空时，不在名单里的不发。
type SMTP struct {
	Host      string
	Port      int
	Username  string
	Password  string
	FromName  string
	FromAddr  string
	Security  string // ssl、starttls、plain
	Prefix    string
	Allowlist []string
	Timeout   time.Duration
}

// Deliver 把一封信发给一个人。名单挡下、或者没配，都不算发出去。
// 返回 skipped 表示这封不该发（名单或注销），err 为 nil。
func Deliver(ctx context.Context, cfg SMTP, letter Letter, to Person, siteURL string, now time.Time) (skipped bool, err error) {
	people := People([]Person{to})
	if len(people) == 0 {
		return true, nil
	}
	to = people[0]
	if !allowed(cfg.Allowlist, to.Address) {
		return true, nil
	}
	if cfg.Host == "" || cfg.FromAddr == "" {
		return false, ErrNotConfigured
	}
	from := cfg.FromAddr
	if cfg.FromName != "" {
		from = cfg.FromName + " <" + cfg.FromAddr + ">"
	}
	msg, err := Build(letter, to, from, siteURL, cfg.Prefix, now)
	if err != nil {
		return false, err
	}
	return false, send(ctx, cfg, cfg.FromAddr, to.Address, msg.Raw)
}

func allowed(list []string, address string) bool {
	if len(list) == 0 {
		return true
	}
	address = strings.ToLower(address)
	for _, item := range list {
		if strings.ToLower(strings.TrimSpace(item)) == address {
			return true
		}
	}
	return false
}

func send(ctx context.Context, cfg SMTP, from, to string, raw []byte) error {
	timeout := cfg.Timeout
	if timeout <= 0 {
		timeout = SMTPTimeout
	}
	if cfg.Port == 0 {
		cfg.Port = 587
	}
	addr := net.JoinHostPort(cfg.Host, strconv.Itoa(cfg.Port))
	dialer := net.Dialer{Timeout: timeout}
	var conn net.Conn
	var err error
	if strings.EqualFold(cfg.Security, "ssl") {
		conn, err = tls.DialWithDialer(&dialer, "tcp", addr, &tls.Config{ServerName: cfg.Host, MinVersion: tls.VersionTLS12})
	} else {
		conn, err = dialer.DialContext(ctx, "tcp", addr)
	}
	if err != nil {
		return err
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(timeout))

	client, err := smtp.NewClient(conn, cfg.Host)
	if err != nil {
		return err
	}
	defer client.Close()
	if strings.EqualFold(cfg.Security, "starttls") {
		if err := client.StartTLS(&tls.Config{ServerName: cfg.Host, MinVersion: tls.VersionTLS12}); err != nil {
			return err
		}
	}
	if cfg.Username != "" {
		if err := client.Auth(smtp.PlainAuth("", cfg.Username, cfg.Password, cfg.Host)); err != nil {
			return err
		}
	}
	if err := client.Mail(from); err != nil {
		return err
	}
	if err := client.Rcpt(to); err != nil {
		return err
	}
	w, err := client.Data()
	if err != nil {
		return err
	}
	if _, err := w.Write(raw); err != nil {
		_ = w.Close()
		return err
	}
	if err := w.Close(); err != nil {
		return err
	}
	return client.Quit()
}

// FormatFrom 是「名字 <地址>」。名字空着就只留地址。
func FormatFrom(name, addr string) string {
	if name == "" {
		return addr
	}
	return fmt.Sprintf("%s <%s>", name, addr)
}
