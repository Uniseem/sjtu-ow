package activity

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCSVExportRequiresActivityCapability(t *testing.T) {
	d := newTestDB(t)
	module := NewModule(NewService(d, "https://example.test"))
	cases := []struct {
		name   string
		viewer *app.Viewer
		status int
	}{
		{"visitor", nil, http.StatusUnauthorized},
		{"disabled superuser", &app.Viewer{ID: 1, Superuser: true, Disabled: true}, http.StatusUnauthorized},
		{"ordinary member", &app.Viewer{ID: 2}, http.StatusForbidden},
		{"activity officer", &app.Viewer{ID: 3, Caps: map[app.Cap]struct{}{accounts.CapActivityView: {}}}, http.StatusOK},
		{"superuser", &app.Viewer{ID: 4, Superuser: true}, http.StatusOK},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			module.SetViewerResolver(func(*http.Request) *app.Viewer { return tc.viewer })
			response := httptest.NewRecorder()
			module.exportCSV(response, httptest.NewRequest(http.MethodGet, "/api/admin/activity/export?start=2026-10-01&end=2026-10-12", nil))
			if response.Code != tc.status {
				t.Fatalf("status=%d want=%d", response.Code, tc.status)
			}
			if response.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatal("export must never be shared cached")
			}
			if tc.status == http.StatusOK && !strings.HasPrefix(response.Header().Get("Content-Type"), "text/csv") {
				t.Fatal("authorized export lost CSV response")
			}
		})
	}
}

func TestCSVExportFailsClosedWithoutResolver(t *testing.T) {
	module := NewModule(NewService(nil, ""))
	response := httptest.NewRecorder()
	module.exportCSV(response, httptest.NewRequest(http.MethodGet, "/api/admin/activity/export", nil))
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("unconfigured export status=%d", response.Code)
	}
}

func TestLegacyActivityCSVPreservesLoginReturnAndCapabilityDoor(t *testing.T) {
	module := NewModule(NewService(newTestDB(t), "https://site.test"))
	path := "/admin/activity/?start=2026-01-01&end=2026-12-31&format=csv"
	for _, tc := range []struct {
		viewer *app.Viewer
		code   int
	}{
		{nil, 302}, {&app.Viewer{ID: 2}, 403}, {&app.Viewer{ID: 3, Superuser: true}, 200},
	} {
		module.SetViewerResolver(func(*http.Request) *app.Viewer { return tc.viewer })
		result := httptest.NewRecorder()
		module.legacyExportCSV(result, httptest.NewRequest("GET", path, nil))
		if result.Code != tc.code {
			t.Fatalf("legacy gate=%d want=%d", result.Code, tc.code)
		}
		if tc.code == 302 && !strings.Contains(result.Header().Get("Location"), "next=%2Fadmin%2Factivity%2F") {
			t.Fatal("lost original return URL")
		}
		if tc.code == 403 && (!strings.Contains(result.Body.String(), "你没有权限查看这个页面。") || strings.Contains(result.Body.String(), "<script")) {
			t.Fatal("forbidden download is not the frozen private error document")
		}
	}
}
