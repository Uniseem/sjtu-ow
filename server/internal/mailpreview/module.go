package mailpreview

import (
	"encoding/base64"
	"fmt"
	"net/http"
	"sort"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

type Module struct {
	resolve api.ViewerResolver
	samples []Sample
	byKey   map[string]Sample
}

func NewModule(resolve api.ViewerResolver) *Module {
	samples := Catalogue()
	byKey := make(map[string]Sample, len(samples))
	for _, sample := range samples {
		byKey[sample.Key] = sample
	}
	return &Module{resolve: resolve, samples: samples, byKey: byKey}
}

type ListIn struct {
	Group string `query:"group"`
	Q     string `query:"q"`
}
type SampleIn struct {
	Key string `path:"key"`
}

type SampleOut struct {
	Key              string `json:"key"`
	Group            string `json:"group"`
	Title            string `json:"title"`
	To               string `json:"to"`
	Subject          string `json:"subject"`
	DeliveredSubject string `json:"delivered_subject"`
	Text             string `json:"text"`
	PreviewURL       string `json:"preview_url"`
	TextURL          string `json:"text_url"`
	Source           string `json:"source"`
	Fictional        bool   `json:"fictional"`
	Date             string `json:"date"`
}

type SampleGroup struct {
	Name  string `json:"name"`
	Count int    `json:"count"`
}
type ListOut struct {
	Items   []SampleOut   `json:"items"`
	Groups  []SampleGroup `json:"groups"`
	Total   int           `json:"total"`
	RootURL string        `json:"root_url"`
	Prefix  string        `json:"prefix"`
}

func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/mail-samples", api.Cap("admin.enter"), m.list)
	api.Get(r, "/api/admin/mail-samples/{key}", api.Cap("admin.enter"), m.detail)
	api.Raw(r, http.MethodGet, "/api/admin/mail-samples/{key}/preview", nil, m.preview)
	api.Raw(r, http.MethodGet, "/api/admin/mail-samples/{key}/text", nil, m.text)
}

func describe(sample Sample) SampleOut {
	return SampleOut{
		Key: sample.Key, Group: sample.Group, Title: sample.Title, To: sample.To,
		Subject: plainSubject(sample.Letter), DeliveredSubject: mail.PrefixSubject(sample.Letter.Subject, mail.DefaultPrefix),
		Text:       sample.Letter.Text(sample.Name, sampleRoot, specimenDate),
		PreviewURL: "/api/admin/mail-samples/" + sample.Key + "/preview",
		TextURL:    "/api/admin/mail-samples/" + sample.Key + "/text",
		Source:     sample.Source, Fictional: true, Date: mail.Dated(specimenDate),
	}
}

func (m *Module) list(ctx *app.Ctx, in ListIn) (ListOut, error) {
	out := ListOut{Items: []SampleOut{}, Groups: []SampleGroup{}, Total: len(m.samples), RootURL: sampleRoot, Prefix: mail.DefaultPrefix}
	counts := map[string]int{}
	order := []string{}
	for _, sample := range m.samples {
		if counts[sample.Group] == 0 {
			order = append(order, sample.Group)
		}
		counts[sample.Group]++
	}
	for _, group := range order {
		out.Groups = append(out.Groups, SampleGroup{Name: group, Count: counts[group]})
	}
	query := strings.ToLower(strings.TrimSpace(in.Q))
	if len([]rune(query)) > 50 {
		return out, api.InvalidFields(map[string][]string{"q": {"搜索不超过50字"}})
	}
	for _, sample := range m.samples {
		if in.Group != "" && sample.Group != in.Group {
			continue
		}
		if query != "" && !strings.Contains(strings.ToLower(sample.Title+" "+sample.Letter.Subject+" "+sample.Key), query) {
			continue
		}
		out.Items = append(out.Items, describe(sample))
	}
	return out, nil
}

func (m *Module) detail(ctx *app.Ctx, in SampleIn) (SampleOut, error) {
	sample, found := m.byKey[in.Key]
	if !found {
		return SampleOut{}, api.NotFound("邮件样张不存在")
	}
	return describe(sample), nil
}

func (m *Module) authorize(w http.ResponseWriter, r *http.Request) bool {
	if m.resolve == nil {
		http.Error(w, "邮件样张暂时不可用", http.StatusServiceUnavailable)
		return false
	}
	viewer := m.resolve(r)
	if viewer == nil || viewer.Disabled || viewer.ID <= 0 || !viewer.HasCap("admin.enter") {
		// Keep the private styleguide's hidden-document behavior.
		http.NotFound(w, r)
		return false
	}
	return true
}

func previewHeaders(w http.ResponseWriter, contentType string) {
	w.Header().Set("Content-Type", contentType)
	w.Header().Set("Cache-Control", "no-store, private")
	w.Header().Set("Pragma", "no-cache")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("X-Frame-Options", "SAMEORIGIN")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; form-action 'none'; sandbox")
}

// BrowserHTML replaces only the production letter's two embedded CID pictures.
// The letter frame remains mail.Letter.HTML, including its email inline CSS.
func BrowserHTML(letter mail.Letter, name string) (string, error) {
	body, err := letter.HTML(name, sampleRoot, specimenDate)
	if err != nil {
		return "", err
	}
	art := mail.Art()
	keys := make([]string, 0, len(art))
	for key := range art {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		data := "data:image/png;base64," + base64.StdEncoding.EncodeToString(art[key])
		body = strings.ReplaceAll(body, "cid:"+key, data)
	}
	return body, nil
}

func (m *Module) preview(w http.ResponseWriter, r *http.Request) {
	previewHeaders(w, "text/html; charset=utf-8")
	if !m.authorize(w, r) {
		return
	}
	sample, found := m.byKey[r.PathValue("key")]
	if !found {
		http.NotFound(w, r)
		return
	}
	body, err := BrowserHTML(sample.Letter, sample.Name)
	if err != nil {
		http.Error(w, "邮件样张暂时无法渲染", http.StatusInternalServerError)
		return
	}
	_, _ = fmt.Fprint(w, body)
}

func (m *Module) text(w http.ResponseWriter, r *http.Request) {
	previewHeaders(w, "text/plain; charset=utf-8")
	if !m.authorize(w, r) {
		return
	}
	sample, found := m.byKey[r.PathValue("key")]
	if !found {
		http.NotFound(w, r)
		return
	}
	_, _ = fmt.Fprint(w, sample.Letter.Text(sample.Name, sampleRoot, specimenDate))
}
