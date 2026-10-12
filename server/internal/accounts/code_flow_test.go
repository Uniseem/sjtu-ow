package accounts

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestAnonymousCodeFlowHTTPShapeAndThirdAttemptDoNotEnumerateAccounts(t *testing.T) {
	for _, purpose := range []string{"signup", "password_reset"} {
		t.Run(purpose, func(t *testing.T) {
			database := newTestDB(t)
			svc := NewService(database, nil, "https://site.test", nil, nil)
			svc.codeGen = fixedCode("654321")
			newVerifiedUser(t, database, "known@sjtu.edu.cn", "Known", "Password123!@#", true)
			disabled := newVerifiedUser(t, database, "disabled@sjtu.edu.cn", "Disabled", "Password123!@#", true)
			if err := database.WriteTx(context.Background(), func(c context.Context, tx *db.Tx) error {
				_, err := tx.ExecContext(c, "UPDATE users SET is_active=0 WHERE id=?", disabled.ID)
				return err
			}); err != nil {
				t.Fatal(err)
			}
			var registry api.Registry
			NewModule(svc).Routes(&registry)
			handler := registry.Handler(func(*http.Request) *app.Viewer { return nil }, api.WithSecureCookies(true))
			call := func(method, path, body string, cookie *http.Cookie) *httptest.ResponseRecorder {
				request := httptest.NewRequest(method, path, strings.NewReader(body))
				request.Header.Set("Content-Type", "application/json")
				if cookie != nil {
					request.AddCookie(cookie)
				}
				recorder := httptest.NewRecorder()
				handler.ServeHTTP(recorder, request)
				return recorder
			}
			beginPath, statePath, verifyPath, cookieName := "/api/auth/resend-code", "/api/auth/verify-email/state", "/api/auth/verify-email", auth.SignupFlowCookieName
			if purpose == "password_reset" {
				beginPath = "/api/auth/reset-password"
				statePath = "/api/auth/reset-password/code-state"
				verifyPath = "/api/auth/reset-password/verify"
				cookieName = auth.ResetCodeFlowCookieName
			}
			missing := call("GET", statePath, "", nil)
			if missing.Code != 200 || missing.Header().Get("Cache-Control") != "no-store" || strings.Contains(missing.Body.String(), `"email"`) {
				t.Fatalf("missing anonymous state: %d %s", missing.Code, missing.Body.String())
			}
			var firstFailure string
			for _, email := range []string{"known@sjtu.edu.cn", "unknown@sjtu.edu.cn", "disabled@sjtu.edu.cn"} {
				started := call("POST", beginPath, `{"email":"`+email+`"}`, nil)
				cookies := started.Result().Cookies()
				if started.Code != 200 || len(cookies) != 1 {
					t.Fatalf("begin %s: %d cookies=%d %s", email, started.Code, len(cookies), started.Body.String())
				}
				cookie := cookies[0]
				if cookie.Name != cookieName || !cookie.HttpOnly || !cookie.Secure || cookie.SameSite != http.SameSiteLaxMode || resetTokenHash(cookie.Value) == "" || strings.Contains(started.Body.String(), cookie.Value) {
					t.Fatalf("invalid/private flow cookie for %s", email)
				}
				for attempt := 1; attempt <= 3; attempt++ {
					failed := call("POST", verifyPath, `{"email":"`+email+`","code":"999999"}`, cookie)
					if failed.Code != 422 {
						t.Fatalf("flow must retain failed POST contract: %d %s", failed.Code, failed.Body.String())
					}
					if firstFailure == "" {
						firstFailure = failed.Body.String()
					} else if failed.Body.String() != firstFailure {
						t.Fatal("failure response enumerated account or attempts")
					}
					stateResponse := call("GET", statePath, "", cookie)
					var state CodeFlowState
					if err := json.Unmarshal(stateResponse.Body.Bytes(), &state); err != nil {
						t.Fatal(err)
					}
					if state.Active != (attempt < 3) {
						t.Fatalf("attempt %d for %s active=%v", attempt, email, state.Active)
					}
					if attempt < 3 && state.Email != email {
						t.Fatal("active state lost caller-provided address")
					}
					if attempt == 3 && state.Email != "" {
						t.Fatal("closed state retained address")
					}
				}
			}
		})
	}
}

