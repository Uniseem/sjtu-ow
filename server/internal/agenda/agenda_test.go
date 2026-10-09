package agenda

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	_ "modernc.org/sqlite"
)

var t0 = time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)

type testEnv struct {
	t   *testing.T
	d   *db.DB
	svc *Service
	n   int64
}

func newTestEnv(t *testing.T) *testEnv {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "agenda.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	svc := NewService(d, "https://sjtu.example", "test-signing-key-0123456789-abcdefghij")
	return &testEnv{t: t, d: d, svc: svc}
}

func (e *testEnv) exec(q string, args ...any) {
	e.t.Helper()
	if err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, q, args...)
		return err
	}); err != nil {
		e.t.Fatalf("exec %q: %v", q, err)
	}
}

func (e *testEnv) user(nick string) int64 {
	e.t.Helper()
	e.n++
	s := db.FormatUTC(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`,
		e.n, fmt.Sprintf("u%d@sjtu.example", e.n), fmt.Sprintf("u%d@sjtu.example", e.n), nick, s, s, s, s, s)
	return e.n
}

func (e *testEnv) ctxAt(id int64, now time.Time) *app.Ctx {
	v := &app.Viewer{ID: id, EmailVerified: true, Caps: map[app.Cap]struct{}{}}
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(now), Viewer: v}
}

func TestAgendaMineAndLimit(t *testing.T) {
	e := newTestEnv(t)
	u1 := e.user("选手A")
	now := t0
	sNow := db.FormatUTC(now)

	// 1. Scrim 1: 开始于 2 小时后，分了队：A队 · 坦克
	tPlus2 := db.FormatUTC(now.Add(2 * time.Hour))
	e.exec(`INSERT INTO scrims (id, title, format, starts_at, status, created_at, updated_at)
		VALUES (1, '周五内战', 'rq_5v5', ?, 'published', ?, ?)`, tPlus2, sNow, sNow)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, team, assigned_role, is_selected, created_at, updated_at)
		VALUES (1, ?, 1, 'a', 'tank', 1, ?, ?)`, u1, sNow, sNow)

	// 2. Scrim 2: 开始于 1 小时前（在 6 小时保护期内），未分队 -> "已报名"
	tMinus1 := db.FormatUTC(now.Add(-1 * time.Hour))
	e.exec(`INSERT INTO scrims (id, title, format, starts_at, status, created_at, updated_at)
		VALUES (2, '进行中内战', 'rq_5v5', ?, 'published', ?, ?)`, tMinus1, sNow, sNow)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_damage, team, assigned_role, is_selected, created_at, updated_at)
		VALUES (2, ?, 1, '', '', 0, ?, ?)`, u1, sNow, sNow)

	// 3. Scrim 3: 开始于 7 小时前（超过 6 小时保护期），应该被排除
	tMinus7 := db.FormatUTC(now.Add(-7 * time.Hour))
	e.exec(`INSERT INTO scrims (id, title, format, starts_at, status, created_at, updated_at)
		VALUES (3, '久远内战', 'rq_5v5', ?, 'published', ?, ?)`, tMinus7, sNow, sNow)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_damage, team, assigned_role, is_selected, created_at, updated_at)
		VALUES (3, ?, 1, 'a', 'damage', 1, ?, ?)`, u1, sNow, sNow)

	// 4. Tournament 1: 开始于 5 小时后，整队报名通过 -> "烈火战队 · 已通过"
	tPlus5 := db.FormatUTC(now.Add(5 * time.Hour))
	e.exec(`INSERT INTO tournaments (id, title, starts_at, status, created_at, updated_at)
		VALUES (10, '高校锦标赛', ?, 'published', ?, ?)`, tPlus5, sNow, sNow)
	e.exec(`INSERT INTO registrations (id, tournament_id, status, team_name, submitted_at, created_at, updated_at)
		VALUES (100, 10, 'approved', '烈火战队', ?, ?, ?)`, sNow, sNow, sNow)
	e.exec(`INSERT INTO registration_members (registration_id, tournament_id, user_id, nickname, battletag, is_active)
		VALUES (100, 10, ?, '选手A', 'BT#1', 1)`, u1)

	// 5. Tournament 2: 开始于 8 小时后，个人散人池 -> "等待编队"
	tPlus8 := db.FormatUTC(now.Add(8 * time.Hour))
	e.exec(`INSERT INTO tournaments (id, title, starts_at, status, created_at, updated_at)
		VALUES (20, '水友趣味赛', ?, 'published', ?, ?)`, tPlus8, sNow, sNow)
	e.exec(`INSERT INTO individual_signups (tournament_id, user_id, role_support, created_at, updated_at)
		VALUES (20, ?, 1, ?, ?)`, u1, sNow, sNow)

	// 6. Tournament 3: 无开始时间，个人散人池 -> "等待编队"，When == nil，排在最后
	e.exec(`INSERT INTO tournaments (id, title, starts_at, status, created_at, updated_at)
		VALUES (30, '待定友谊赛', NULL, 'published', ?, ?)`, sNow, sNow)
	e.exec(`INSERT INTO individual_signups (tournament_id, user_id, role_tank, created_at, updated_at)
		VALUES (30, ?, 1, ?, ?)`, u1, sNow, sNow)

	// 7. Tournament 4: 开始于过去（1小时前），已开始的赛事应该排除
	e.exec(`INSERT INTO tournaments (id, title, starts_at, status, created_at, updated_at)
		VALUES (40, '已过去赛事', ?, 'published', ?, ?)`, tMinus1, sNow, sNow)
	e.exec(`INSERT INTO individual_signups (tournament_id, user_id, role_tank, created_at, updated_at)
		VALUES (40, ?, 1, ?, ?)`, u1, sNow, sNow)

	// 8. 草稿状态的内战与赛事不应进入安排
	tPlus1 := db.FormatUTC(now.Add(1 * time.Hour))
	e.exec(`INSERT INTO scrims (id, title, starts_at, status, created_at, updated_at)
		VALUES (99, '草稿内战', ?, 'draft', ?, ?)`, tPlus1, sNow, sNow)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, created_at, updated_at)
		VALUES (99, ?, 1, ?, ?)`, u1, sNow, sNow)

	items, err := Items(context.Background(), e.d.ReadPool(), u1, now, 0)
	if err != nil {
		t.Fatalf("Items 出错: %v", err)
	}
	// 预期包含 5 项：
	// Scrim 2 (-1h), Scrim 1 (+2h), Tour 10 (+5h), Tour 20 (+8h), Tour 30 (nil)
	if len(items) != 5 {
		t.Fatalf("预期 5 项安排，实际 %d 项: %+v", len(items), items)
	}
	if items[0].Title != "进行中内战" || items[0].Note != "已报名" {
		t.Errorf("第 1 项不符: %+v", items[0])
	}
	if items[1].Title != "周五内战" || items[1].Note != "A 队 · 坦克" {
		t.Errorf("第 2 项不符: %+v", items[1])
	}
	if items[2].Title != "高校锦标赛" || items[2].Note != "烈火战队 · 已通过" {
		t.Errorf("第 3 项不符: %+v", items[2])
	}
	if items[3].Title != "水友趣味赛" || items[3].Note != "等待编队" {
		t.Errorf("第 4 项不符: %+v", items[3])
	}
	if items[4].Title != "待定友谊赛" || items[4].When != nil {
		t.Errorf("第 5 项不符: %+v", items[4])
	}

	// 测试 Mine 接口限制最多 4 条 (MaxItems)
	ctx := e.ctxAt(u1, now)
	mine, err := e.svc.Mine(ctx)
	if err != nil {
		t.Fatalf("Mine 出错: %v", err)
	}
	if len(mine) != 4 {
		t.Fatalf("Mine 限制 4 项，实际 %d", len(mine))
	}
	if mine[3].Title != "水友趣味赛" {
		t.Errorf("第 4 项应为水友趣味赛: %+v", mine[3])
	}

	// 未登录或被停用账号
	anonCtx := &app.Ctx{Context: context.Background()}
	if _, err := e.svc.Mine(anonCtx); err == nil {
		t.Fatal("未登录 Mine 应当返回未认证")
	}
	disabledCtx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: u1, Disabled: true}}
	if _, err := e.svc.Mine(disabledCtx); err == nil {
		t.Fatal("已停用 Mine 应当返回未认证")
	}
}

func TestCalendarTokenRenewAndServe(t *testing.T) {
	e := newTestEnv(t)
	u1 := e.user("选手B")
	ctx := e.ctxAt(u1, t0)

	addr, err := e.svc.MyAddress(ctx)
	if err != nil {
		t.Fatalf("MyAddress 失败: %v", err)
	}
	if !strings.HasPrefix(addr.URL, "https://sjtu.example/calendar/") || !strings.HasSuffix(addr.URL, ".ics") {
		t.Fatalf("订阅地址格式不符: %s", addr.URL)
	}
	if !strings.HasPrefix(addr.Webcal, "webcal://sjtu.example/calendar/") {
		t.Fatalf("Webcal 地址格式不符: %s", addr.Webcal)
	}

	oldToken := strings.TrimSuffix(strings.TrimPrefix(addr.URL, "https://sjtu.example/calendar/"), ".ics")
	id, nick, ok := e.svc.userFor(context.Background(), e.d.ReadPool(), oldToken)
	if !ok || id != u1 || nick != "选手B" {
		t.Fatalf("userFor 应当能解析旧令牌: %v, %d, %s", ok, id, nick)
	}

	// 换一个地址
	renewed, err := e.svc.Renew(ctx)
	if err != nil {
		t.Fatalf("Renew 失败: %v", err)
	}
	if renewed.URL == addr.URL {
		t.Fatal("Renew 后的地址应当变化")
	}
	newToken := strings.TrimSuffix(strings.TrimPrefix(renewed.URL, "https://sjtu.example/calendar/"), ".ics")

	// 旧令牌失效，新令牌有效
	_, _, okOld := e.svc.userFor(context.Background(), e.d.ReadPool(), oldToken)
	if okOld {
		t.Fatal("换地址后旧令牌应当失效")
	}
	idNew, _, okNew := e.svc.userFor(context.Background(), e.d.ReadPool(), newToken)
	if !okNew || idNew != u1 {
		t.Fatal("新令牌应当有效")
	}

	// 篡改令牌无效
	if _, _, ok := e.svc.userFor(context.Background(), e.d.ReadPool(), newToken+"bad"); ok {
		t.Fatal("篡改令牌不应有效")
	}

	// 停用账号令牌无效
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, u1)
	if _, _, ok := e.svc.userFor(context.Background(), e.d.ReadPool(), newToken); ok {
		t.Fatal("停用账号令牌不应有效")
	}
}

func TestCalendarICSGenerationAndFolding(t *testing.T) {
	e := newTestEnv(t)
	u1 := e.user("选手C")
	sNow := db.FormatUTC(t0)
	tPlus2 := db.FormatUTC(t0.Add(2 * time.Hour))

	e.exec(`INSERT INTO scrims (id, title, format, starts_at, status, created_at, updated_at)
		VALUES (1, '上海交通大学守望先锋社团2026年秋季超长标题内战第一轮选拔测试', 'rq_5v5', ?, 'published', ?, ?)`, tPlus2, sNow, sNow)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, team, assigned_role, is_selected, created_at, updated_at)
		VALUES (1, ?, 1, 'a', 'tank', 1, ?, ?)`, u1, sNow, sNow)

	ctx := e.ctxAt(u1, t0)
	addr, err := e.svc.MyAddress(ctx)
	if err != nil {
		t.Fatal(err)
	}

	rec := httptest.NewRecorder()
	file := strings.TrimPrefix(addr.URL, "https://sjtu.example/calendar/")
	req := httptest.NewRequest("GET", "/calendar/"+file, nil)
	req.SetPathValue("file", file)
	e.svc.Serve(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("Serve 状态码非 200: %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); ct != "text/calendar; charset=utf-8" {
		t.Errorf("Content-Type 不符: %s", ct)
	}
	if cc := rec.Header().Get("Cache-Control"); cc != "private, max-age=900" {
		t.Errorf("Cache-Control 不符: %s", cc)
	}
	if xr := rec.Header().Get("X-Robots-Tag"); xr != "noindex" {
		t.Errorf("X-Robots-Tag 不符: %s", xr)
	}

	body := rec.Body.String()
	if !strings.Contains(body, "BEGIN:VCALENDAR") || !strings.Contains(body, "END:VCALENDAR") {
		t.Fatal("缺少 VCALENDAR 标记")
	}
	if !strings.Contains(body, "BEGIN:VEVENT") || !strings.Contains(body, "END:VEVENT") {
		t.Fatal("缺少 VEVENT 标记")
	}
	if !strings.Contains(body, "SUMMARY:") {
		t.Fatal("缺少 SUMMARY")
	}

	// 验证 RFC 5545 换行折叠格式（不拆散字，以 \r\n 开头）
	lines := strings.Split(body, "\r\n")
	for _, l := range lines {
		if len(l) > 75 {
			t.Errorf("未折叠行超过 75 字节: %s (长 %d)", l, len(l))
		}
	}

	// 非 .ics 结尾 404
	badReq := httptest.NewRequest("GET", "/calendar/"+strings.TrimSuffix(file, ".ics"), nil)
	badReq.SetPathValue("file", strings.TrimSuffix(file, ".ics"))
	badRec := httptest.NewRecorder()
	e.svc.Serve(badRec, badReq)
	if badRec.Code != http.StatusNotFound {
		t.Errorf("非 .ics 后缀应当 404, 实际: %d", badRec.Code)
	}
}

