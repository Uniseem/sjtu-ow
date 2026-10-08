package mail

import (
	_ "embed"
	"html/template"
	"strings"
	"time"
)

//go:embed letter.tmpl
var letterTmplSrc string

//go:embed art/mark.png
var markPNG []byte

//go:embed art/horizon.png
var horizonPNG []byte

// Art 是信头的两张图，键是 cid 名。
func Art() map[string][]byte {
	return map[string][]byte{
		"ow-mark":    append([]byte(nil), markPNG...),
		"ow-horizon": append([]byte(nil), horizonPNG...),
	}
}

var letterTmpl = template.Must(template.New("letter").Parse(letterTmplSrc))

type htmlData struct {
	Subject        string
	Lead           string
	Greeting       string
	Notice         string
	Facts          [][2]string
	Code           string
	Items          [][2]string
	ItemLink       string
	Paragraphs     []string
	HasAction      bool
	ActionLabel    string
	ActionURL      string
	ActionReadable string
	Note           string
	Reason         string
	Unsubscribe    string
	Date           string
	SiteURL        string
	SiteHost       string
	MarkCID        template.URL
	HorizonCID     template.URL
}

// HTML 是同一封信的 HTML。图片用 cid:，不引用外站。
func (l Letter) HTML(name, siteURL string, now time.Time) (string, error) {
	label, href := l.action()
	data := htmlData{
		Subject:        l.Subject,
		Lead:           l.Lead,
		Greeting:       Greeting(name),
		Notice:         l.Notice,
		Facts:          l.Facts,
		Code:           l.Code,
		Items:          l.Items,
		ItemLink:       l.itemLink(),
		Paragraphs:     l.Paragraphs,
		HasAction:      label != "" || href != "",
		ActionLabel:    label,
		ActionURL:      href,
		ActionReadable: ReadableURL(href),
		Note:           l.Note,
		Reason:         l.Reason,
		Unsubscribe:    l.Unsubscribe,
		Date:           Dated(now),
		SiteURL:        SiteRoot(siteURL),
		SiteHost:       SiteHost(siteURL),
		MarkCID:        "cid:ow-mark",
		HorizonCID:     "cid:ow-horizon",
	}
	var b strings.Builder
	if err := letterTmpl.Execute(&b, data); err != nil {
		return "", err
	}
	return b.String(), nil
}
