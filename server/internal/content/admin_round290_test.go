package content

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func round290Module(t *testing.T) (*Module, *db.DB, *app.Ctx, *app.Ctx) {
	t.Helper()
	database := newTestDB(t)
	insertTestUser(t, database, 1, "first@example.invalid", "First")
	insertTestUser(t, database, 2, "second@example.invalid", "Second")
	service := NewService(NewStore(database), "https://example.invalid")
	first := newTestCtx(context.Background(), 1, false, "admin.enter", CapArticlesPublishOwn)
	second := newTestCtx(context.Background(), 2, false, "admin.enter", CapArticlesPublishOwn)
	return NewModule(service), database, first, second
}

func round290ErrorStatus(t *testing.T, err error, want int) *api.Error {
	t.Helper()
	var apiErr *api.Error
	if !errors.As(err, &apiErr) || apiErr.Status != want {
		t.Fatalf("error=%v, want status %d", err, want)
	}
	return apiErr
}

func round290Create(t *testing.T, m *Module, ctx *app.Ctx, title, body string) *CreateDraftResult {
	t.Helper()
	result, err := m.svc.CreateDraft(ctx, CreateDraftInput{Title: title, BodyMD: body})
	if err != nil {
		t.Fatal(err)
	}
	return result
}

func TestRound290AuthorCannotReadOtherDraftThroughListDetailOrPreview(t *testing.T) {
	m, _, first, second := round290Module(t)
	own := round290Create(t, m, first, "first private title", "first secret body")
	other := round290Create(t, m, second, "second private title", "second secret body")
	listed, err := m.adminListArticles(first, AdminListArticlesIn{Page: 1, PageSize: 25})
	if err != nil {
		t.Fatal(err)
	}
	if listed.Total != 1 || len(listed.Items) != 1 || listed.Items[0].ID != own.ID {
		t.Fatalf("author list exposed another draft: %+v", listed)
	}
	_, err = m.adminGetArticleDetail(first, AdminArticleDetailIn{ID: api.ID(other.ID)})
	round290ErrorStatus(t, err, http.StatusNotFound)
	queried, err := m.adminListArticles(first, AdminListArticlesIn{Q: "second private"})
	if err != nil {
		t.Fatal(err)
	}
	if queried.Total != 0 || len(queried.Items) != 0 {
		t.Fatalf("filtered draft leak: %+v", queried)
	}

	m.SetPreviewResolver(func(r *http.Request) *app.Viewer { return first.Viewer })
	request := httptest.NewRequest(http.MethodGet, fmt.Sprintf("/api/admin/articles/%d/preview", other.ID), nil)
	request.SetPathValue("id", fmt.Sprint(other.ID))
	recorder := httptest.NewRecorder()
	m.serveArticlePreview(recorder, request)
	if recorder.Code != http.StatusNotFound || strings.Contains(recorder.Body.String(), "second secret body") {
		t.Fatalf("preview leaked: %d %s", recorder.Code, recorder.Body.String())
	}
	first.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	listed, err = m.adminListArticles(first, AdminListArticlesIn{})
	if err != nil || listed.Total != 2 {
		t.Fatalf("editor did not see both: %+v %v", listed, err)
	}
}