func TestAnonymousCodeFlowExpiresReplaysAndBindsAddressAndPurpose(t *testing.T) {
	database := newTestDB(t)
	now := time.Date(2026, 10, 12, 0, 0, 0, 0, time.UTC)
	svc := NewService(database, clock.Fixed(now), "https://site.test", nil, nil)
	ctx := &app.Ctx{Context: context.Background()}
	if err := svc.startCodeFlow(ctx, "signup", "unknown@example.test"); err != nil {
		t.Fatal(err)
	}
	first := ctx.DrainCodeFlowCookies()[0]
	state, err := svc.codeFlowState(ctx.Context, "signup", first.Token)
	if err != nil || !state.Active || first.ExpiresAt.Sub(now) != 15*time.Minute {
		t.Fatalf("start state %+v %v", state, err)
	}
	otherPurpose, err := svc.codeFlowState(ctx.Context, "password_reset", first.Token)
	if err != nil || otherPurpose.Active {
		t.Fatal("purpose boundary broken")
	}
	_, err = svc.VerifyEmail(ctx.Context, VerifyEmailInput{Email: "other@example.test", Code: "999999"}, first.Token)
	if err == nil {
		t.Fatal("different address accepted")
	}
	var attempts int
	if err := database.ReadPool().QueryRow("SELECT attempts FROM account_code_flows WHERE token_hash=?", resetTokenHash(first.Token)).Scan(&attempts); err != nil || attempts != 0 {
		t.Fatalf("foreign address changed attempts: %d %v", attempts, err)
	}
	ctx.CodeFlowTokens = map[string]string{"signup": first.Token}
	if err := svc.startCodeFlow(ctx, "signup", "unknown@example.test"); err != nil {
		t.Fatal(err)
	}
	second := ctx.DrainCodeFlowCookies()[0]
	state, err = svc.codeFlowState(ctx.Context, "signup", first.Token)
	if err != nil || state.Active {
		t.Fatal("resend did not revoke previous browser flow")
	}
	svc.clock = clock.Fixed(second.ExpiresAt)
	state, err = svc.codeFlowState(ctx.Context, "signup", second.Token)
	if err != nil || state.Active {
		t.Fatal("expiry boundary accepted")
	}
	if count, err := svc.CleanupCodeFlows(ctx.Context, second.ExpiresAt); err != nil || count != 1 {
		t.Fatalf("cleanup: %d %v", count, err)
	}
}

func TestAnonymousCodeFlowConcurrentAttemptsCommitAndStopAtThree(t *testing.T) {
	database := newTestDB(t)
	svc := NewService(database, nil, "https://site.test", nil, nil)
	ctx := &app.Ctx{Context: context.Background()}
	if err := svc.startCodeFlow(ctx, "signup", "unknown@example.test"); err != nil {
		t.Fatal(err)
	}
	token := ctx.DrainCodeFlowCookies()[0].Token
	var group sync.WaitGroup
	for attempt := 0; attempt < 8; attempt++ {
		group.Add(1)
		go func() {
			defer group.Done()
			_, err := svc.VerifyEmail(ctx.Context, VerifyEmailInput{Email: "unknown@example.test", Code: "999999"}, token)
			if err == nil {
				t.Error("unknown address verified")
			}
		}()
	}
	group.Wait()
	var attempts, closed int
	if err := database.ReadPool().QueryRow("SELECT attempts,closed FROM account_code_flows WHERE token_hash=?", resetTokenHash(token)).Scan(&attempts, &closed); err != nil || attempts != 3 || closed != 1 {
		t.Fatalf("concurrent attempt gate: %d %d %v", attempts, closed, err)
	}
}

func TestAnonymousCodeFlowCorrectThirdAttemptStillVerifies(t *testing.T) {
	database := newTestDB(t)
	svc := NewService(database, nil, "https://site.test", nil, nil)
	svc.codeGen = fixedCode("654321")
	user := newVerifiedUser(t, database, "pending@example.test", "Pending", "Password123!@#", true)
	if err := database.WriteTx(context.Background(), func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE users SET email_verified_at=NULL WHERE id=?", user.ID)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	ctx := &app.Ctx{Context: context.Background()}
	if _, err := svc.ResendCode(ctx.Context, ResendCodeInput{Email: user.Email}); err != nil {
		t.Fatal(err)
	}
	if err := svc.startCodeFlow(ctx, "signup", user.Email); err != nil {
		t.Fatal(err)
	}
	token := ctx.DrainCodeFlowCookies()[0].Token
	for i := 0; i < 2; i++ {
		if _, err := svc.VerifyEmail(ctx.Context, VerifyEmailInput{Email: user.Email, Code: "999999"}, token); err == nil {
			t.Fatal("wrong code accepted")
		}
	}
	verified, err := svc.VerifyEmail(ctx.Context, VerifyEmailInput{Email: user.Email, Code: "654321"}, token)
	if err != nil || verified.Token == "" {
		t.Fatalf("correct third try: %+v %v", verified, err)
	}
	state, err := svc.codeFlowState(ctx.Context, "signup", token)
	if err != nil || state.Active {
		t.Fatal("success did not consume browser flow")
	}
}

func TestAnonymousCodeFlowRevocationErasesOnlyMatchingAddress(t *testing.T) {
	database := newTestDB(t)
	svc := NewService(database, nil, "https://site.test", nil, nil)
	ctx := &app.Ctx{Context: context.Background()}
	for _, email := range []string{"first@example.test", "second@example.test"} {
		if err := svc.startCodeFlow(ctx, "signup", email); err != nil {
			t.Fatal(err)
		}
	}
	if err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error { return RevokeCodeFlowsForEmail(c, tx, "FIRST@example.test") }); err != nil {
		t.Fatal(err)
	}
	var count int
	if err := database.ReadPool().QueryRow("SELECT COUNT(*) FROM account_code_flows").Scan(&count); err != nil || count != 1 {
		t.Fatalf("revocation: %d %v", count, err)
	}
	if err := database.ReadPool().QueryRow("SELECT COUNT(*) FROM account_code_flows WHERE email_norm='second@example.test'").Scan(&count); err != nil || count != 1 {
		t.Fatal("revocation removed another workflow")
	}
}

