package accounts

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
)

func TestResetGrantHTTPIsPrivateSingleUseAndResendInvalidates(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://site.test", nil, nil)
	svc.codeGen = fixedCode("654321")
	u := newVerifiedUser(t, d, "reset@sjtu.edu.cn", "重置", "Password123!@#", true)
	oldSession, err := svc.sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	r := &api.Registry{}
	NewModule(svc).Routes(r)
	h := r.Handler(func(*http.Request) *app.Viewer { return nil }, api.WithSecureCookies(true))
	call := func(method, path, body string, cookie *http.Cookie) *httptest.ResponseRecorder {
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		if cookie != nil {
			req.AddCookie(cookie)
		}
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec
	}
	issue := func() *http.Cookie {
		t.Helper()
		if _, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: u.Email}); err != nil {
			t.Fatal(err)
		}
		bad := call("POST", "/api/auth/reset-password/verify", `{"email":"reset@sjtu.edu.cn","code":"000000"}`, nil)
		if bad.Code != 422 {
			t.Fatalf("wrong code: %d", bad.Code)
		}
		code, err := svc.store.GetLatestEmailCode(ctx, "password_reset", u.EmailNorm)
		if err != nil || code == nil || code.Attempts != 1 {
			t.Fatalf("attempt must commit: %+v %v", code, err)
		}
		verified := call("POST", "/api/auth/reset-password/verify", `{"email":"reset@sjtu.edu.cn","code":"654321"}`, nil)
		if verified.Code != 200 {
			t.Fatalf("verify: %d %s", verified.Code, verified.Body.String())
		}
		cookies := verified.Result().Cookies()
		if len(cookies) != 1 || cookies[0].Name != auth.ResetCookieName || !cookies[0].HttpOnly || !cookies[0].Secure || cookies[0].SameSite != http.SameSiteLaxMode || cookies[0].MaxAge > 180 || cookies[0].MaxAge <= 0 {
			t.Fatalf("grant cookie: %+v", cookies)
		}
		cookie := cookies[0]
		if strings.Contains(verified.Body.String(), cookie.Value) {
			t.Fatal("grant must never be JSON")
		}
		grant, err := svc.store.GetLatestEmailCode(ctx, resetGrantPurpose, u.EmailNorm)
		if err != nil || grant == nil || grant.CodeHash != resetTokenHash(cookie.Value) || grant.CodeHash == cookie.Value {
			t.Fatalf("database stores hash only: %+v %v", grant, err)
		}
		return cookie
	}
	first := issue()
	if _, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: u.Email}); err != nil {
		t.Fatal(err)
	}
	stale := call("GET", "/api/auth/reset-password/state", "", first)
	var state ResetState
	if err := json.Unmarshal(stale.Body.Bytes(), &state); err != nil || state.Verified || state.Email != "" {
		t.Fatalf("resend invalidates proof: %s %v", stale.Body.String(), err)
	}
	proof := issue()
	good := call("GET", "/api/auth/reset-password/state", "", proof)
	if err := json.Unmarshal(good.Body.Bytes(), &state); err != nil || !state.Verified || state.Email != u.Email {
		t.Fatalf("state: %s %v", good.Body.String(), err)
	}
	body := `{"password":"AnotherSafe!2026","confirm_password":"AnotherSafe!2026"}`
	if missing := call("POST", "/api/auth/reset-password/complete", body, nil); missing.Code != 422 {
		t.Fatal("password requires proof")
	}
	weak := call("POST", "/api/auth/reset-password/complete", `{"password":"12345678","confirm_password":"12345678"}`, proof)
	if weak.Code != 422 {
		t.Fatal("weak password accepted")
	}
	done := call("POST", "/api/auth/reset-password/complete", body, proof)
	if done.Code != 200 {
		t.Fatalf("complete: %d %s", done.Code, done.Body.String())
	}
	for _, c := range done.Result().Cookies() {
		if c.Value != "" || c.MaxAge >= 0 {
			t.Fatalf("reset must not log in: %+v", c)
		}
	}
	if sess, err := svc.sessions.Lookup(ctx, oldSession); err != nil || sess != nil {
		t.Fatalf("all old sessions invalidated: %+v %v", sess, err)
	}
	if replay := call("POST", "/api/auth/reset-password/complete", body, proof); replay.Code != 422 {
		t.Fatal("grant replay accepted")
	}
	updated, err := svc.store.GetByID(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	ok, _, err := auth.Verify(ctx, updated.PasswordHash, "AnotherSafe!2026")
	if err != nil || !ok {
		t.Fatalf("new password: %v %v", ok, err)
	}
}