func TestRound290ContributorGuideAndClosedCategoryGate(t *testing.T) {
	m, _, plain, _ := round290Module(t)
	open := &Category{Name: "Open", Slug: "open", AllowSubmission: true}
	closed := &Category{Name: "Closed", Slug: "closed", AllowSubmission: false}
	if err := m.svc.store.CreateCategory(plain.Context, open); err != nil {
		t.Fatal(err)
	}
	if err := m.svc.store.CreateCategory(plain.Context, closed); err != nil {
		t.Fatal(err)
	}
	projection, err := m.newArticleEditor(plain, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	// publish_own is also granted to ordinary derived contributors.
	if !projection.Guide || projection.Capabilities.EditSchedule || len(projection.Categories) != 1 || projection.Categories[0].ID != open.ID {
		t.Fatalf("ordinary contributor misclassified: %+v", projection)
	}
	_, err = m.svc.CreateDraft(plain, CreateDraftInput{Title: "Blocked", CategoryID: &closed.ID})
	apiErr := round290ErrorStatus(t, err, http.StatusUnprocessableEntity)
	if len(apiErr.Fields["category_id"]) == 0 {
		t.Fatalf("missing category error: %+v", apiErr)
	}

	plain.Viewer.Roles = map[string]struct{}{"certified_author": {}}
	projection, err = m.newArticleEditor(plain, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	if projection.Guide || !projection.Capabilities.EditSchedule || len(projection.Categories) != 2 {
		t.Fatalf("certified author options wrong: %+v", projection)
	}
	if _, err := m.svc.CreateDraft(plain, CreateDraftInput{Title: "Allowed", CategoryID: &closed.ID}); err != nil {
		t.Fatal(err)
	}
}

func TestRound290ImportedRevisionAliasesSurviveUnrelatedSaveAndStaleWrite(t *testing.T) {
	m, database, first, _ := round290Module(t)
	category := &Category{Name: "Imported", Slug: "imported", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(first.Context, category); err != nil {
		t.Fatal(err)
	}
	created := round290Create(t, m, first, "Live fallback title", "LIVE FALLBACK BODY")
	raw := fmt.Sprintf(`{"title":"Imported draft","body":"KEEP IMPORTED BODY","category":%d,"author":1,"comments_enabled":true,"summary":"Keep summary"}`, category.ID)
	err := database.WriteTx(first.Context, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, "UPDATE page_revisions SET content=? WHERE page_id=?", raw, created.ID)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	detail, err := m.adminGetArticleDetail(first, AdminArticleDetailIn{ID: api.ID(created.ID)})
	if err != nil {
		t.Fatal(err)
	}
	if detail.Version != created.Version || detail.Revision == nil || detail.Revision.BodyMD != "KEEP IMPORTED BODY" {
		t.Fatalf("imported draft not decoded: %+v", detail)
	}
	saved, err := m.svc.SaveDraft(first, created.ID, SaveDraftInput{BaseVersion: detail.Version, Changes: map[string]any{"title": "Edited title"}})
	if err != nil {
		t.Fatal(err)
	}
	latest, err := m.adminGetArticleDetail(first, AdminArticleDetailIn{ID: api.ID(created.ID)})
	if err != nil {
		t.Fatal(err)
	}
	if latest.Revision == nil || latest.Revision.BodyMD != "KEEP IMPORTED BODY" || latest.Revision.Summary != "Keep summary" || latest.Revision.CategoryID == nil || *latest.Revision.CategoryID != category.ID {
		t.Fatalf("unrelated save cleared imported fields: %+v", latest.Revision)
	}
	_, err = m.svc.SaveDraft(first, created.ID, SaveDraftInput{BaseVersion: detail.Version, Changes: map[string]any{"body_md": "STALE OVERWRITE"}})
	stale := round290ErrorStatus(t, err, http.StatusConflict)
	if stale.Current == nil {
		t.Fatal("conflict omitted safe current editor projection")
	}
	record, err := json.Marshal(stale.Current)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(record), "KEEP IMPORTED BODY") || strings.Contains(string(record), "password_hash") {
		t.Fatalf("unsafe or incorrect current: %s", record)
	}
	after, err := m.adminGetArticleDetail(first, AdminArticleDetailIn{ID: api.ID(created.ID)})
	if err != nil || after.Version != saved.Version || after.Revision.BodyMD != "KEEP IMPORTED BODY" {
		t.Fatalf("stale write changed state: %+v %v", after, err)
	}
}

func TestRound290PlainDraftDoesNotChangePublishedPageUntilPublish(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapSitePagesManage] = struct{}{}
	now := time.Now().UTC().Format(time.RFC3339Nano)
	err := database.WriteTx(editor.Context, func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, "INSERT INTO pages(id,kind,slug,title,live,version,created_at,updated_at) VALUES(1000,'site_page','privacy','Published title',1,1,?,?)", now, now); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, "INSERT INTO site_pages(page_id,body_md,body_html,body_plain) VALUES(1000,'PUBLISHED BODY','<p>PUBLISHED BODY</p>','PUBLISHED BODY')")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	saved, err := m.patchPlainPage(editor, PlainPagePatchIn{ID: 1000, BaseVersion: 1, Changes: map[string]any{"title": "Draft title", "body_md": "PRIVATE DRAFT BODY"}})
	if err != nil {
		t.Fatal(err)
	}
	public := &app.Ctx{Context: context.Background()}
	page, err := m.getSitePage(public, SitePageIn{Slug: "privacy"})
	if err != nil || page.Title != "Published title" || strings.Contains(page.BodyHTML, "PRIVATE DRAFT") {
		t.Fatalf("draft appeared publicly: %+v %v", page, err)
	}
	_, err = m.publishPlainPage(editor, PlainPagePublishIn{ID: 1000, BaseVersion: 1})
	round290ErrorStatus(t, err, http.StatusConflict)
	page, err = m.getSitePage(public, SitePageIn{Slug: "privacy"})
	if err != nil || strings.Contains(page.BodyHTML, "PRIVATE DRAFT") {
		t.Fatal("stale publish changed live content")
	}
	result, err := m.publishPlainPage(editor, PlainPagePublishIn{ID: 1000, BaseVersion: saved.Version})
	if err != nil || result.Version <= saved.Version {
		t.Fatalf("publish: %+v %v", result, err)
	}
	page, err = m.getSitePage(public, SitePageIn{Slug: "privacy"})
	if err != nil || page.Title != "Draft title" || !strings.Contains(page.BodyHTML, "PRIVATE DRAFT BODY") {
		t.Fatalf("published value missing: %+v %v", page, err)
	}
}

