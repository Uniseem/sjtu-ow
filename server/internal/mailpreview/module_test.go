package mailpreview

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

func previewHarness(viewer **app.Viewer) http.Handler {
	resolve := func(*http.Request) *app.Viewer { return *viewer }
	module := NewModule(resolve)
	registry := &api.Registry{}
	module.Routes(registry)
	return registry.Handler(resolve)
}

func TestMailSampleJSONAndRawDocumentsRequireAdminCapability(t *testing.T) {
	admin := &app.Viewer{ID: 1, EmailVerified: true, Caps: map[app.Cap]struct{}{"admin.enter": {}}}
	viewer := admin
	handler := previewHarness(&viewer)
	request := func(path string) *httptest.ResponseRecorder {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, path, nil))
		return recorder
	}
	if result := request("/api/admin/mail-samples"); result.Code != http.StatusOK {
		t.Fatalf("admin catalogue: %d %s", result.Code, result.Body.String())
	}
	viewer = &app.Viewer{ID: 2, EmailVerified: true, Caps: map[app.Cap]struct{}{}}
	if result := request("/api/admin/mail-samples"); result.Code != http.StatusForbidden {
		t.Fatalf("member catalogue: %d", result.Code)
	}
	for _, path := range []string{"/api/admin/mail-samples/verify/preview", "/api/admin/mail-samples/verify/text"} {
		result := request(path)
		if result.Code != http.StatusNotFound || strings.Contains(result.Body.String(), "482915") {
			t.Fatalf("member raw leak: %s %d %s", path, result.Code, result.Body.String())
		}
	}
	viewer = nil
	if result := request("/api/admin/mail-samples"); result.Code != http.StatusUnauthorized {
		t.Fatalf("anonymous catalogue: %d", result.Code)
	}
	viewer = &app.Viewer{ID: 1, Disabled: true, Superuser: true}
	if result := request("/api/admin/mail-samples/verify/preview"); result.Code == http.StatusOK {
		t.Fatal("disabled superuser preview accepted")
	}
	viewer = admin
	if result := request("/api/admin/mail-samples/not-a-real-type/preview"); result.Code != http.StatusNotFound {
		t.Fatalf("unknown type: %d", result.Code)
	}
}

func TestMailSamplesKeepEveryLegacyKeyAndNeverUseRealRecipientAddresses(t *testing.T) {
	oldKeys := []string{
		"verify", "reset", "unknown", "exists", "smtp", "apply", "apply-ok", "apply-no", "applications-waiting", "removed",
		"unplaced-reminder", "tournament-update", "tournament-update-again", "member-left", "captain", "disbanded",
		"submitted", "entered", "approved", "rejected", "cancelled", "formed", "returned", "left", "tournament-reminder",
		"reminder", "new-tournament", "new-article", "new-scrim", "scrim-update", "scrim-cancelled", "patrol", "ask-author", "avatar-taken-down",
	}
	samples := Catalogue()
	byKey := map[string]Sample{}
	for _, sample := range samples {
		if _, duplicate := byKey[sample.Key]; duplicate {
			t.Fatalf("duplicate catalogue key: %s", sample.Key)
		}
		byKey[sample.Key] = sample
		described := describe(sample)
		if !described.Fictional || !strings.Contains(described.Text, sampleRoot) {
			t.Fatalf("sample not marked fictional: %+v", described)
		}
		for _, url := range append(append([]string{}, sample.Letter.Action...), sample.Letter.Unsubscribe) {
			if strings.HasPrefix(url, "http") && !strings.HasPrefix(url, sampleRoot) {
				t.Fatalf("sample %s contains live URL: %s", sample.Key, url)
			}
		}
		if strings.Contains(described.Text, "@example.com") || strings.Contains(described.Text, "@sjtu.edu.cn") {
			t.Fatalf("sample %s contains nonfictional email", sample.Key)
		}
		rendered, err := BrowserHTML(sample.Letter, sample.Name)
		if err != nil {
			t.Fatalf("render %s: %v", sample.Key, err)
		}
		if strings.Contains(rendered, "cid:") {
			t.Fatalf("sample %s left unresolved email artwork", sample.Key)
		}
		for _, cid := range []string{"ow-mark", "ow-horizon"} {
			encoded := base64.StdEncoding.EncodeToString(mail.Art()[cid])
			if !strings.Contains(rendered, "data:image/png;base64,"+encoded) {
				t.Fatalf("sample %s omitted production art %s", sample.Key, cid)
			}
		}
	}
	for _, key := range oldKeys {
		if _, found := byKey[key]; !found {
			t.Errorf("legacy sample missing: %s", key)
		}
	}
}

