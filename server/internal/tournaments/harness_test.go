package tournaments

import (
	"context"
	"errors"
	"fmt"
	"net/http"
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
	d, err := db.Open(filepath.Join(t.TempDir(), "tournaments.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	e := &env{t: t, d: d, svc: NewService(d, "https://sjtu.example"), now: t0, denied: map[int64]bool{}}
	// 900 号是赛事管理员（mgr()），库里要有这个人，created_by 和日志的外键才成立
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (900, 'mgr@sjtu.example', 'mgr@sjtu.example', 'h', '赛事管理员', 1, ?, ?, ?, 1, ?, ?)`,
		ts(t0), ts(t0), ts(t0), ts(t0), ts(t0))
	e.svc.SetViewerBuilder(func(_ context.Context, id int64) (*app.Viewer, error) {
		v := &app.Viewer{ID: id, EmailVerified: true}
		if e.denied[id] {
			v.FeatureDenied = map[app.Feature]struct{}{accounts.FeatureTournamentRegister: {}}
		}
		return v, nil
	})
	return e
}

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

func ts(t time.Time) string { return db.FormatUTC(t) }

// user 建一个资料完整（有游戏 ID 和联系方式）、邮箱已验证的交大用户。
func (e *env) user(nick string) int64 {
	e.t.Helper()
	e.n++
	id := e.n
	s := ts(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at,
		agreed_cross_border_at, email_verified_at, is_active, created_at, updated_at)
		VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`, id, email(id), email(id), nick, s, s, s, s, s)
	e.exec(`INSERT INTO game_accounts (user_id, battletag, battletag_norm, rank_tank, rank_damage, rank_support, ranks_updated_at, created_at, updated_at)
		VALUES (?, ?, ?, 2000, 3000, NULL, ?, ?, ?)`, id, fmt.Sprintf("P%d#1000", id), fmt.Sprintf("p%d#1000", id), s, s, s)
	e.exec(`INSERT INTO contacts (user_id, type, value, created_at, updated_at) VALUES (?, 'qq', '12345678', ?, ?)`, id, s, s)
	return id
}

func email(id int64) string { return fmt.Sprintf("u%d@sjtu.example", id) }

func (e *env) outsider(nick string) int64 {
	id := e.user(nick)
	e.exec(`UPDATE users SET is_sjtu = 0 WHERE id = ?`, id)
	return id
}

func (e *env) mgr() *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(e.now),
		Viewer: &app.Viewer{ID: 900, EmailVerified: true, Caps: map[app.Cap]struct{}{accounts.CapTournamentsManage: {}}}}
}

func (e *env) ctx(id int64) *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(e.now), Viewer: &app.Viewer{ID: id, EmailVerified: true}}
}

func (e *env) anon() *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(e.now)}
}

// team 建一支战队（第一个是队长），返回编号。
func (e *env) team(name string, members ...int64) int64 {
	e.t.Helper()
	s := ts(t0)
	e.exec(`INSERT INTO teams (name, created_at, updated_at) VALUES (?, ?, ?)`, name, s, s)
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT id FROM teams WHERE name = ?`, name).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	for i, m := range members {
		role := "member"
		if i == 0 {
			role = "captain"
		}
		e.exec(`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)`, id, m, role, s)
	}
	return id
}

type opt func(*tourOpts)

type tourOpts struct {
	mode    string
	status  string
	min     int
	max     int
	sjtu    bool
	auto    bool
	opens   time.Time
	closes  time.Time
	starts  *time.Time
	contact string
}

func withMode(m string) opt         { return func(o *tourOpts) { o.mode = m } }
func withSjtuOnly() opt             { return func(o *tourOpts) { o.sjtu = true } }
func withAuto() opt                 { return func(o *tourOpts) { o.auto = true } }
func withRoster(min, max int) opt   { return func(o *tourOpts) { o.min, o.max = min, max } }
func withStatus(s string) opt       { return func(o *tourOpts) { o.status = s } }
func withContact(c string) opt      { return func(o *tourOpts) { o.contact = c } }
func withStart(t time.Time) opt     { return func(o *tourOpts) { o.starts = &t } }
func withWindow(a, b time.Time) opt { return func(o *tourOpts) { o.opens, o.closes = a, b } }

// tour 直接建一项已发布的赛事（默认整队、2–3 人、报名窗口包住现在、十天后开赛）。
func (e *env) tour(opts ...opt) int64 {
	e.t.Helper()
	start := t0.Add(10 * 24 * time.Hour)
	o := &tourOpts{mode: ModeTeam, status: StatusPublished, min: 2, max: 3, opens: t0.Add(-24 * time.Hour), closes: t0.Add(7 * 24 * time.Hour), starts: &start}
	for _, f := range opts {
		f(o)
	}
	var starts any
	if o.starts != nil {
		starts = ts(*o.starts)
	}
	e.exec(`INSERT INTO tournaments (title, summary, status, registration_mode, roster_min, roster_max, sjtu_only, auto_approve,
		registration_opens_at, registration_closes_at, starts_at, participant_contact, published_at, created_at, updated_at)
		VALUES ('春季赛', '简介', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		o.status, o.mode, o.min, o.max, b2i(o.sjtu), b2i(o.auto), ts(o.opens), ts(o.closes), starts, o.contact, ts(t0), ts(t0), ts(t0))
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT MAX(id) FROM tournaments`).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return id
}

// register 队长提交整队报名，返回报名。
func (e *env) register(tid, teamID, captain int64) *Registration {
	e.t.Helper()
	r, err := e.svc.Submit(e.ctx(captain), SubmitInput{TournamentID: tid, TeamID: teamID})
	if err != nil {
		e.t.Fatalf("Submit: %v", err)
	}
	return r
}

func (e *env) regStatus(id int64) string {
	e.t.Helper()
	var s string
	if err := e.d.ReadPool().QueryRow(`SELECT status FROM registrations WHERE id = ?`, id).Scan(&s); err != nil {
		e.t.Fatal(err)
	}
	return s
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
		if err := rows.Scan(&s); err != nil {
			e.t.Fatal(err)
		}
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

func str(s string) *string { return &s }
func num(n int) *int       { return &n }
func flag(b bool) *bool    { return &b }

func rfc(t time.Time) *string { s := t.Format(time.RFC3339); return &s }

var _ = http.StatusOK

// sink 记下送审的东西。
type sink struct{ got []string }

func (s *sink) Submit(_ context.Context, targetType string, targetID int64, field, text, url string, authorID int64) error {
	s.got = append(s.got, fmt.Sprintf("%s#%d:%s", targetType, targetID, field))
	return nil
}