func TestAgendaHTTPRoutes(t *testing.T) {
	e := newTestEnv(t)
	u1 := e.user("选手D")
	reg := &api.Registry{}
	NewModule(e.svc).Routes(reg)

	h := reg.Handler(func(r *http.Request) *app.Viewer {
		id, _ := strconv.ParseInt(r.Header.Get("X-Test-User"), 10, 64)
		if id == 0 {
			return nil
		}
		return &app.Viewer{ID: id, EmailVerified: true, Caps: map[app.Cap]struct{}{}}
	})

	// 1. GET /api/me/agenda 需登录
	rec1 := httptest.NewRecorder()
	req1 := httptest.NewRequest("GET", "/api/me/agenda", nil)
	h.ServeHTTP(rec1, req1)
	if rec1.Code != http.StatusUnauthorized {
		t.Errorf("未登录请求 agenda 应当 401: %d", rec1.Code)
	}

	rec2 := httptest.NewRecorder()
	req2 := httptest.NewRequest("GET", "/api/me/agenda", nil)
	req2.Header.Set("X-Test-User", strconv.FormatInt(u1, 10))
	h.ServeHTTP(rec2, req2)
	if rec2.Code != http.StatusOK {
		t.Errorf("已登录请求 agenda 应当 200: %d", rec2.Code)
	}

	// 2. GET /api/me/calendar
	rec3 := httptest.NewRecorder()
	req3 := httptest.NewRequest("GET", "/api/me/calendar", nil)
	req3.Header.Set("X-Test-User", strconv.FormatInt(u1, 10))
	h.ServeHTTP(rec3, req3)
	if rec3.Code != http.StatusOK {
		t.Errorf("GET calendar 应当 200: %d", rec3.Code)
	}

	// 3. POST /api/me/calendar/renew
	rec4 := httptest.NewRecorder()
	req4 := httptest.NewRequest("POST", "/api/me/calendar/renew", strings.NewReader("{}"))
	req4.Header.Set("Content-Type", "application/json")
	req4.Header.Set("X-Test-User", strconv.FormatInt(u1, 10))
	h.ServeHTTP(rec4, req4)
	if rec4.Code != http.StatusOK {
		t.Errorf("POST calendar/renew 应当 200: %d", rec4.Code)
	}
}
