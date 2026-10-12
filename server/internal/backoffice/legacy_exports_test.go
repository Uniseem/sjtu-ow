package backoffice

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func TestLegacyRegistrationDownloadPreservesFilterAndPrivateCSV(t *testing.T) {
	e := managementFixture(t)
	e.event(1, "published")
	e.event(2, "published")
	e.registration(10, 1, "pending")
	e.registration(11, 2, "approved")
	e.exec(`INSERT INTO contacts(user_id,type,value,created_at,updated_at) VALUES(2,'qq','private-contact',?,?)`, stamp(e.ctx.Now()), stamp(e.ctx.Now()))
	module := NewModule(e.svc)
	registry := &api.Registry{}
	module.SetViewerResolver(func(*http.Request) *app.Viewer { return e.ctx.Viewer })
	module.Routes(registry)
	handler := registry.Handler(nil)
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, httptest.NewRequest("GET", "/admin/registrations/export.csv?status=pending&tournament=1", nil))
	if response.Code != 200 || !strings.HasPrefix(response.Header().Get("Content-Type"), "text/csv") || !strings.Contains(response.Header().Get("Content-Disposition"), "attachment; filename=") || !strings.Contains(response.Body.String(), "private-contact") || strings.Contains(response.Body.String(), "已通过") {
		t.Fatalf("old filter/download failed: %d %s %s", response.Code, response.Header(), response.Body.String())
	}
	if e.count(`SELECT COUNT(*) FROM audit_log WHERE action='registration.export' AND object_id=1`) != 1 {
		t.Fatal("legacy private export lost audit")
	}
	module.SetViewerResolver(func(*http.Request) *app.Viewer {
		return &app.Viewer{ID: 2, Caps: map[app.Cap]struct{}{accounts.CapTournamentsManage: {}}}
	})
	restricted := httptest.NewRecorder()
	handler.ServeHTTP(restricted, httptest.NewRequest("GET", "/admin/registrations/export.csv?tournament=1", nil))
	if restricted.Code != 200 || strings.Contains(restricted.Body.String(), "private-contact") || strings.Contains(restricted.Body.String(), "联系方式") {
		t.Fatal("legacy export leaked contacts without capability")
	}
}

func TestLegacyRegistrationDownloadGatesBeforeLookingAtRoster(t *testing.T) {
	module := NewModule(NewService(nil, &api.Registry{}))
	registry := &api.Registry{}
	module.Routes(registry)
	handler := registry.Handler(nil)
	for _, viewer := range []*app.Viewer{nil, {ID: 2}, {ID: 3, Superuser: true, Disabled: true}} {
		module.SetViewerResolver(func(*http.Request) *app.Viewer { return viewer })
		response := httptest.NewRecorder()
		handler.ServeHTTP(response, httptest.NewRequest("GET", "/admin/registrations/export.csv?tournament=987654", nil))
		want := 403
		if viewer == nil || viewer.Disabled {
			want = 302
		}
		if response.Code != want {
			t.Fatalf("legacy download gate=%d want=%d", response.Code, want)
		}
		if want == 302 && !strings.HasPrefix(response.Header().Get("Location"), "/accounts/login/?next=") {
			t.Fatal("bookmarked download lost login continuation")
		}
	}
}