func TestResetProofKeepsTheOriginalThreeMinuteDeadline(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	start := time.Date(2026, 10, 10, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: start}
	svc := NewService(d, clk, "https://site.test", nil, nil)
	svc.codeGen = fixedCode("654321")
	u := newVerifiedUser(t, d, "deadline@sjtu.edu.cn", "截止", "Password123!@#", true)
	if _, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: u.Email}); err != nil {
		t.Fatal(err)
	}
	clk.t = start.Add(2 * time.Minute)
	grant, err := svc.VerifyPasswordResetCode(ctx, ResetCodeInput{Email: u.Email, Code: "654321"})
	if err != nil || !grant.ExpiresAt.Equal(start.Add(3*time.Minute)) {
		t.Fatalf("verification must not extend the deadline: %+v %v", grant, err)
	}
	clk.t = start.Add(3 * time.Minute)
	state, err := svc.PasswordResetState(ctx, grant.Token)
	if err != nil || state.Verified || state.Email != "" {
		t.Fatalf("expired proof: %+v %v", state, err)
	}
	if _, err := svc.CompletePasswordReset(ctx, grant.Token, CompleteResetInput{Password: "AnotherSafe!2026", ConfirmPassword: "AnotherSafe!2026"}); err == nil {
		t.Fatal("expired proof accepted")
	}
}

func TestEmailChangeWrongAttemptsCommitAndCancellation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	clk := clock.Fixed(time.Now().UTC())
	svc := NewService(d, clk, "https://site.test", nil, nil)
	svc.codeGen = fixedCode("123456")
	u := newVerifiedUser(t, d, "old@sjtu.edu.cn", "邮箱", "Password123!@#", true)
	token, err := svc.sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	actor := newTestCtx(ctx, u, token, false)
	if _, err := svc.RequestEmailChange(actor, RequestEmailChangeInput{NewEmail: "next@sjtu.edu.cn"}); err == nil {
		t.Fatal("reauth required")
	}
	if _, err := svc.Reauthenticate(actor, ReauthInput{Password: "Password123!@#"}); err != nil {
		t.Fatal(err)
	}
	request := func() {
		t.Helper()
		if _, err := svc.RequestEmailChange(actor, RequestEmailChangeInput{NewEmail: "next@sjtu.edu.cn"}); err != nil {
			t.Fatal(err)
		}
	}
	request()
	for n := 1; n <= 3; n++ {
		if _, err := svc.ConfirmEmailChange(actor, ConfirmEmailChangeInput{Code: "000000"}); err == nil {
			t.Fatal("wrong code accepted")
		}
		var count int
		if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM email_changes WHERE user_id = ?", u.ID).Scan(&count); err != nil {
			t.Fatal(err)
		}
		if n == 3 {
			if count != 0 {
				t.Fatal("third attempt must invalidate")
			}
			continue
		}
		var attempts int
		if err := d.ReadPool().QueryRowContext(ctx, "SELECT attempts FROM email_changes WHERE user_id = ?", u.ID).Scan(&attempts); err != nil || attempts != n {
			t.Fatalf("attempt rollback: %d %v", attempts, err)
		}
	}
	if _, err := svc.ConfirmEmailChange(actor, ConfirmEmailChangeInput{Code: "123456"}); err == nil {
		t.Fatal("exhausted code accepted")
	}
	request()
	state, err := svc.EmailChangeState(actor)
	if err != nil || state.PendingEmail != "next@sjtu.edu.cn" || state.Email != u.Email || !state.Reauthenticated {
		t.Fatalf("state: %+v %v", state, err)
	}
	if _, err := svc.CancelEmailChange(actor); err != nil {
		t.Fatal(err)
	}
	state, err = svc.EmailChangeState(actor)
	if err != nil || state.PendingEmail != "" {
		t.Fatal("cancel did not remove pending email")
	}
	request()
	if _, err := svc.ConfirmEmailChange(actor, ConfirmEmailChangeInput{Code: "123456"}); err != nil {
		t.Fatal(err)
	}
	if notice, err := svc.sessions.PopNotice(ctx, token); err != nil || notice != "邮箱修改成功。" {
		t.Fatalf("notice: %q %v", notice, err)
	}
	state, err = svc.EmailChangeState(actor)
	if err != nil || state.Email != "next@sjtu.edu.cn" || state.PendingEmail != "" {
		t.Fatalf("new email: %+v %v", state, err)
	}
}