func TestRound290MarkdownPreviewTokenIsOwnedExpiringAndSanitized(t *testing.T) {
	m, _, first, second := round290Module(t)
	result, err := m.markdownPreview(first, MarkdownPreviewIn{BodyMD: "# Heading\n\n<script>alert(1)</script>\n\n[unsafe](javascript:alert(2))"})
	if err != nil {
		t.Fatal(err)
	}
	token := strings.TrimPrefix(result.PreviewURL, "/api/admin/previews/")
	if len(token) != 64 {
		t.Fatalf("unexpected token: %s", result.PreviewURL)
	}
	viewer := first.Viewer
	m.SetPreviewResolver(func(r *http.Request) *app.Viewer { return viewer })
	get := func(key string) *httptest.ResponseRecorder {
		request := httptest.NewRequest(http.MethodGet, "/api/admin/previews/"+key, nil)
		request.SetPathValue("token", key)
		recorder := httptest.NewRecorder()
		m.serveMarkdownPreview(recorder, request)
		return recorder
	}
	recorder := get(token)
	if recorder.Code != http.StatusOK {
		t.Fatalf("owner preview: %d %s", recorder.Code, recorder.Body.String())
	}
	if strings.Contains(recorder.Body.String(), "<script") || strings.Contains(recorder.Body.String(), `href="javascript:`) {
		t.Fatalf("preview contains executable markup: %s", recorder.Body.String())
	}
	if !strings.Contains(recorder.Header().Get("Cache-Control"), "no-store") || strings.Contains(recorder.Header().Get("Content-Security-Policy"), "unsafe-inline") {
		t.Fatal("reader preview policy relaxed")
	}
	viewer = second.Viewer
	if recorder := get(token); recorder.Code != http.StatusNotFound {
		t.Fatalf("other owner accessed token: %d", recorder.Code)
	}
	viewer = nil
	if recorder := get(token); recorder.Code == http.StatusOK {
		t.Fatal("anonymous preview accepted")
	}
	viewer = first.Viewer
	m.previews.mu.Lock()
	entry := m.previews.documents[token]
	entry.Expires = time.Now().Add(-time.Second)
	m.previews.documents[token] = entry
	m.previews.mu.Unlock()
	if recorder := get(token); recorder.Code != http.StatusNotFound {
		t.Fatalf("expired token accepted: %d", recorder.Code)
	}
	if recorder := get("short"); recorder.Code != http.StatusNotFound {
		t.Fatalf("short token accepted: %d", recorder.Code)
	}
}
