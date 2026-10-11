package content

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"html"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

type contentPreview struct {
	OwnerID int64
	HTML    string
	Expires time.Time
}
type contentPreviewCache struct {
	mu        sync.Mutex
	documents map[string]contentPreview
}
type MarkdownPreviewIn struct {
	BodyMD string `json:"body_md"`
}
type MarkdownPreviewOut struct {
	PreviewURL string `json:"preview_url"`
}

// SetPreviewResolver uses the exact resolver used by the JSON API registry.
func (m *Module) SetPreviewResolver(resolve api.ViewerResolver) { m.previewResolver = resolve }

func (m *Module) SetPreviewStylesheet(path string) {
	if strings.HasPrefix(path, "/") && !strings.HasPrefix(path, "//") && !strings.ContainsAny(path, "\\\r\n") {
		m.previewStylesheet = path
	}
}

func (m *Module) previewDocument(title, body string) string {
	stylesheet := ""
	if m.previewStylesheet != "" {
		stylesheet = `<link rel="stylesheet" href="` + html.EscapeString(m.previewStylesheet) + `">`
	}
	return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
		`<title>` + html.EscapeString(title) + ` · 草稿预览</title>` + stylesheet + `</head><body><main id="main" class="c-reading">` +
		`<article class="c-article"><header class="c-article__head"><h1 class="c-article__title">` + html.EscapeString(title) + `</h1></header><div class="c-prose">` + body + `</div></article></main></body></html>`
}

func (m *Module) markdownPreview(ctx *app.Ctx, in MarkdownPreviewIn) (MarkdownPreviewOut, error) {
	if len(in.BodyMD) > 1024*1024 {
		return MarkdownPreviewOut{}, api.InvalidFields(map[string][]string{"body_md": {"正文不超过1 MB"}})
	}
	rendered, _, err := markdown.Render(in.BodyMD, m.svc.siteURL, nil)
	if err != nil {
		return MarkdownPreviewOut{}, err
	}
	token := make([]byte, 32)
	if _, err := rand.Read(token); err != nil {
		return MarkdownPreviewOut{}, err
	}
	key := hex.EncodeToString(token)
	cache := &m.previews
	cache.mu.Lock()
	defer cache.mu.Unlock()
	if cache.documents == nil {
		cache.documents = map[string]contentPreview{}
	}
	now := ctx.Now()
	for key, entry := range cache.documents {
		if !entry.Expires.After(now) {
			delete(cache.documents, key)
		}
	}
	if len(cache.documents) >= 128 {
		return MarkdownPreviewOut{}, api.TooManyRequests(time.Minute)
	}
	cache.documents[key] = contentPreview{OwnerID: ctx.Viewer.ID, HTML: m.previewDocument("正文预览", rendered), Expires: now.Add(5 * time.Minute)}
	return MarkdownPreviewOut{PreviewURL: "/api/admin/previews/" + key}, nil
}

func (m *Module) previewViewer(w http.ResponseWriter, r *http.Request) *app.Viewer {
	if m.previewResolver == nil {
		http.Error(w, "预览暂时不可用", http.StatusServiceUnavailable)
		return nil
	}
	viewer := m.previewResolver(r)
	if viewer == nil || viewer.Disabled || viewer.ID <= 0 || !viewer.HasCap("admin.enter") {
		http.Error(w, "要先登录", http.StatusUnauthorized)
		return nil
	}
	return viewer
}

func privatePreviewHeaders(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store, private")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'self'; img-src 'self' data:; font-src 'self'; frame-src https://player.bilibili.com; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
}

func (m *Module) serveMarkdownPreview(w http.ResponseWriter, r *http.Request) {
	privatePreviewHeaders(w)
	viewer := m.previewViewer(w, r)
	if viewer == nil {
		return
	}
	key := r.PathValue("token")
	if len(key) != 64 {
		http.NotFound(w, r)
		return
	}
	if _, err := hex.DecodeString(key); err != nil {
		http.NotFound(w, r)
		return
	}
	cache := &m.previews
	cache.mu.Lock()
	entry, ok := cache.documents[key]
	if ok && !entry.Expires.After(time.Now()) {
		delete(cache.documents, key)
		ok = false
	}
	cache.mu.Unlock()
	if !ok || entry.OwnerID != viewer.ID {
		http.NotFound(w, r)
		return
	}
	_, _ = fmt.Fprint(w, entry.HTML)
}

func (m *Module) serveArticlePreview(w http.ResponseWriter, r *http.Request) {
	privatePreviewHeaders(w)
	viewer := m.previewViewer(w, r)
	if viewer == nil {
		return
	}
	id, ok := api.ParseID(r.PathValue("id"))
	if !ok {
		http.NotFound(w, r)
		return
	}
	ctx := &app.Ctx{Context: r.Context(), Viewer: viewer}
	article, err := m.authorizedArticle(ctx, int64(id))
	if err != nil || article == nil {
		http.NotFound(w, r)
		return
	}
	draft := articleDraft(article)
	if value := r.URL.Query().Get("revision"); value != "" {
		revision, err := strconv.ParseInt(value, 10, 64)
		if err != nil || revision <= 0 {
			http.NotFound(w, r)
			return
		}
		result, err := m.articleRevision(ctx, ArticleRevisionIn{ID: id, Revision: api.ID(revision)})
		if err != nil {
			http.NotFound(w, r)
			return
		}
		draft = result.Draft
	} else {
		latest, err := m.svc.store.GetLatestRevision(r.Context(), int64(id))
		if err != nil {
			http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
			return
		}
		if latest != nil {
			result, err := readArticleRevisionContent(latest.Content, draft)
			if err != nil {
				http.Error(w, "草稿内容损坏", http.StatusInternalServerError)
				return
			}
			draft = result
		}
	}
	document, err := m.renderArticlePreview(ctx, article, draft)
	if err != nil {
		http.Error(w, "预览暂时不可用", http.StatusInternalServerError)
		return
	}
	_, _ = fmt.Fprint(w, document)
}
