package moderation

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	_ "modernc.org/sqlite"
)

var t0 = time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)

type env struct {
	t   *testing.T
	d   *db.DB
	svc *Service
	n   int64
}

func newEnv(t *testing.T) *env {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "mod.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return &env{t: t, d: d, svc: NewService(d, "https://sjtu.example")}
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

func (e *env) enable() {
	e.exec(`UPDATE site_settings SET moderation_enabled = 1, moderation_configured = 1 WHERE id = 1`)
}

func (e *env) user(nick string) int64 {
	e.t.Helper()
	e.n++
	s := db.FormatUTC(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`,
		e.n, fmt.Sprintf("u%d@sjtu.example", e.n), fmt.Sprintf("u%d@sjtu.example", e.n), nick, s, s, s, s, s)
	return e.n
}

func (e *env) reviewer() *app.Ctx {
	e.n++
	id := e.n + 1000
	s := db.FormatUTC(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (?, ?, ?, 'h', '内容编辑', 1, ?, ?, ?, 1, ?, ?)`,
		id, fmt.Sprintf("r%d@sjtu.example", id), fmt.Sprintf("r%d@sjtu.example", id), s, s, s, s, s)
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(t0),
		Viewer: &app.Viewer{ID: id, EmailVerified: true, Caps: map[app.Cap]struct{}{accounts.CapModerationReview: {}}}}
}

func (e *env) submit(tt string, id int64, field, text string, author int64) {
	e.t.Helper()
	if err := e.svc.Submit(context.Background(), tt, id, field, text, "/x/", author); err != nil {
		e.t.Fatal(err)
	}
}

func wantErr(t *testing.T, err error, status int, msg string) {
	t.Helper()
	var ae *api.Error
	if !errors.As(err, &ae) || ae.Status != status {
		t.Fatalf("要 %d 的 api 错误，拿到 %v", status, err)
	}
	text := ae.Message
	for _, fs := range ae.Fields {
		text += strings.Join(fs, "|")
	}
	if msg != "" && !strings.Contains(text, msg) {
		t.Fatalf("文案 %q 里没有 %q", text, msg)
	}
}

