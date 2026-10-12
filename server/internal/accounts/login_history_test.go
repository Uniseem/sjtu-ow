package accounts

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestLoginHistoryTracksRealLoginAndVerificationButNotCLISessions(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	now := time.Date(2026, 10, 13, 1, 2, 3, 0, time.UTC)
	frozen := clock.Fixed(now)
	svc := NewService(d, frozen, "https://example.test", nil, nil)
	user := newVerifiedUser(t, d, "login-history@example.test", "登录历史", "Password123!@#", true)
	if _, err := svc.Login(ctx, LoginInput{Email: user.Email, Password: "Password123!@#"}); err != nil {
		t.Fatal(err)
	}
	check := func(id int64, expected time.Time) {
		t.Helper()
		var value string
		if err := d.ReadPool().QueryRowContext(ctx, "SELECT last_login_at FROM users WHERE id=?", id).Scan(&value); err != nil {
			t.Fatal(err)
		}
		if value != db.FormatUTC(expected) {
			t.Fatalf("wrong login timestamp: %q", value)
		}
	}
	check(user.ID, now)
	later := now.Add(time.Hour)
	if _, err := auth.NewStore(d, clock.Fixed(later)).Create(ctx, user.ID); err != nil {
		t.Fatal(err)
	}
	check(user.ID, now)
	if _, err := svc.Login(ctx, LoginInput{Email: user.Email, Password: "wrong-password"}); err == nil {
		t.Fatal("invalid login passed")
	}
	check(user.ID, now)
	detail, err := svc.GetUserDetail(&app.Ctx{Context: ctx, Viewer: &app.Viewer{ID: user.ID, Superuser: true}}, UserDetailInput{ID: api.ID(user.ID)})
	if err != nil || detail.LastLoginAt == nil || !detail.LastLoginAt.Equal(now) {
		t.Fatalf("admin projection: %v %v", detail, err)
	}
	svc.codeGen = fixedCode("123456")
	mustRegister(t, svc, "verify-history@example.test", "邮箱历史", "Password123!@#")
	verified, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "verify-history@example.test", Code: "123456"})
	if err != nil {
		t.Fatal(err)
	}
	session, err := svc.sessions.Lookup(ctx, verified.Token)
	if err != nil || session == nil {
		t.Fatal("verification session missing", err)
	}
	check(session.UserID, now)
	// A failed history update rolls session creation back in the same transaction.
	execAll(t, d, `CREATE TRIGGER reject_history BEFORE UPDATE OF last_login_at ON users BEGIN SELECT RAISE(ABORT,'history write failed'); END`)
	before := countOf(t, d, `SELECT count(*) FROM sessions`)
	if _, err := svc.Login(ctx, LoginInput{Email: user.Email, Password: "Password123!@#"}); err == nil {
		t.Fatal("failed history write passed")
	}
	if countOf(t, d, `SELECT count(*) FROM sessions`) != before {
		t.Fatal("session survived rejected login history update")
	}
}

func TestLegacyLoginHistoryPreservesNullableTimeAndRejectsInvalidTime(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "legacy.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	statements := []string{
		`CREATE TABLE accounts_user(id INTEGER,email TEXT,password TEXT,nickname TEXT,is_sjtu INTEGER,agreed_terms_at TEXT,agreed_cross_border_at TEXT,date_joined TEXT,is_active INTEGER,is_superuser INTEGER,last_login TEXT)`,
		`INSERT INTO accounts_user VALUES(1,'one@example.test','!','一个用户',0,'2026-01-01 00:00:00','2026-01-01 00:00:00','2026-01-01 00:00:00',1,0,'2026-10-12 08:09:10.123456'),(2,'two@example.test','!','另个用户',0,'2026-01-01 00:00:00','2026-01-01 00:00:00','2026-01-01 00:00:00',1,0,NULL),(3,'deleted-3@deleted.invalid','!','已注销用户',0,'2026-01-01 00:00:00','2026-01-01 00:00:00','2026-01-01 00:00:00',0,0,'2026-10-01 08:09:10')`,
	}
	for _, statement := range statements {
		if _, err := legacy.ExecContext(ctx, statement); err != nil {
			t.Fatal(err)
		}
	}
	for i := 0; i < 2; i++ {
		if err := ImportLegacyAccounts(ctx, d, legacy); err != nil {
			t.Fatal(err)
		}
	}
	var value string
	if err := d.ReadPool().QueryRowContext(ctx, `SELECT last_login_at FROM users WHERE id=1`).Scan(&value); err != nil {
		t.Fatal(err)
	}
	parsed, err := db.ParseUTC("2026-10-12 08:09:10.123456")
	if err != nil || value != db.FormatUTC(parsed) {
		t.Fatal("legacy login time changed", value, err)
	}
	if countOf(t, d, `SELECT count(*) FROM users WHERE id=2 AND last_login_at IS NULL`) != 1 {
		t.Fatal("never-logged-in user got fake timestamp")
	}
	if countOf(t, d, `SELECT count(*) FROM users WHERE id=3 AND last_login_at IS NULL`) != 1 {
		t.Fatal("anonymized legacy account regained personal login history")
	}
	if _, err := legacy.ExecContext(ctx, `UPDATE accounts_user SET last_login='not-a-time' WHERE id=1`); err != nil {
		t.Fatal(err)
	}
	if err := ImportLegacyAccounts(ctx, d, legacy); err == nil {
		t.Fatal("invalid legacy login time accepted")
	}
	var after string
	_ = d.ReadPool().QueryRowContext(ctx, `SELECT last_login_at FROM users WHERE id=1`).Scan(&after)
	if after != value {
		t.Fatal("failed import overwrote preserved history")
	}
}
