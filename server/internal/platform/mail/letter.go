// Package mail 是信纸和发信（12 号文档 5.11、设计 10.3）。
// 主题保持裸的，前缀在发出去时加一次。34 种信的正文在各领域，这里只做信纸。
package mail

import (
	"fmt"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"
)

const (
	Closing   = "祝好！"
	Signature = "SJTU-OW"
	NoReply   = "这封邮件由系统自动发送，请不要直接回复。"
	// DefaultPrefix 是没配前缀时用的（208 轮起）。
	DefaultPrefix = "[SJTU-OW]"
)

// Letter 是一封信要说的话。Action 最多一个。Items 是（文字，链接）。
type Letter struct {
	Subject     string      `json:"subject"`
	Lead        string      `json:"lead"`
	Paragraphs  []string    `json:"paragraphs"`
	Facts       [][2]string `json:"facts"`
	Items       [][2]string `json:"items"`
	ItemLink    string      `json:"item_link"`
	Code        string      `json:"code"`
	Action      []string    `json:"action"`
	Note        string      `json:"note"`
	Reason      string      `json:"reason"`
	Unsubscribe string      `json:"unsubscribe"`
	Notice      string      `json:"notice"`
}

// Person 是一个收件人。Address 以 .invalid 结尾的是注销账号，不发。
type Person struct {
	Address string `json:"address"`
	Name    string `json:"name"`
}

// Greeting 是「昵称，你好：」；不知道是谁就「你好：」。
func Greeting(name string) string {
	if name == "" {
		return "你好："
	}
	return name + "，你好："
}

// Dated 是落款日期，按上海时区的日历日（和现行站 localdate 一样）。
func Dated(now time.Time) string {
	t := now.In(shanghai)
	return fmt.Sprintf("%d 年 %d 月 %d 日", t.Year(), int(t.Month()), t.Day())
}

var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

// Text 是纯文本。空的段落不占行。
func (l Letter) Text(name, siteURL string, now time.Time) string {
	var parts []string
	add := func(s string) {
		if s != "" {
			parts = append(parts, s)
		}
	}
	add(Greeting(name))
	add(l.Notice)
	add(l.Lead)
	if len(l.Facts) > 0 {
		lines := make([]string, len(l.Facts))
		for i, f := range l.Facts {
			lines[i] = f[0] + "：" + f[1]
		}
		add(strings.Join(lines, "\n"))
	}
	if l.Code != "" {
		add("验证码：" + l.Code)
	}
	if len(l.Items) > 0 {
		var lines []string
		for _, item := range l.Items {
			line := "- " + item[0]
			if item[1] != "" {
				line += "\n  " + item[1]
			}
			lines = append(lines, line)
		}
		add(strings.Join(lines, "\n"))
	}
	for _, p := range l.Paragraphs {
		add(p)
	}
	if label, href := l.action(); href != "" || label != "" {
		add(label + "：" + href)
	}
	add(l.Note)
	add(Closing)
	add(Signature + "\n" + Dated(now))
	unsub := ""
	if l.Unsubscribe != "" {
		unsub = "\n退订活动通知：" + l.Unsubscribe
	}
	add("——\n" + l.Reason + NoReply + unsub + "\n" + SiteRoot(siteURL))
	return strings.Join(parts, "\n\n")
}

func (l Letter) action() (label, href string) {
	if len(l.Action) >= 2 {
		return l.Action[0], l.Action[1]
	}
	if len(l.Action) == 1 {
		return l.Action[0], ""
	}
	return "", ""
}

func (l Letter) itemLink() string {
	if l.ItemLink == "" {
		return "打开"
	}
	return l.ItemLink
}

// SiteRoot 是站点根，结尾有斜杠。
func SiteRoot(siteURL string) string {
	return strings.TrimRight(strings.TrimSpace(siteURL), "/") + "/"
}

// SiteHost 是页脚上显示的主机名。
func SiteHost(siteURL string) string {
	u, err := url.Parse(strings.TrimSpace(siteURL))
	if err != nil || u.Host == "" {
		return strings.TrimRight(strings.TrimSpace(siteURL), "/")
	}
	return u.Host
}

// PrefixSubject 加上主题前缀。已经以这个前缀开头的不加第二次。
func PrefixSubject(subject, prefix string) string {
	prefix = strings.TrimSpace(prefix)
	if prefix == "" {
		return subject
	}
	if strings.HasPrefix(subject, prefix) {
		return subject
	}
	return strings.TrimSpace(prefix + " " + subject)
}

// People 按地址去重、排序，丢掉空的和注销的。同地址留先出现的名字。
func People(in []Person) []Person {
	found := map[string]string{}
	var order []string
	for _, p := range in {
		addr := strings.TrimSpace(p.Address)
		if addr == "" || strings.HasSuffix(addr, ".invalid") {
			continue
		}
		if _, ok := found[addr]; ok {
			continue
		}
		found[addr] = p.Name
		order = append(order, addr)
	}
	sort.Strings(order)
	out := make([]Person, len(order))
	for i, addr := range order {
		out[i] = Person{Address: addr, Name: found[addr]}
	}
	return out
}

var escapedText = regexp.MustCompile(`(?:%[89A-Fa-f][0-9A-Fa-f])+`)

// ReadableURL 把地址里成片的非 ASCII 百分号还原成字。%2F 这种 ASCII 不动。
func ReadableURL(raw string) string {
	return escapedText.ReplaceAllStringFunc(raw, func(s string) string {
		dec, err := url.PathUnescape(s)
		if err != nil || dec == s {
			return s
		}
		// PathUnescape 对不合法的 UTF-8 会原样留下 %XX。和 Python errors=strict 不同的
		// 那一种（坏字节）保持原样：解出来含替换符就当没解开。
		if strings.ContainsRune(dec, '\uFFFD') {
			return s
		}
		return dec
	})
}