// 契约 R185：开关开着且配置好了才送审；文本为空也不送
func TestSubmitNeedsEnabledAndConfigured(t *testing.T) {
	e := newEnv(t)
	u := e.user("甲")
	e.submit(TargetNickname, u, "nickname", "甲甲", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items`) != 0 {
		t.Fatal("默认不送审")
	}
	e.exec(`UPDATE site_settings SET moderation_enabled = 1 WHERE id = 1`)
	e.submit(TargetNickname, u, "nickname", "甲甲", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items`) != 0 {
		t.Fatal("开了但没配好，不送审（否则攒一堆永远等不到结论的记录）")
	}
	e.exec(`UPDATE site_settings SET moderation_enabled = 0, moderation_configured = 1 WHERE id = 1`)
	e.submit(TargetNickname, u, "nickname", "甲甲", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items`) != 0 {
		t.Fatal("配好了但没开，不送审")
	}
	e.enable()
	e.submit(TargetNickname, u, "nickname", "   ", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items`) != 0 {
		t.Fatal("空文本不送审")
	}
	e.submit(TargetNickname, u, "nickname", " 甲甲 ", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE author_id = ? AND risk = 'unknown' AND status = 'pending' AND checked_at IS NULL`, u) != 1 {
		t.Fatal("送审成功：待巡查、无法判定、作者记上")
	}
}

// 契约 R188：短文只存摘录；长文整篇存 full_text 待读，摘录 2000 字
func TestExcerptAndFullText(t *testing.T) {
	e := newEnv(t)
	e.enable()
	u := e.user("甲")
	e.submit(TargetComment, 1, "body", "一条评论", u)
	long := strings.Repeat("长", 5000)
	e.submit(TargetArticle, 2, "content", long, u)
	var full, excerpt string
	e.d.ReadPool().QueryRow(`SELECT full_text, excerpt FROM moderation_items WHERE target_type = 'comment'`).Scan(&full, &excerpt)
	if full != "" || excerpt != "一条评论" {
		t.Fatalf("短文：full=%q excerpt=%q", full, excerpt)
	}
	e.d.ReadPool().QueryRow(`SELECT full_text, excerpt FROM moderation_items WHERE target_type = 'article'`).Scan(&full, &excerpt)
	if len([]rune(full)) != 5000 || len([]rune(excerpt)) != ExcerptChars {
		t.Fatalf("长文：full=%d excerpt=%d", len([]rune(full)), len([]rune(excerpt)))
	}
}

// 契约 R187：同一处没读过的旧文本被最新文本替换（自动保存的半成品不逐版排队）；文本相同则复用现有记录
func TestUnreadTextIsReplaced(t *testing.T) {
	e := newEnv(t)
	e.enable()
	u := e.user("甲")
	for _, step := range []string{"今", "今晚", "今晚八点", "今晚八点内战"} {
		e.submit(TargetTeamDescription, 7, "description", step, u)
	}
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 7`) != 1 {
		t.Fatal("自动保存的半成品应被替换成只剩一条")
	}
	var excerpt string
	e.d.ReadPool().QueryRow(`SELECT excerpt FROM moderation_items WHERE target_id = 7`).Scan(&excerpt)
	if excerpt != "今晚八点内战" {
		t.Fatalf("留下的是最新文本：%q", excerpt)
	}
	// 相同文本再送：不新增
	e.submit(TargetTeamDescription, 7, "description", "今晚八点内战", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 7`) != 1 {
		t.Fatal("文本相同应复用")
	}
	// 已经被读过（checked_at 有值）的旧文本不被替换，新文本另起一条
	e.exec(`UPDATE moderation_items SET checked_at = ?, risk = 'low' WHERE target_id = 7`, db.FormatUTC(t0))
	e.submit(TargetTeamDescription, 7, "description", "改成了新的内容", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 7`) != 2 {
		t.Fatal("读过的旧记录要保留，新文本另起一条")
	}
	// 同一处有一条读过的旧记录和一条没读过的：再送没读过的那份文本，读过的旧记录不能被清掉
	e.submit(TargetTeamDescription, 8, "description", "已经读过的老文本", u)
	e.exec(`UPDATE moderation_items SET checked_at = ?, risk = 'low' WHERE target_id = 8`, db.FormatUTC(t0))
	e.submit(TargetTeamDescription, 8, "description", "新写的还没读", u)
	e.submit(TargetTeamDescription, 8, "description", "新写的还没读", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 8`) != 2 || e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 8 AND checked_at IS NOT NULL`) != 1 {
		t.Fatal("读过的旧记录要保留，只替换没读过的")
	}
	// 不同的位置互不影响
	e.submit(TargetTeamName, 7, "name", "星队", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 7`) != 3 {
		t.Fatal("不同字段各一条")
	}
	// 替换时重置失败计数
	e.submit(TargetMotto, 9, "motto", "第一版", u)
	e.exec(`UPDATE moderation_items SET attempts = 2, last_error = '超时', failed_at = ? WHERE target_id = 9`, db.FormatUTC(t0))
	e.submit(TargetMotto, 9, "motto", "第二版", u)
	if e.count(`SELECT COUNT(*) FROM moderation_items WHERE target_id = 9 AND attempts = 0 AND last_error = '' AND failed_at IS NULL`) != 1 {
		t.Fatal("文本换了，失败计数清零")
	}
}

func (e *env) seed(tt string, id int64, risk, status string, checked bool, author int64) int64 {
	e.t.Helper()
	var chk any
	if checked {
		chk = db.FormatUTC(t0)
	}
	var au any
	if author > 0 {
		au = author
	}
	e.n++
	e.exec(`INSERT INTO moderation_items (target_type, target_id, field, url, author_id, excerpt, text_hash, risk, status, checked_at, created_at)
		VALUES (?, ?, 'f', '/x/', ?, ?, ?, ?, ?, ?, ?)`, tt, id, au, "内容"+strconv.FormatInt(e.n, 10), "h"+strconv.FormatInt(e.n, 10), risk, status, chk, db.FormatUTC(t0))
	var out int64
	e.d.ReadPool().QueryRow(`SELECT MAX(id) FROM moderation_items`).Scan(&out)
	return out
}

// 契约 R202：只有有复核能力的人（内容编辑）能看和处置；列表不含「无风险」，待复核只含 AI 已经看过的
func TestReviewerGateAndList(t *testing.T) {
	e := newEnv(t)
	e.enable()
	rev := e.reviewer()
	u := e.user("甲")
	a := e.seed(TargetComment, 1, "high", StatusPending, true, u)
	e.seed(TargetComment, 2, "none", StatusPending, true, u)     // 无风险：不进列表
	e.seed(TargetComment, 3, "unknown", StatusPending, false, u) // AI 还没看：不进待复核
	e.seed(TargetNickname, 4, "low", StatusHandled, true, u)

	_, err := e.svc.List(&app.Ctx{Context: context.Background(), Clock: clock.Fixed(t0), Viewer: &app.Viewer{ID: u, EmailVerified: true}}, ListInput{})
	wantErr(t, err, http.StatusForbidden, "")
	_, err = e.svc.List(&app.Ctx{Context: context.Background(), Clock: clock.Fixed(t0)}, ListInput{})
	wantErr(t, err, http.StatusUnauthorized, "")

	res, err := e.svc.List(rev, ListInput{})
	if err != nil || res.Total != 1 || res.Items[0].ID != a || !res.Items[0].NeedsReview() {
		t.Fatalf("默认只列待复核、有风险、AI 看过的：%+v %v", res, err)
	}
	if res.Waiting != 1 || res.Failed != 0 || !res.Enabled {
		t.Fatalf("AI 还没读的 1 条：%+v", res)
	}
	handled, _ := e.svc.List(rev, ListInput{Status: StatusHandled})
	if handled.Total != 1 || handled.Items[0].TargetType != TargetNickname {
		t.Fatalf("按状态筛：%+v", handled)
	}
	if r, _ := e.svc.List(rev, ListInput{Risk: "low"}); r.Total != 0 {
		t.Fatalf("按风险筛，待复核里没有 low：%d", r.Total)
	}
	if r, _ := e.svc.List(rev, ListInput{TargetType: TargetComment}); r.Total != 1 {
		t.Fatalf("按类型筛：%d", r.Total)
	}
	// 没看成的：计入待办（规则 205）
	e.exec(`UPDATE moderation_items SET failed_at = ?, last_error = '接口超时' WHERE target_id = 3`, db.FormatUTC(t0))
	res, _ = e.svc.List(rev, ListInput{})
	if res.Failed != 1 || res.LastError != "接口超时" {
		t.Fatalf("没看成的：%+v", res)
	}
}

// 契约 R202：人工处置写复核人、时间、说明，并进操作记录
func TestHandle(t *testing.T) {
	e := newEnv(t)
	rev := e.reviewer()
	id := e.seed(TargetComment, 1, "medium", StatusPending, true, 0)
	_, err := e.svc.Handle(rev, id, "banana", "")
	wantErr(t, err, http.StatusUnprocessableEntity, "处置方式")
	_, err = e.svc.Handle(rev, id, "ok", strings.Repeat("长", 301))
	wantErr(t, err, http.StatusUnprocessableEntity, "最多 300")
	it, err := e.svc.Handle(rev, id, "ignored", "玩笑话")
	if err != nil || it.Status != StatusIgnored || it.ReviewedBy == nil || *it.ReviewedBy != rev.Viewer.ID || it.HandlingNote != "玩笑话" || it.ReviewedAt == nil {
		t.Fatalf("处置：%+v %v", it, err)
	}
	if _, err := e.svc.Handle(rev, id, "handled", ""); err != nil {
		t.Fatal(err)
	}
	d, err := e.svc.Get(rev, id)
	if err != nil || len(d.History) != 2 || d.History[0].Action != "moderation.handle" {
		t.Fatalf("每次处置都进操作记录，不互相覆盖：%+v %v", d, err)
	}
	_, err = e.svc.Handle(rev, 99999, "ok", "")
	wantErr(t, err, http.StatusNotFound, "")
}

// 契约 R203：复核页唯一的直接处置是发信要求作者修改——说明必填 ≤500 字；作者缺失/停用/没邮箱不能发
func TestAskAuthor(t *testing.T) {
	e := newEnv(t)
	rev := e.reviewer()
	author := e.user("作者")
	id := e.seed(TargetTeamName, 3, "high", StatusPending, true, author)

	_, err := e.svc.AskAuthor(rev, id, "  ")
	wantErr(t, err, http.StatusUnprocessableEntity, "写一段说明")
	_, err = e.svc.AskAuthor(rev, id, strings.Repeat("长", 501))
	wantErr(t, err, http.StatusUnprocessableEntity, "最多 500")

	nobody := e.seed(TargetComment, 5, "high", StatusPending, true, 0)
	_, err = e.svc.AskAuthor(rev, nobody, "请修改")
	wantErr(t, err, http.StatusConflict, "没有作者")
	gone := e.user("停用")
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, gone)
	_, err = e.svc.AskAuthor(rev, e.seed(TargetComment, 6, "high", StatusPending, true, gone), "请修改")
	wantErr(t, err, http.StatusConflict, "已停用")
	anon := e.user("已注销")
	e.exec(`UPDATE users SET email = 'deleted-1@deleted.invalid' WHERE id = ?`, anon)
	_, err = e.svc.AskAuthor(rev, e.seed(TargetComment, 7, "high", StatusPending, true, anon), "请修改")
	wantErr(t, err, http.StatusConflict, "没有邮箱")
	if e.count(`SELECT COUNT(*) FROM jobs WHERE kind = 'mail.letter'`) != 0 {
		t.Fatal("不能发信的情况下一封都不该发")
	}

	it, err := e.svc.AskAuthor(rev, id, "队名里有不合适的词，请改掉")
	if err != nil || it.Status != StatusHandled || it.HandlingNote != "已发信要求作者修改" {
		t.Fatalf("发信：%+v %v", it, err)
	}
	var args string
	e.d.ReadPool().QueryRow(`SELECT args FROM jobs WHERE kind = 'mail.letter'`).Scan(&args)
	if !strings.Contains(args, "请修改你的队名") || !strings.Contains(args, "队名里有不合适的词") || !strings.Contains(args, "/teams/3/manage/") ||
		!strings.Contains(args, fmt.Sprintf("u%d@sjtu.example", author)) {
		t.Fatalf("信：%s", args)
	}
	if e.count(`SELECT COUNT(*) FROM held_letters`) != 0 {
		t.Fatal("复核页的动作是直接发，不过待发信确认")
	}
	// 第二次：信里说明之前已经发过一次
	if _, err := e.svc.AskAuthor(rev, id, "还是不行"); err != nil {
		t.Fatal(err)
	}
	e.d.ReadPool().QueryRow(`SELECT args FROM jobs WHERE kind = 'mail.letter' ORDER BY id DESC LIMIT 1`).Scan(&args)
	if !strings.Contains(args, "已经发过 1 次修改提醒") {
		t.Fatalf("第二封信要说明之前发过几次：%s", args)
	}
	// 有别的可疑内容的作者
	e.seed(TargetNickname, 4, "low", StatusPending, true, author)
	d, _ := e.svc.Get(rev, id)
	if d.AuthorFlags != 1 {
		t.Fatalf("作者的别的可疑内容：%d", d.AuthorFlags)
	}
}

// 契约 R204、R230：已处理的审核记录保留 180 天后清理；没人处理过的永久保留
func TestCleanup(t *testing.T) {
	e := newEnv(t)
	old := db.FormatUTC(t0.Add(-181 * 24 * time.Hour))
	recent := db.FormatUTC(t0.Add(-179 * 24 * time.Hour))
	oldHandled := e.seed(TargetComment, 1, "low", StatusHandled, true, 0)
	e.exec(`UPDATE moderation_items SET reviewed_at = ? WHERE id = ?`, old, oldHandled)
	recentHandled := e.seed(TargetComment, 2, "low", StatusOK, true, 0)
	e.exec(`UPDATE moderation_items SET reviewed_at = ? WHERE id = ?`, recent, recentHandled)
	legacy := e.seed(TargetComment, 3, "low", StatusIgnored, true, 0) // 没有复核时间：看创建时间
	e.exec(`UPDATE moderation_items SET created_at = ? WHERE id = ?`, old, legacy)
	pending := e.seed(TargetComment, 4, "high", StatusPending, true, 0)
	e.exec(`UPDATE moderation_items SET created_at = ? WHERE id = ?`, old, pending)

	n, err := e.svc.Cleanup(context.Background(), t0)
	if err != nil || n != 2 {
		t.Fatalf("清掉 2 条：%d %v", n, err)
	}
	for id, want := range map[int64]int{oldHandled: 0, legacy: 0, recentHandled: 1, pending: 1} {
		if got := e.count(`SELECT COUNT(*) FROM moderation_items WHERE id = ?`, id); got != want {
			t.Fatalf("记录 %d 应剩 %d 条，剩 %d", id, want, got)
		}
	}
}

// 导入器：编号沿用、可重复跑、作者不存在的置空
func TestImportLegacyModeration(t *testing.T) {
	e := newEnv(t)
	u := e.user("作者")
	legacy, err := sql.Open("sqlite", "file:"+filepath.Join(t.TempDir(), "legacy.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, s := range []string{
		`CREATE TABLE moderation_moderationitem (id INTEGER, target_type TEXT, target_id INTEGER, field TEXT, url TEXT, author_id INTEGER,
			excerpt TEXT, full_text TEXT, text_hash TEXT, risk TEXT, categories TEXT, reason TEXT, quote TEXT, model TEXT, input_tokens INTEGER,
			output_tokens INTEGER, status TEXT, reviewed_by_id INTEGER, reviewed_at TEXT, handling_note TEXT, checked_at TEXT, notified_at TEXT,
			attempts INTEGER, last_error TEXT, failed_at TEXT, created_at TEXT)`,
		`INSERT INTO moderation_moderationitem VALUES (12, 'comment', 5, 'body', '/news/1/', ` + strconv.FormatInt(u, 10) + `, '摘录', '', 'abc', 'medium',
			'["attack","other"]', '理由', '引用', 'deepseek', 10, 5, 'handled', 999, '2026-06-02 00:00:00', '已发信要求作者修改', '2026-06-01 00:00:00',
			NULL, 0, '', NULL, '2026-06-01 00:00:00')`,
	} {
		if _, err := legacy.Exec(s); err != nil {
			t.Fatalf("%s: %v", s, err)
		}
	}
	for i := 0; i < 2; i++ {
		if err := ImportLegacyModeration(context.Background(), e.d, legacy); err != nil {
			t.Fatalf("第 %d 次导入：%v", i+1, err)
		}
	}
	it, err := getItem(context.Background(), e.d.ReadPool(), 12)
	if err != nil || it == nil || it.Risk != "medium" || len(it.Categories) != 2 || it.ReviewedBy != nil || it.AuthorID == nil || it.Status != StatusHandled {
		t.Fatalf("导入：%+v %v", it, err)
	}
	if it.ReviewedAt == nil || it.ReviewedAt.Format("2006-01-02T15:04:05Z") != "2026-06-02T00:00:00Z" {
		t.Fatalf("时间按 UTC 沿用：%v", it.ReviewedAt)
	}
}
