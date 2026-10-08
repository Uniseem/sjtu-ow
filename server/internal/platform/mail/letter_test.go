package mail

import (
	"bufio"
	"context"
	"net"
	"os"
	"strings"
	"testing"
	"time"
)

func TestTextReadsAsALetter(t *testing.T) {
	now := time.Date(2026, 10, 8, 12, 0, 0, 0, shanghai)
	letter := Letter{
		Subject:    "邮箱验证码",
		Lead:       "你的验证码是下面这一个。",
		Code:       "123456",
		Reason:     "你收到这封邮件，是因为有人用这个邮箱注册。",
		Paragraphs: []string{"十分钟内有效。"},
	}
	text := letter.Text("小明", "https://example.com", now)
	if !strings.HasPrefix(text, "小明，你好：\n") {
		t.Fatalf("称呼：%q", text)
	}
	if strings.Index(text, "你的验证码是下面这一个。") > strings.Index(text, "验证码：123456") {
		t.Fatal("结论应在验证码前面")
	}
	if strings.Index(text, "验证码：123456") > strings.Index(text, "十分钟内有效。") {
		t.Fatal("验证码应在段落前面")
	}
	if !strings.Contains(text, "\n祝好！\n") || !strings.Contains(text, "SJTU-OW\n2026 年 10 月 8 日") {
		t.Fatalf("落款：%s", text)
	}
	if strings.Index(text, "祝好！") > strings.Index(text, "——") {
		t.Fatal("祝好应在为什么收到之前")
	}
	if !strings.Contains(text, "你收到这封邮件，是因为有人用这个邮箱注册。这封邮件由系统自动发送，请不要直接回复。\nhttps://example.com/") {
		t.Fatalf("页脚：%s", text)
	}
	if letter.Text("", "https://example.com/", now)[:len("你好：")] != "你好：" {
		t.Fatal("不知道是谁应写「你好：」")
	}
}

func TestHTMLFrame(t *testing.T) {
	now := time.Date(2026, 10, 8, 4, 0, 0, 0, time.UTC) // 上海 12 点
	letter := Letter{
		Subject:     "报名已通过：秋季杯",
		Lead:        "你的报名通过了。",
		Notice:      "之前已经发过 1 次。",
		Facts:       [][2]string{{"赛事", "秋季杯"}},
		Items:       [][2]string{{"秩序册", "https://example.com/a"}},
		Paragraphs:  []string{"请准时到。"},
		Action:      []string{"查看报名", "https://example.com/news/网站正式发布/"},
		Note:        "改期会再通知。",
		Reason:      "你收到这封邮件，是因为你报了名。",
		Unsubscribe: "https://example.com/unsub",
	}
	html, err := letter.HTML("小明", "https://example.com", now)
	if err != nil {
		t.Fatal(err)
	}
	for _, needle := range []string{
		`<meta name="color-scheme" content="light">`,
		"data-letter-head", "data-letter-card", "data-letter-horizon",
		"data-letter-facts", "data-letter-button", "data-letter-notice",
		"data-letter-items", "data-letter-url",
		"cid:ow-mark", "cid:ow-horizon",
		"祝好！", "2026 年 10 月 8 日",
		"你收到这封邮件，是因为你报了名。",
		"按钮打不开的话",
		"网站正式发布",
		"退订活动通知",
	} {
		if !strings.Contains(html, needle) {
			t.Errorf("HTML 缺 %s", needle)
		}
	}
	if strings.Contains(html, "<script") || strings.Contains(html, "<link") || strings.Contains(html, " class=") {
		t.Fatal("信里不该有脚本、外链样式或 class")
	}
	if strings.Count(html, "这封邮件由系统自动发送") != 1 {
		t.Fatal("自动发送应只出现一次")
	}
}

func TestReadableURLKeepsASCIIEscapes(t *testing.T) {
	got := ReadableURL("https://example.com/news/%E7%BD%91%E7%AB%99%E6%AD%A3%E5%BC%8F%E5%8F%91%E5%B8%83/?q=%2F")
	if !strings.Contains(got, "网站正式发布") || !strings.Contains(got, "%2F") {
		t.Fatalf("得到 %s", got)
	}
}

func TestPrefixOnceAndArtBytes(t *testing.T) {
	if PrefixSubject("邮箱验证码", DefaultPrefix) != "[SJTU-OW] 邮箱验证码" {
		t.Fatal("应加前缀")
	}
	if PrefixSubject("[SJTU-OW] 已经有了", DefaultPrefix) != "[SJTU-OW] 已经有了" {
		t.Fatal("不应加第二次")
	}
	for _, name := range []string{"mark.png", "horizon.png"} {
		want, err := os.ReadFile("../../../../static/img/email/" + name)
		if err != nil {
			t.Fatal(err)
		}
		cid := "ow-mark"
		if name == "horizon.png" {
			cid = "ow-horizon"
		}
		got := Art()[cid]
		if string(got) != string(want) {
			t.Fatalf("%s 和仓库里的不一致（%d / %d）", name, len(got), len(want))
		}
	}
}