func TestAnonymousResetCodeFlowCorrectThirdAttemptIssuesOnlyResetGrant(t *testing.T) {
	database := newTestDB(t)
	svc := NewService(database, nil, "https://site.test", nil, nil)
	svc.codeGen = fixedCode("654321")
	user := newVerifiedUser(t, database, "reset-flow@example.test", "Reset", "Password123!@#", true)
	ctx := &app.Ctx{Context: context.Background()}
	if _, err := svc.RequestPasswordReset(ctx.Context, ResetPasswordInput{Email: user.Email}); err != nil {
		t.Fatal(err)
	}
	if err := svc.startCodeFlow(ctx, "password_reset", user.Email); err != nil {
		t.Fatal(err)
	}
	cookie := ctx.DrainCodeFlowCookies()[0]
	if remaining := time.Until(cookie.ExpiresAt); remaining > 3*time.Minute || remaining < 2*time.Minute {
		t.Fatalf("reset lifetime: %v", remaining)
	}
	for i := 0; i < 2; i++ {
		if _, err := svc.VerifyPasswordResetCode(ctx.Context, ResetCodeInput{Email: user.Email, Code: "999999"}, cookie.Token); err == nil {
			t.Fatal("wrong reset code accepted")
		}
	}
	grant, err := svc.VerifyPasswordResetCode(ctx.Context, ResetCodeInput{Email: user.Email, Code: "654321"}, cookie.Token)
	if err != nil || grant.Token == "" {
		t.Fatalf("correct third reset try: %+v %v", grant, err)
	}
	state, err := svc.codeFlowState(ctx.Context, "password_reset", cookie.Token)
	if err != nil || state.Active {
		t.Fatal("reset success did not consume anonymous flow")
	}
	var sessions int
	if err := database.ReadPool().QueryRow("SELECT COUNT(*) FROM sessions WHERE user_id=?", user.ID).Scan(&sessions); err != nil || sessions != 0 {
		t.Fatalf("reset verification created login session: %d %v", sessions, err)
	}
}

func TestAnonymousExpiredFlowDoesNotConsumeLiveCodeOrRevealItsPresence(t *testing.T) {
	database := newTestDB(t)
	svc := NewService(database, nil, "https://site.test", nil, nil)
	svc.codeGen = fixedCode("654321")
	user := newVerifiedUser(t, database, "expired-flow@example.test", "Expired", "Password123!@#", true)
	ctx := &app.Ctx{Context: context.Background()}
	if _, err := svc.RequestPasswordReset(ctx.Context, ResetPasswordInput{Email: user.Email}); err != nil {
		t.Fatal(err)
	}
	if err := svc.startCodeFlow(ctx, "password_reset", user.Email); err != nil {
		t.Fatal(err)
	}
	token := ctx.DrainCodeFlowCookies()[0].Token
	if err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE account_code_flows SET expires_at=? WHERE token_hash=?", db.FormatUTC(svc.clock.Now()), resetTokenHash(token))
		return err
	}); err != nil {
		t.Fatal(err)
	}
	_, err := svc.VerifyPasswordResetCode(ctx.Context, ResetCodeInput{Email: user.Email, Code: "654321"}, token)
	if err != errBadCode {
		t.Fatalf("expired workflow must retain uniform code error: %v", err)
	}
	state, err := svc.codeFlowState(ctx.Context, "password_reset", token)
	if err != nil || state.Active || state.Email != "" {
		t.Fatalf("expired state: %+v %v", state, err)
	}
	// API consumers without browser flow retain the existing code contract.
	grant, err := svc.VerifyPasswordResetCode(ctx.Context, ResetCodeInput{Email: user.Email, Code: "654321"})
	if err != nil || grant.Token == "" {
		t.Fatalf("expired browser state changed direct API behavior: %+v %v", grant, err)
	}
}
