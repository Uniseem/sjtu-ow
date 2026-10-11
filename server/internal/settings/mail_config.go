package settings

import (
	"context"
	"fmt"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/crypto"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// MailConfig is read for each delivery so a saved SMTP change works without
// restarting the worker. The environment fallback supports existing test and
// initial bootstrap configurations only while both database fields are blank.
func (s *Service) MailConfig(ctx context.Context, fallback mail.SMTP) (mail.SMTP, error) {
	var config mail.SMTP
	var encrypted string
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT smtp_host,smtp_port,smtp_security,smtp_username,smtp_password,from_address,from_name,email_subject_prefix FROM site_settings WHERE id=1`).Scan(&config.Host, &config.Port, &config.Security, &config.Username, &encrypted, &config.FromAddr, &config.FromName, &config.Prefix)
	if err != nil {
		return mail.SMTP{}, err
	}
	if config.Host == "" && config.FromAddr == "" {
		return fallback, nil
	}
	if encrypted != "" {
		config.Password, err = crypto.Decrypt(s.fieldKey, encrypted)
		if err != nil {
			return mail.SMTP{}, fmt.Errorf("无法解密已保存的 SMTP 密码，请重新保存密钥。")
		}
	}
	if strings.EqualFold(config.Security, "tls") {
		config.Security = "starttls"
	}
	if config.Security == "none" {
		config.Security = "plain"
	}
	config.Allowlist = fallback.Allowlist
	config.Timeout = fallback.Timeout
	return config, nil
}