func TestMailPreviewHasNarrowCSPAndNoSharedCache(t *testing.T) {
	viewer := &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}}}
	handler := previewHarness(&viewer)
	for _, suffix := range []string{"preview", "text"} {
		result := httptest.NewRecorder()
		handler.ServeHTTP(result, httptest.NewRequest(http.MethodGet, "/api/admin/mail-samples/verify/"+suffix, nil))
		if result.Code != http.StatusOK {
			t.Fatalf("%s status=%d", suffix, result.Code)
		}
		if !strings.Contains(result.Header().Get("Cache-Control"), "no-store") {
			t.Fatal("sample can be cached")
		}
		csp := result.Header().Get("Content-Security-Policy")
		for _, part := range []string{"default-src 'none'", "img-src data:", "frame-ancestors 'self'", "form-action 'none'", "sandbox"} {
			if !strings.Contains(csp, part) {
				t.Fatalf("%s policy missing %q: %s", suffix, part, csp)
			}
		}
		if strings.Contains(csp, "unsafe-eval") || strings.Contains(csp, "script-src 'unsafe-inline'") {
			t.Fatalf("mail preview permits executable code: %s", csp)
		}
		if result.Header().Get("X-Frame-Options") != "SAMEORIGIN" {
			t.Fatal("mail preview framing unrestricted")
		}
	}
}

func TestMailCatalogueGroupingFilteringAndDefaultPrefix(t *testing.T) {
	viewer := &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}}}
	handler := previewHarness(&viewer)
	result := httptest.NewRecorder()
	handler.ServeHTTP(result, httptest.NewRequest(http.MethodGet, "/api/admin/mail-samples?group=%E8%B4%A6%E5%8F%B7&q=verify", nil))
	if result.Code != http.StatusOK {
		t.Fatal(result.Code, result.Body.String())
	}
	var data ListOut
	if err := json.Unmarshal(result.Body.Bytes(), &data); err != nil {
		t.Fatal(err)
	}
	if len(data.Items) == 0 || data.Total <= len(data.Items) {
		t.Fatalf("filter ignored: %+v", data)
	}
	for _, sample := range data.Items {
		if sample.Group != "账号" || !strings.HasPrefix(sample.DeliveredSubject, mail.DefaultPrefix) {
			t.Fatalf("wrong filtered sample: %+v", sample)
		}
	}
	total := 0
	for _, group := range data.Groups {
		total += group.Count
	}
	if total != data.Total {
		t.Fatalf("group counts=%d total=%d", total, data.Total)
	}
}

func TestProductionMailRendererEscapesFictionalInputs(t *testing.T) {
	body, err := BrowserHTML(mail.Letter{
		Subject: `<script>alert(1)</script>`, Lead: `<img src=x onerror=alert(2)>`,
		Action: []string{"Unsafe link", "javascript:alert(3)"},
	}, `<svg onload=alert(4)>`)
	if err != nil {
		t.Fatal(err)
	}
	for _, unsafe := range []string{"<script", "<svg", "<img src=x", `href="javascript:`} {
		if strings.Contains(body, unsafe) {
			t.Fatalf("rendered executable input %q", unsafe)
		}
	}
}