func TestBuildCarriesPicturesAndUnsubscribe(t *testing.T) {
	now := time.Date(2026, 10, 8, 1, 0, 0, 0, time.UTC)
	msg, err := Build(Letter{
		Subject: "验证码", Lead: "看下面。", Code: "1",
		Unsubscribe: "https://example.com/unsub",
		Reason:      "因为。",
	}, Person{Address: "a@example.com", Name: "小明"}, "SJTU-OW <noreply@example.com>", "https://example.com", DefaultPrefix, now)
	if err != nil {
		t.Fatal(err)
	}
	if msg.Subject != "[SJTU-OW] 验证码" {
		t.Fatalf("主题 %s", msg.Subject)
	}
	raw := string(msg.Raw)
	if !strings.Contains(raw, "List-Unsubscribe: <https://example.com/unsub>") {
		t.Fatal("缺退订头")
	}
	if !strings.Contains(raw, "List-Unsubscribe-Post: List-Unsubscribe=One-Click") {
		t.Fatal("缺一键退订")
	}
	// 标准库把 Content-ID 规范成 Content-Id，两种都算挂上了。
	if (!strings.Contains(raw, "Content-Id: <ow-mark>") && !strings.Contains(raw, "Content-ID: <ow-mark>")) ||
		(!strings.Contains(raw, "Content-Id: <ow-horizon>") && !strings.Contains(raw, "Content-ID: <ow-horizon>")) {
		t.Fatal("头图没挂上")
	}
}

func TestDeliverSkipsAllowlistAndUnconfigured(t *testing.T) {
	now := time.Date(2026, 10, 8, 1, 0, 0, 0, time.UTC)
	letter := Letter{Subject: "验证码", Lead: "看下面。", Reason: "因为。"}
	skipped, err := Deliver(context.Background(), SMTP{
		Host: "127.0.0.1", Port: 1, FromAddr: "noreply@example.com",
		Allowlist: []string{"other@example.com"},
	}, letter, Person{Address: "a@example.com"}, "https://example.com", now)
	if err != nil || !skipped {
		t.Fatalf("名单外应跳过：skipped=%v err=%v", skipped, err)
	}
	_, err = Deliver(context.Background(), SMTP{}, letter, Person{Address: "a@example.com"}, "https://example.com", now)
	if err == nil || !strings.Contains(err.Error(), "尚未配置 SMTP") {
		t.Fatalf("没配应报错：%v", err)
	}
}

func TestDeliverTalksSMTPAndTimesOut(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer ln.Close()
	got := make(chan string, 1)
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		got <- speak(conn)
	}()
	_, port, _ := net.SplitHostPort(ln.Addr().String())
	var p int
	fmtSscan(port, &p)
	now := time.Date(2026, 10, 8, 1, 0, 0, 0, time.UTC)
	skipped, err := Deliver(context.Background(), SMTP{
		Host: "127.0.0.1", Port: p, FromAddr: "noreply@example.com", FromName: "SJTU-OW",
		Security: "plain", Timeout: 2 * time.Second,
	}, Letter{Subject: "验证码", Lead: "看下面。", Reason: "因为。"}, Person{Address: "a@example.com", Name: "小明"}, "https://example.com", now)
	if err != nil || skipped {
		t.Fatalf("应发出去：skipped=%v err=%v", skipped, err)
	}
	body := <-got
	if !strings.Contains(body, "Subject:") || !strings.Contains(body, "a@example.com") {
		t.Fatalf("服务器没收到信：%s", body[:min(200, len(body))])
	}

	blackhole, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer blackhole.Close()
	go func() {
		conn, err := blackhole.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		time.Sleep(time.Second)
	}()
	_, port, _ = net.SplitHostPort(blackhole.Addr().String())
	fmtSscan(port, &p)
	_, err = Deliver(context.Background(), SMTP{
		Host: "127.0.0.1", Port: p, FromAddr: "noreply@example.com",
		Security: "plain", Timeout: 200 * time.Millisecond,
	}, Letter{Subject: "验证码", Lead: "看下面。", Reason: "因为。"}, Person{Address: "a@example.com"}, "https://example.com", now)
	if err == nil {
		t.Fatal("对方不说话应在超时内放弃")
	}
}

func speak(conn net.Conn) string {
	r := bufio.NewReader(conn)
	w := bufio.NewWriter(conn)
	_, _ = w.WriteString("220 localhost\r\n")
	_ = w.Flush()
	var data strings.Builder
	reading := false
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			return data.String()
		}
		if reading {
			if line == ".\r\n" {
				reading = false
				_, _ = w.WriteString("250 queued\r\n")
				_ = w.Flush()
				continue
			}
			data.WriteString(line)
			continue
		}
		cmd := strings.ToUpper(strings.TrimSpace(line))
		switch {
		case strings.HasPrefix(cmd, "DATA"):
			_, _ = w.WriteString("354 go\r\n")
			reading = true
		case strings.HasPrefix(cmd, "QUIT"):
			_, _ = w.WriteString("221 bye\r\n")
			_ = w.Flush()
			return data.String()
		default:
			_, _ = w.WriteString("250 ok\r\n")
		}
		_ = w.Flush()
	}
}

func fmtSscan(s string, p *int) {
	n := 0
	for _, r := range s {
		n = n*10 + int(r-'0')
	}
	*p = n
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
