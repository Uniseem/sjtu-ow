package notify

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

func TestLegacyHeldPreviewIsStandaloneOwnedMailAndInventedAdminURLIs404(t *testing.T) {
	env := newEnv(t)
	owner := env.user("Owner")
	other := env.user("Other")
	batch := "11111111-1111-1111-1111-111111111111"
	frozen, _ := json.Marshal(mail.Letter{Subject: "Private frozen subject", Lead: "PRIVATE HELD BODY", Code: "004321"})
	recipients, _ := json.Marshal([][]string{{"recipient@example.test", "Recipient"}})
	env.exec("INSERT INTO held_letters(id,batch,actor_id,letter,recipients,back,in_back_office,state,created_at,decided_at) VALUES(1,?,?,?,?, '/admin/',1,'waiting',?,'')", batch, owner, string(frozen), string(recipients), db.FormatUTC(t0))
	ownerToken, err := auth.NewStore(env.d, nil).Create(context.Background(), owner)
	if err != nil {
		t.Fatal(err)
	}
	otherToken, err := auth.NewStore(env.d, nil).Create(context.Background(), other)
	if err != nil {
		t.Fatal(err)
	}
	var registry api.Registry
	NewModule(env.svc).Routes(&registry)
	handler := registry.Handler(func(*http.Request) *app.Viewer { return nil })
	call := func(path, token string) *httptest.ResponseRecorder {
		request := httptest.NewRequest(http.MethodGet, path, nil)
		if token != "" {
			request.AddCookie(&http.Cookie{Name: auth.CookieName, Value: token})
		}
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, request)
		return recorder
	}
	apiResponse := call("/api/letters/"+batch+"/1/preview", ownerToken)
	legacyResponse := call("/letters/"+batch+"/1/", ownerToken)
	if apiResponse.Code != 200 || legacyResponse.Code != 200 {
		t.Fatalf("document statuses API=%d legacy=%d", apiResponse.Code, legacyResponse.Code)
	}
	if legacyResponse.Header().Get("Location") != "" || legacyResponse.Body.String() != apiResponse.Body.String() {
		t.Fatal("legacy preview redirects or renders different frozen paper")
	}
	body := legacyResponse.Body.String()
	if !strings.Contains(body, "PRIVATE HELD BODY") || !strings.Contains(body, "004321") || strings.Contains(body, "<iframe") || strings.Contains(body, "<script") {
		t.Fatal("legacy route lost frozen body or gained application shell")
	}
	if legacyResponse.Header().Get("Cache-Control") != "no-store" || legacyResponse.Header().Get("Content-Security-Policy") != frozenMailCSP {
		t.Fatal("private mail policy changed")
	}
	assertNotFound := func(response *httptest.ResponseRecorder) {
		t.Helper()
		body := response.Body.String()
		policy := response.Header().Get("Content-Security-Policy")
		if response.Code != 404 || !strings.Contains(body, "<!DOCTYPE html>") || !strings.Contains(body, "页面不存在") || !strings.Contains(body, "/static/css/error.css") || strings.Contains(body, "<script") || strings.Contains(body, "PRIVATE HELD BODY") || strings.Contains(body, "004321") {
			t.Fatalf("private standalone404 status=%d", response.Code)
		}
		if strings.Contains(policy, "sandbox") || strings.Contains(policy, "unsafe-inline") || !strings.Contains(policy, "style-src 'self'") {
			t.Fatalf("error inherited mail CSP: %s", policy)
		}
		if response.Header().Get("Cache-Control") != "no-store" {
			t.Fatal("private error cached")
		}
	}
	for _, fixture := range []struct{ path, token string }{
		{"/letters/" + batch + "/1/", ""},
		{"/letters/" + batch + "/1/", otherToken},
		{"/letters/" + batch + "/999/", ownerToken},
		{"/letters/22222222-2222-2222-2222-222222222222/1/", ownerToken},
		{"/letters/" + batch + "/invalid/", ownerToken},
		{"/admin/letters/" + batch + "/1/", ownerToken},
		{"/admin/letters/" + batch + "/1/", otherToken},
		{"/admin/letters/" + batch + "/1/", ""},
	} {
		assertNotFound(call(fixture.path, fixture.token))
	}
	env.exec("UPDATE users SET is_active=0 WHERE id=?", owner)
	assertNotFound(call("/letters/"+batch+"/1/", ownerToken))
	// Existing API route remains private and keeps its original plain API 404.
	if response := call("/api/letters/"+batch+"/1/preview", otherToken); response.Code != 404 || strings.Contains(response.Body.String(), "PRIVATE HELD BODY") {
		t.Fatal("API preview privacy regressed")
	}
}
