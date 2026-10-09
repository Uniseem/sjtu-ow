package scrims

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

var t0 = time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)

type env struct {
	t      *testing.T
	d      *db.DB
	svc    *Service
	n      int64
	now    time.Time
	denied map[int64]bool
}

func newEnv(t *testing.T) *env {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "scrims.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	e := &env{t: t, d: d, svc: NewService(d, "https://sjtu.example"), now: t0, denied: map[int64]bool{}}
	e.svc.SetRand(rand.New(rand.NewSource(1)))
	e.svc.SetViewerBuilder(func(_ context.Context, id int64) (*app.Viewer, error) {
		v := &app.Viewer{ID: id, EmailVerified: true}
		if e.denied[id] {
			v.FeatureDenied = map[app.Feature]struct{}{accounts.FeatureScrimSignup: {}}
		}
		return v, nil
	})
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (900, 'mgr@sjtu.example', 'mgr@sjtu.example', 'h', '内战管理员', 1, ?, ?, ?, 1, ?, ?)`,
		ts(t0), ts(t0), ts(t0), ts(t0), ts(t0))
	return e
}

func ts(t time.Time) string { return db.FormatUTC(t) }

func (e *env) exec(q string, args ...any) {
	e.t.Helper()
	if err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, q, args...)
		return err
	}); err != nil {
		e.t.Fatalf("exec %q: %v", q, err)
	}
}

func (e *env) count(q string, args ...any) int {
	e.t.Helper()
	var n int
	if err := e.d.ReadPool().QueryRow(q, args...).Scan(&n); err != nil {
		e.t.Fatal(err)
	}
	return n
}

func email(id int64) string { return fmt.Sprintf("u%d@sjtu.example", id) }

// user 建一个资料完整的用户，游戏 ID 上三个位置的段位由参数给（0 表示没填）。
func (e *env) user(nick string, tank, damage, support int) int64 {
	e.t.Helper()
	e.n++
	id := e.n
	s := ts(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`, id, email(id), email(id), nick, s, s, s, s, s)
	rk := func(v int) any {
		if v == 0 {
			return nil
		}
		return v
	}
	e.exec(`INSERT INTO game_accounts (user_id, battletag, battletag_norm, rank_tank, rank_damage, rank_support, ranks_updated_at, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`, id, fmt.Sprintf("P%d#1000", id), fmt.Sprintf("p%d#1000", id), rk(tank), rk(damage), rk(support), s, s, s)
	e.exec(`INSERT INTO contacts (user_id, type, value, created_at, updated_at) VALUES (?, 'qq', ?, ?, ?)`, id, fmt.Sprintf("%d0000", id), s, s)
	return id
}

func (e *env) account(uid int64) int64 {
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT id FROM game_accounts WHERE user_id = ? ORDER BY id LIMIT 1`, uid).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return id
}

func (e *env) mgr() *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(e.now),
		Viewer: &app.Viewer{ID: 900, EmailVerified: true, Caps: map[app.Cap]struct{}{accounts.CapScrimsManage: {}, accounts.CapContactsView: {}}}}
}

func (e *env) ctx(id int64) *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(e.now), Viewer: &app.Viewer{ID: id, EmailVerified: true}}
}

func (e *env) anon() *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(e.now)}
}

type opt func(*opts)

type opts struct {
	format string
	status string
	starts time.Time
	closes *time.Time
	sjtu   bool
}

func withFormat(f string) opt    { return func(o *opts) { o.format = f } }
func withStatus(s string) opt    { return func(o *opts) { o.status = s } }
func withStart(t time.Time) opt  { return func(o *opts) { o.starts = t } }
func withCloses(t time.Time) opt { return func(o *opts) { o.closes = &t } }
func sjtuOnly() opt              { return func(o *opts) { o.sjtu = true } }

// scrim 直接建一场已发布的内战（默认 5v5 角色限定，十天后开始，没设报名截止）。
func (e *env) scrim(os ...opt) int64 {
	e.t.Helper()
	o := &opts{format: FormatRQ5, status: StatusPublished, starts: t0.Add(10 * 24 * time.Hour)}
	for _, f := range os {
		f(o)
	}
	var closes any
	if o.closes != nil {
		closes = ts(*o.closes)
	}
	e.exec(`INSERT INTO scrims (title, status, format, starts_at, signup_closes_at, sjtu_only, created_at, updated_at)
		VALUES ('周五内战', ?, ?, ?, ?, ?, ?, ?)`, o.status, o.format, ts(o.starts), closes, b2i(o.sjtu), ts(t0), ts(t0))
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT MAX(id) FROM scrims`).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return id
}

func (e *env) signup(sid, uid int64, roles ...string) {
	e.t.Helper()
	if _, err := e.svc.SignUp(e.ctx(uid), SignupInput{ScrimID: sid, GameAccountID: e.account(uid), Roles: roles}); err != nil {
		e.t.Fatalf("SignUp: %v", err)
	}
}

func (e *env) signupID(sid, uid int64) int64 {
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT id FROM scrim_signups WHERE scrim_id = ? AND user_id = ?`, sid, uid).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return id
}

func (e *env) mails() []string {
	e.t.Helper()
	rows, err := e.d.ReadPool().Query(`SELECT args FROM jobs WHERE kind = 'mail.letter' ORDER BY id`)
	if err != nil {
		e.t.Fatal(err)
	}
	defer rows.Close()
	var out []string
	for rows.Next() {
		var s string
		rows.Scan(&s)
		out = append(out, s)
	}
	return out
}

func (e *env) mailsTo(id int64) []string {
	var out []string
	for _, m := range e.mails() {
		if strings.Contains(m, `"address":"`+email(id)+`"`) {
			out = append(out, m)
		}
	}
	return out
}

func (e *env) clearMails() { e.exec(`DELETE FROM jobs`) }

func wantErr(t *testing.T, err error, status int, msg string) {
	t.Helper()
	var ae *api.Error
	if !errors.As(err, &ae) {
		t.Fatalf("要一个 api 错误（%d %q），拿到 %v", status, msg, err)
	}
	if ae.Status != status {
		t.Fatalf("状态码 %d（%s %v），要 %d", ae.Status, ae.Message, ae.Fields, status)
	}
	text := ae.Message
	for _, fs := range ae.Fields {
		text += strings.Join(fs, "|")
	}
	if msg != "" && !strings.Contains(text, msg) {
		t.Fatalf("文案 %q 里没有 %q", text, msg)
	}
}

func str(s string) *string    { return &s }
func rfc(t time.Time) *string { s := t.Format(time.RFC3339); return &s }
