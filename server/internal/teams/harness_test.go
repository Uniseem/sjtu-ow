package teams

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"image"
	"image/color"
	"image/png"
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
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

var t0 = time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)

type env struct {
	t   *testing.T
	d   *db.DB
	svc *Service
	med *media.Service
	n   int64
}

func newEnv(t *testing.T) *env {
	t.Helper()
	dir := t.TempDir()
	d, err := db.Open(filepath.Join(dir, "teams.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	med := media.NewService(d, filepath.Join(dir, "data"), filepath.Join(dir, "media"))
	svc := NewService(d, "https://sjtu.example", ratelimit.NewEnforcer(d, clock.Fixed(t0)), med)
	return &env{t: t, d: d, svc: svc, med: med}
}

func (e *env) exec(q string, args ...any) {
	e.t.Helper()
	err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, q, args...)
		return err
	})
	if err != nil {
		e.t.Fatalf("exec %q: %v", q, err)
	}
}

func (e *env) count(q string, args ...any) int {
	e.t.Helper()
	var n int
	if err := e.d.ReadPool().QueryRowContext(context.Background(), q, args...).Scan(&n); err != nil {
		e.t.Fatalf("count %q: %v", q, err)
	}
	return n
}

// user 建一个已验证邮箱、启用、绑了一个游戏 ID 的用户，返回编号。
func (e *env) user(nick string) int64 {
	e.t.Helper()
	e.n++
	id := e.n
	ts := db.FormatUTC(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at,
		agreed_cross_border_at, email_verified_at, is_active, created_at, updated_at)
		VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`,
		id, fmt.Sprintf("u%d@sjtu.example", id), fmt.Sprintf("u%d@sjtu.example", id), nick, ts, ts, ts, ts, ts)
	e.exec(`INSERT INTO game_accounts (user_id, battletag, battletag_norm, ranks_updated_at, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?)`, id, fmt.Sprintf("P%d#1000", id), fmt.Sprintf("p%d#1000", id), ts, ts, ts)
	return id
}

// bare 建一个没有游戏 ID 的用户。
func (e *env) bare(nick string) int64 {
	id := e.user(nick)
	e.exec(`DELETE FROM game_accounts WHERE user_id = ?`, id)
	return id
}

func (e *env) deactivate(id int64) {
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, id)
}

func (e *env) ctx(id int64, super bool) *app.Ctx {
	return &app.Ctx{
		Context: context.Background(),
		Viewer:  &app.Viewer{ID: id, EmailVerified: true, Superuser: super},
		Clock:   clock.Fixed(t0),
	}
}

func (e *env) anon() *app.Ctx {
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(t0)}
}

func (e *env) limits(members, captained int) {
	e.exec(`UPDATE site_settings SET team_max_members = ?, team_max_captained = ? WHERE id = 1`, members, captained)
}

// team 以 captain 的名义建一支队。
func (e *env) team(captain int64, name string) *Team {
	e.t.Helper()
	t, err := e.svc.CreateTeam(e.ctx(captain, false), CreateTeamInput{Name: name})
	if err != nil {
		e.t.Fatalf("CreateTeam(%s): %v", name, err)
	}
	return t
}

// join 让 user 申请加入并由队长通过。
func (e *env) join(t *Team, captain, user int64) {
	e.t.Helper()
	a, err := e.svc.Apply(e.ctx(user, false), ApplyInput{TeamID: t.ID, Roles: []string{"tank"}})
	if err != nil {
		e.t.Fatalf("Apply: %v", err)
	}
	if _, err := e.svc.Approve(e.ctx(captain, false), a.ID); err != nil {
		e.t.Fatalf("Approve: %v", err)
	}
}

func (e *env) role(teamID, userID int64) string {
	var role string
	err := e.d.ReadPool().QueryRowContext(context.Background(),
		`SELECT role FROM team_memberships WHERE team_id = ? AND user_id = ?`, teamID, userID).Scan(&role)
	if err != nil {
		return ""
	}
	return role
}

// mails 返回已入队的信的 JSON 参数，按先后。
func (e *env) mails() []string {
	e.t.Helper()
	rows, err := e.d.ReadPool().QueryContext(context.Background(), `SELECT args FROM jobs WHERE kind = 'mail.letter' ORDER BY id`)
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

func (e *env) mailsTo(addr string) []string {
	var out []string
	for _, m := range e.mails() {
		if strings.Contains(m, `"address":"`+addr+`"`) {
			out = append(out, m)
		}
	}
	return out
}

// resetCounters 清掉限流计数（固定时钟下一整天都在同一个时间片里）。
func (e *env) resetCounters() { e.exec(`DELETE FROM rate_counters`) }

func email(id int64) string { return fmt.Sprintf("u%d@sjtu.example", id) }

// wantErr 要求 err 是 *api.Error，状态码是 status，文案含 msg（msg 为空不查）。
func wantErr(t *testing.T, err error, status int, msg string) {
	t.Helper()
	var ae *api.Error
	if !errors.As(err, &ae) {
		t.Fatalf("要一个 api 错误（%d %q），拿到 %v", status, msg, err)
	}
	if ae.Status != status {
		t.Fatalf("状态码 %d（%s），要 %d；%v", ae.Status, ae.Message, status, err)
	}
	if msg != "" {
		text := ae.Message
		for _, fs := range ae.Fields {
			text += strings.Join(fs, "")
		}
		if !strings.Contains(text, msg) {
			t.Fatalf("文案 %q 里没有 %q", text, msg)
		}
	}
}

func wantField(t *testing.T, err error, field, msg string) {
	t.Helper()
	wantErr(t, err, http.StatusUnprocessableEntity, "")
	var ae *api.Error
	errors.As(err, &ae)
	got := strings.Join(ae.Fields[field], "")
	if !strings.Contains(got, msg) {
		t.Fatalf("字段 %s 的错误 %q 里没有 %q", field, got, msg)
	}
}

func pngBytes(t *testing.T) []byte {
	t.Helper()
	img := image.NewRGBA(image.Rect(0, 0, 64, 64))
	for x := 0; x < 64; x++ {
		for y := 0; y < 64; y++ {
			img.Set(x, y, color.RGBA{R: uint8(x * 4), G: uint8(y * 4), B: 90, A: 255})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

// sink 记下送审的东西。
type sink struct {
	got  []string
	fail bool
}

func (s *sink) Submit(_ context.Context, targetType string, targetID int64, field, text, url string, authorID int64) error {
	s.got = append(s.got, fmt.Sprintf("%s#%d:%s=%s", targetType, targetID, field, text))
	if s.fail {
		return errors.New("审核服务连不上")
	}
	return nil
}

// guard 是赛事报名检查的桩。
type guard struct {
	live    []string
	listing []ListedEntry
}

func (g *guard) LiveRegistrations(context.Context, db.DBTX, int64) ([]string, error) {
	return g.live, nil
}

func (g *guard) EntriesStillListing(context.Context, db.DBTX, int64, int64) ([]ListedEntry, error) {
	return g.listing, nil
}

var _ = accounts.RoleOrder

func itoa(n int64) string { return fmt.Sprintf("%d", n) }
