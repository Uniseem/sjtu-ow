package notify

import (
	"context"
	"encoding/json"
	"errors"
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
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
	_ "modernc.org/sqlite"
)

var t0 = time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)

const capAnnounce app.Cap = "test.announce"

type env struct {
	t       *testing.T
	d       *db.DB
	svc     *Service
	n       int64
	subject *Subject // 假种类现在读到的对象；nil 就是「不存在」
	ready   bool
}

func newEnv(t *testing.T) *env {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "notify.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	e := &env{t: t, d: d, ready: true, subject: &Subject{Title: "秋季招新", Live: true}}
	e.svc = NewService(d, "https://sjtu.example", "test-signing-key-0123456789-abcdefghij", func() bool { return e.ready })
	e.svc.Register(Kind{
		Key:  KindArticle,
		Noun: "这篇文章",
		CanSend: func(v *app.Viewer) bool {
			return v != nil && v.HasCap(capAnnounce)
		},
		Load: func(context.Context, db.DBTX, int64) (*Subject, error) { return e.subject, nil },
		Letter: func(_ context.Context, _ db.DBTX, id int64, unsub string, _ time.Time) (mail.Letter, error) {
			return mail.Letter{
				Subject: "公告：" + e.subject.Title, Lead: "社团发布了一篇公告。",
				Action: []string{"阅读全文", fmt.Sprintf("https://sjtu.example/news/%d/", id)}, Unsubscribe: unsub,
			}, nil
		},
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
		e.t.Fatalf("count %q: %v", q, err)
	}
	return n
}

// user 建一个启用、邮箱验证过、开着活动通知的交大用户。
func (e *env) user(nick string) int64 {
	e.t.Helper()
	e.n++
	s := db.FormatUTC(t0)
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at,
		email_verified_at, is_active, created_at, updated_at) VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`,
		e.n, fmt.Sprintf("u%d@sjtu.example", e.n), fmt.Sprintf("u%d@sjtu.example", e.n), nick, s, s, s, s, s)
	return e.n
}

func (e *env) ctxAt(id int64, now time.Time, caps ...app.Cap) *app.Ctx {
	v := &app.Viewer{ID: id, EmailVerified: true, Caps: map[app.Cap]struct{}{}}
	for _, c := range caps {
		v.Caps[c] = struct{}{}
	}
	return &app.Ctx{Context: context.Background(), Clock: clock.Fixed(now), Viewer: v}
}

func (e *env) editor() *app.Ctx { return e.ctxAt(e.user("编辑"), t0, capAnnounce) }

// letterJobs 读出已经排进邮件车道的信：收信地址 → 信。
func (e *env) letterJobs() map[string]mail.Letter {
	e.t.Helper()
	rows, err := e.d.ReadPool().Query(`SELECT args FROM jobs WHERE kind = ? ORDER BY id`, outbox.KindLetter)
	if err != nil {
		e.t.Fatal(err)
	}
	defer rows.Close()
	out := map[string]mail.Letter{}
	for rows.Next() {
		var raw string
		if err := rows.Scan(&raw); err != nil {
			e.t.Fatal(err)
		}
		var p struct {
			Letter mail.Letter `json:"letter"`
			To     mail.Person `json:"to"`
		}
		if err := json.Unmarshal([]byte(raw), &p); err != nil {
			e.t.Fatal(err)
		}
		out[p.To.Address] = p.Letter
	}
	return out
}

func (e *env) deliver(broadcastID int64) {
	e.t.Helper()
	args, _ := json.Marshal(map[string]int64{"broadcast_id": broadcastID})
	if err := e.svc.Deliver()(context.Background(), e.d, jobs.Job{Kind: JobDeliver, Args: string(args)}); err != nil {
		e.t.Fatalf("Deliver: %v", err)
	}
}

func wantErr(t *testing.T, err error, status int, contains string) {
	t.Helper()
	var ae *api.Error
	if !errors.As(err, &ae) {
		t.Fatalf("要 %d 的 api 错误，拿到 %v", status, err)
	}
	if ae.Status != status || !strings.Contains(ae.Message, contains) {
		t.Fatalf("要 %d「%s」，拿到 %d「%s」", status, contains, ae.Status, ae.Message)
	}
}

// hold 模拟一次登录用户的写动作：在一个批次里发两封不同的信，第一封发给两个人。
func (e *env) hold(actor int64, to1, to2 []mail.Person, now time.Time) *app.LetterBatch {
	e.t.Helper()
	batch := outbox.Open(actor)
	err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		if _, err := outbox.Send(ctx, tx, batch, "https://sjtu.example", mail.Letter{Subject: "申请通过", Lead: "a"}, to1, now); err != nil {
			return err
		}
		_, err := outbox.Send(ctx, tx, batch, "https://sjtu.example", mail.Letter{Subject: "申请被拒", Lead: "b"}, to2, now)
		return err
	})
	if err != nil {
		e.t.Fatal(err)
	}
	return batch
}

// 契约 R206–R208：待发信确认、代发与清理
func TestHeldDecideSendsOnlyTheTickedOnesAndOnlyOnce(t *testing.T) {
	e := newEnv(t)
	actor := e.user("队长")
	other := e.user("路人")
	a := []mail.Person{{Address: "a@x.example", Name: "甲"}, {Address: "b@x.example", Name: "乙"}}
	b := []mail.Person{{Address: "c@x.example", Name: "丙"}}
	batch := e.hold(actor, a, b, t0)
	if batch.Held != 2 {
		t.Fatalf("两封不同的信该冻住两封，批次里记了 %d", batch.Held)
	}
	if got := len(e.letterJobs()); got != 0 {
		t.Fatalf("冻住的信不该进邮件车道，现在有 %d 封", got)
	}

	// 别人看不到这批；不存在的批次也是 404
	if _, err := e.svc.Held(e.ctxAt(other, t0), batch.Key); err == nil {
		t.Fatal("别人的批次该是 404")
	} else {
		wantErr(t, err, 404, "")
	}
	if _, err := e.svc.Held(e.ctxAt(actor, t0), "no-such"); err == nil {
		t.Fatal("不存在的批次该是 404")
	}
	if _, err := e.svc.DecideHeld(e.ctxAt(other, t0), batch.Key, nil, false); err == nil {
		t.Fatal("别人不能处理这批")
	}

	view, err := e.svc.Held(e.ctxAt(actor, t0), batch.Key)
	if err != nil {
		t.Fatal(err)
	}
	if view.State != "waiting" || len(view.Letters) != 2 {
		t.Fatalf("该有两封等着：%+v", view)
	}
	if view.Letters[0].Subject != "申请通过" || view.Letters[0].Count != 2 || view.Letters[0].Who != "甲、乙" {
		t.Fatalf("第一封：%+v", view.Letters[0])
	}

	// 勾第一封：只发它，第二封丢掉
	res, err := e.svc.DecideHeld(e.ctxAt(actor, t0), batch.Key, []int64{view.Letters[0].ID}, false)
	if err != nil {
		t.Fatal(err)
	}
	if res.Letters != 1 || res.People != 2 {
		t.Fatalf("该发 1 封给 2 人：%+v", res)
	}
	sent := e.letterJobs()
	if len(sent) != 2 || sent["a@x.example"].Subject != "申请通过" || sent["c@x.example"].Subject != "" {
		t.Fatalf("只该发第一封：%v", sent)
	}
	// 再点一次：什么都不发
	res, err = e.svc.DecideHeld(e.ctxAt(actor, t0), batch.Key, []int64{view.Letters[0].ID, view.Letters[1].ID}, false)
	if err != nil {
		t.Fatal(err)
	}
	if res.Letters != 0 || len(e.letterJobs()) != 2 {
		t.Fatalf("第二次点不该再发：%+v / %d", res, len(e.letterJobs()))
	}
	again, _ := e.svc.Held(e.ctxAt(actor, t0), batch.Key)
	if again.State != "done" {
		t.Fatalf("处理过的批次该是 done：%+v", again)
	}
}

func TestHeldSkipSendsNothing(t *testing.T) {
	e := newEnv(t)
	actor := e.user("队长")
	batch := e.hold(actor, []mail.Person{{Address: "a@x.example", Name: "甲"}}, []mail.Person{{Address: "b@x.example", Name: "乙"}}, t0)
	view, _ := e.svc.Held(e.ctxAt(actor, t0), batch.Key)
	ids := []int64{view.Letters[0].ID, view.Letters[1].ID}
	res, err := e.svc.DecideHeld(e.ctxAt(actor, t0), batch.Key, ids, true)
	if err != nil {
		t.Fatal(err)
	}
	if res.Letters != 0 || len(e.letterJobs()) != 0 {
		t.Fatalf("这次不发就一封都不能发：%+v", res)
	}
	if e.count(`SELECT COUNT(*) FROM held_letters WHERE state = 'skipped'`) != 2 {
		t.Fatal("没发的该记成 skipped")
	}
}

func TestHeldExpiresAfterSevenDaysAndCleanupAfterThirty(t *testing.T) {
	e := newEnv(t)
	actor := e.user("队长")
	batch := e.hold(actor, []mail.Person{{Address: "a@x.example", Name: "甲"}}, []mail.Person{{Address: "b@x.example", Name: "乙"}}, t0)
	later := t0.Add(7*24*time.Hour + time.Minute)
	view, err := e.svc.Held(e.ctxAt(actor, later), batch.Key)
	if err != nil {
		t.Fatal(err)
	}
	if view.State != "expired" || len(view.Letters) != 0 {
		t.Fatalf("7 天后该作废：%+v", view)
	}
	ids := []int64{1, 2}
	res, err := e.svc.DecideHeld(e.ctxAt(actor, later), batch.Key, ids, false)
	if err != nil {
		t.Fatal(err)
	}
	if res.Letters != 0 || len(e.letterJobs()) != 0 {
		t.Fatalf("作废的信不能再发：%+v", res)
	}
	// 刚好 7 天内还能发
	batch2 := e.hold(actor, []mail.Person{{Address: "a@x.example", Name: "甲"}}, nil, t0)
	if v, _ := e.svc.Held(e.ctxAt(actor, t0.Add(7*24*time.Hour-time.Minute)), batch2.Key); v == nil || v.State != "waiting" {
		t.Fatalf("7 天内该还在等着：%+v", v)
	}

	// 清理：30 天以上的删，29 天的留
	err = e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		n, err := CleanupHeld(ctx, tx, t0.Add(30*24*time.Hour+time.Minute))
		if err != nil {
			return err
		}
		if n != 3 {
			return fmt.Errorf("该删 3 行，删了 %d", n)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	fresh := e.hold(e.user("新"), []mail.Person{{Address: "z@x.example", Name: "丁"}}, nil, t0.Add(29*24*time.Hour))
	_ = fresh
	err = e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		n, err := CleanupHeld(ctx, tx, t0.Add(30*24*time.Hour+time.Minute))
		if n != 0 {
			return fmt.Errorf("29 天前的不该删，删了 %d", n)
		}
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestWaitingListMergesByBatchAndLeavesOutExpired(t *testing.T) {
	e := newEnv(t)
	actor := e.user("队长")
	old := e.hold(actor, []mail.Person{{Address: "a@x.example", Name: "甲"}}, nil, t0.Add(-8*24*time.Hour))
	_ = old
	first := e.hold(actor, []mail.Person{{Address: "a@x.example", Name: "甲"}}, []mail.Person{{Address: "b@x.example", Name: "乙"}}, t0.Add(-time.Hour))
	second := e.hold(actor, []mail.Person{{Address: "c@x.example", Name: "丙"}}, nil, t0)
	list, err := e.svc.Waiting(e.ctxAt(actor, t0))
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 {
		t.Fatalf("该有两件事（过期的不算）：%+v", list)
	}
	if list[0].Batch != second.Key || list[1].Batch != first.Key {
		t.Fatalf("新的在前：%+v", list)
	}
	if len(list[1].Subjects) != 2 || list[1].People != 2 {
		t.Fatalf("同一批的两封信合成一件事：%+v", list[1])
	}
	if other, _ := e.svc.Waiting(e.ctxAt(e.user("路人"), t0)); len(other) != 0 {
		t.Fatal("别人的事不该出现在我的列表里")
	}
}

// --- 通过接口走一遍：登录用户的写动作冻住信，答复里带 letters（规则 206、207）------

func (e *env) handler() http.Handler {
	reg := &api.Registry{}
	NewModule(e.svc).Routes(reg)
	act := func(ctx *app.Ctx, in struct {
		Quit  bool `json:"quit"`
		Quiet bool `json:"quiet"`
	},
	) (map[string]any, error) {
		err := e.d.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
			if in.Quiet {
				return nil
			}
			_, err := outbox.Send(c, tx, ctx.Letters, "https://sjtu.example", mail.Letter{Subject: "申请通过", Lead: "a"},
				[]mail.Person{{Address: "a@x.example", Name: "甲"}}, ctx.Now())
			return err
		})
		if in.Quit {
			ctx.ClearSessionCookie()
		}
		return map[string]any{"ok": true}, err
	}
	api.Post(reg, "/api/test/act", api.Member, act, api.NoLimit("test"))
	api.Get(reg, "/api/test/peek", api.Member, func(ctx *app.Ctx, _ NoIn) (map[string]any, error) {
		return map[string]any{"ok": true}, nil
	})
	return reg.Handler(func(r *http.Request) *app.Viewer {
		id, _ := strconv.ParseInt(r.Header.Get("X-Test-User"), 10, 64)
		if id == 0 {
			return nil
		}
		v := &app.Viewer{ID: id, EmailVerified: true, Caps: map[app.Cap]struct{}{}}
		if r.Header.Get("X-Test-Cap") != "" {
			v.Caps[capAnnounce] = struct{}{}
		}
		return v
	}, api.WithLetters(e.d, "https://sjtu.example"))
}

func (e *env) call(h http.Handler, method, path string, user int64, body string, hdr ...string) (int, map[string]any) {
	e.t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	if user > 0 {
		req.Header.Set("X-Test-User", strconv.FormatInt(user, 10))
	}
	for i := 0; i+1 < len(hdr); i += 2 {
		req.Header.Set(hdr[i], hdr[i+1])
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var out map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &out)
	return rec.Code, out
}

func TestRegistryHoldsLettersOfALoggedInWriteAndAnswersWithTheBatch(t *testing.T) {
	e := newEnv(t)
	h := e.handler()
	actor := e.user("队长")

	code, out := e.call(h, "POST", "/api/test/act", actor, `{}`)
	if code != 200 {
		t.Fatalf("动作：%d %v", code, out)
	}
	letters, ok := out["letters"].(map[string]any)
	if !ok || letters["batch"] == "" || letters["count"].(float64) != 1 {
		t.Fatalf("答复里该带 letters{batch,count}：%v", out)
	}
	if len(e.letterJobs()) != 0 {
		t.Fatal("信该冻住，不该直接发")
	}
	batch := letters["batch"].(string)

	// 页面读、点发信
	code, out = e.call(h, "GET", "/api/letters/"+batch, actor, "")
	if code != 200 || len(out["letters"].([]any)) != 1 {
		t.Fatalf("读确认页：%d %v", code, out)
	}
	id := int64(out["letters"].([]any)[0].(map[string]any)["id"].(float64))
	code, out = e.call(h, "POST", "/api/letters/"+batch, actor, fmt.Sprintf(`{"send":[%d]}`, id))
	if code != 200 || out["letters"].(float64) != 1 || len(e.letterJobs()) != 1 {
		t.Fatalf("点发信：%d %v / %d", code, out, len(e.letterJobs()))
	}

	// 没登录的、只读的请求都没有 letters
	if code, out = e.call(h, "GET", "/api/test/peek", actor, ""); code != 200 || out["letters"] != nil {
		t.Fatalf("GET 不该有 letters：%v", out)
	}
	if code, _ = e.call(h, "GET", "/api/letters/"+batch, 0, ""); code != 401 {
		t.Fatalf("没登录读确认页该 401：%d", code)
	}
	// 动作没带出信时答复里没有 letters 这一项
	if code, out = e.call(h, "POST", "/api/test/act", actor, `{"quiet":true}`); code != 200 || out["letters"] != nil {
		t.Fatalf("没带出信就不该有 letters：%d %v", code, out)
	}
}

func TestRegistrySendsForTheActorWhoQuitDuringTheRequest(t *testing.T) {
	e := newEnv(t)
	h := e.handler()
	actor := e.user("注销的人")
	code, out := e.call(h, "POST", "/api/test/act", actor, `{"quit":true}`)
	if code != 200 {
		t.Fatalf("动作：%d %v", code, out)
	}
	if out["letters"] != nil {
		t.Fatalf("注销了就没人可问，不该带 letters：%v", out)
	}
	if len(e.letterJobs()) != 1 {
		t.Fatalf("做事的人注销了，这批信该由系统代发：%d", len(e.letterJobs()))
	}
	if e.count(`SELECT COUNT(*) FROM held_letters WHERE state = 'sent'`) != 1 {
		t.Fatal("代发的该记成 sent")
	}
}

// 契约 R073–R079、R209、R210：通知全体成员（权限门槛、定时发布上线通知、30分钟冷却、受众动态核算、前缀统一、历史记录与重试）
func TestAnnounceGatesAndConditions(t *testing.T) {
	e := newEnv(t)
	e.user("甲")
	admin := e.editor()

	// 没有能力的人不行
	plain := e.ctxAt(e.user("普通"), t0)
	if _, err := e.svc.Announce(plain, KindArticle, 1); err == nil {
		t.Fatal("没有权限不能发")
	} else {
		wantErr(t, err, 403, "")
	}
	if _, err := e.svc.Status(plain, KindArticle, 1); err == nil {
		t.Fatal("没有权限也不能看状态")
	}
	if _, err := e.svc.Announce(admin, "bogus", 1); err == nil {
		t.Fatal("不认识的种类")
	}
	// 没发布也没安排定时
	e.subject = &Subject{Title: "草稿", Live: false}
	_, err := e.svc.Announce(admin, KindArticle, 1)
	wantErr(t, err, 409, "发布之后才能通知")
	// 对象不存在
	e.subject = nil
	if _, err := e.svc.Announce(admin, KindArticle, 1); err == nil {
		t.Fatal("对象不存在该 404")
	}
	// SMTP 没配
	e.subject = &Subject{Title: "公告", Live: true}
	e.ready = false
	_, err = e.svc.Announce(admin, KindArticle, 1)
	wantErr(t, err, 409, "还没有配置邮件")
	st, err := e.svc.Status(admin, KindArticle, 1)
	if err != nil || !strings.Contains(st.Problem, "还没有配置邮件") {
		t.Fatalf("状态里也该说为什么发不出去：%+v %v", st, err)
	}
	e.ready = true
	if e.count(`SELECT COUNT(*) FROM broadcasts`) != 0 {
		t.Fatal("被拒的不该留下历史")
	}
}

func TestAnnounceDeliversOneLetterPerMemberWithOwnUnsubscribeLink(t *testing.T) {
	e := newEnv(t)
	admin := e.editor() // 编辑自己也是成员，收一封
	bob := e.user("乙")
	off := e.user("关了通知")
	e.exec(`UPDATE users SET accepts_announcements = 0 WHERE id = ?`, off)
	gone := e.user("停用")
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, gone)
	unverified := e.user("没验证")
	e.exec(`UPDATE users SET email_verified_at = NULL WHERE id = ?`, unverified)
	outsider := e.user("校外")
	e.exec(`UPDATE users SET is_sjtu = 0 WHERE id = ?`, outsider)

	res, err := e.svc.Announce(admin, KindArticle, 7)
	if err != nil {
		t.Fatal(err)
	}
	// 校外的人也收（文章不限交大）：编辑、乙、校外 = 3
	if res.Recipients != 3 || res.Waiting {
		t.Fatalf("该排给 3 人：%+v", res)
	}
	if e.count(`SELECT COUNT(*) FROM jobs WHERE kind = ?`, JobDeliver) != 1 {
		t.Fatal("该排一个下发任务")
	}
	if e.count(`SELECT COUNT(*) FROM audit_log WHERE action = 'articles.announce'`) != 1 {
		t.Fatal("该记一条操作记录")
	}
	e.deliver(res.BroadcastID)
	sent := e.letterJobs()
	if len(sent) != 3 {
		t.Fatalf("每人一封，共 3 封：%v", sent)
	}
	for _, addr := range []string{"u1@sjtu.example", fmt.Sprintf("u%d@sjtu.example", bob), fmt.Sprintf("u%d@sjtu.example", outsider)} {
		l, ok := sent[addr]
		if !ok {
			t.Fatalf("%s 没收到：%v", addr, sent)
		}
		if !strings.HasPrefix(l.Unsubscribe, "https://sjtu.example/unsubscribe/") || !strings.HasSuffix(l.Unsubscribe, "/") {
			t.Fatalf("退订链接：%q", l.Unsubscribe)
		}
		if l.Notice != "" {
			t.Fatalf("第一封不该有「发过几次」：%q", l.Notice)
		}
	}
	// 每人的退订链接各不相同，而且各自指向自己
	if sent["u1@sjtu.example"].Unsubscribe == sent[fmt.Sprintf("u%d@sjtu.example", bob)].Unsubscribe {
		t.Fatal("退订链接该每人一份")
	}
	token := strings.TrimSuffix(strings.TrimPrefix(sent[fmt.Sprintf("u%d@sjtu.example", bob)].Unsubscribe, "https://sjtu.example/unsubscribe/"), "/")
	if info, err := e.svc.UnsubscribeInfo(&app.Ctx{Context: context.Background()}, token); err != nil || info.Nickname != "乙" {
		t.Fatalf("链接该指向乙：%+v %v", info, err)
	}
	var got int
	if err := e.d.ReadPool().QueryRow(`SELECT recipient_count FROM broadcasts WHERE id = ?`, res.BroadcastID).Scan(&got); err != nil || got != 3 {
		t.Fatalf("历史里的人数该是实际发出的 3：%d %v", got, err)
	}
}

func TestDeliverRecountsRecipientsAtSendTime(t *testing.T) {
	e := newEnv(t)
	admin := e.editor()
	bob := e.user("乙")
	res, err := e.svc.Announce(admin, KindArticle, 1)
	if err != nil || res.Recipients != 2 {
		t.Fatalf("%+v %v", res, err)
	}
	// 排队到发送之间，乙关掉了活动通知
	e.exec(`UPDATE users SET accepts_announcements = 0 WHERE id = ?`, bob)
	e.deliver(res.BroadcastID)
	sent := e.letterJobs()
	if len(sent) != 1 {
		t.Fatalf("发送时才重算收件人，乙关了就不发：%v", sent)
	}
	if _, ok := sent[fmt.Sprintf("u%d@sjtu.example", bob)]; ok {
		t.Fatal("关了通知的人收到了信")
	}
}

func TestAnnounceCooldownAndRepeatNotice(t *testing.T) {
	e := newEnv(t)
	admin := e.editor()
	r1, err := e.svc.Announce(admin, KindArticle, 1)
	if err != nil {
		t.Fatal(err)
	}
	// 10 分钟后再发：冷却
	soon := e.ctxAt(admin.Viewer.ID, t0.Add(10*time.Minute), capAnnounce)
	_, err = e.svc.Announce(soon, KindArticle, 1)
	wantErr(t, err, 409, "30 分钟内不再发")
	st, _ := e.svc.Status(soon, KindArticle, 1)
	if !strings.Contains(st.Problem, "20:00 刚通知过") {
		t.Fatalf("冷却提示里该写上次的北京时间 20:00：%q", st.Problem)
	}
	// 29 分钟还不行，31 分钟可以
	edge := e.ctxAt(admin.Viewer.ID, t0.Add(29*time.Minute), capAnnounce)
	if _, err = e.svc.Announce(edge, KindArticle, 1); err == nil {
		t.Fatal("29 分钟还在冷却")
	}
	later := e.ctxAt(admin.Viewer.ID, t0.Add(31*time.Minute), capAnnounce)
	r2, err := e.svc.Announce(later, KindArticle, 1)
	if err != nil {
		t.Fatalf("31 分钟后该能发：%v", err)
	}
	// 另一个对象不受冷却牵连
	if _, err := e.svc.Announce(admin, KindArticle, 2); err != nil {
		t.Fatalf("别的对象不该被冷却挡：%v", err)
	}
	e.deliver(r1.BroadcastID)
	for _, l := range e.letterJobs() {
		if l.Notice != "" {
			t.Fatalf("第一封没有提示：%q", l.Notice)
		}
	}
	e.exec(`DELETE FROM jobs WHERE kind = ?`, outbox.KindLetter)
	e.deliver(r2.BroadcastID)
	for _, l := range e.letterJobs() {
		if l.Notice != "关于这篇文章「秋季招新」，之前已经发过 1 次邮件，这次可能有修改，请以这封为准。" {
			t.Fatalf("第二封该写之前发过 1 次：%q", l.Notice)
		}
	}
	if RepeatNotice("这场赛事", "X", 0) != "" {
		t.Fatal("没发过就没有提示")
	}
}

func TestAnnounceForAScheduledArticleWaitsAndSendsOnceWhenItGoesLive(t *testing.T) {
	e := newEnv(t)
	admin := e.editor()
	planned := t0.Add(48 * time.Hour)
	e.subject = &Subject{Title: "定时公告", Live: false, GoLiveAt: &planned}
	res, err := e.svc.Announce(admin, KindArticle, 5)
	if err != nil {
		t.Fatal(err)
	}
	if !res.Waiting || res.Recipients != 0 {
		t.Fatalf("定时的该记着、不数人：%+v", res)
	}
	if e.count(`SELECT COUNT(*) FROM jobs WHERE kind = ?`, JobDeliver) != 0 {
		t.Fatal("还没上线，不能排下发")
	}
	// 再安排一次被拒
	later := e.ctxAt(admin.Viewer.ID, t0.Add(time.Hour), capAnnounce)
	_, err = e.svc.Announce(later, KindArticle, 5)
	wantErr(t, err, 409, "已经安排在上线时通知")
	// 唯一索引兜底：绕过服务直接再插一条等着的，数据库也不让
	err = e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO broadcasts (kind, object_id, audience, waits_for_publish, created_at)
			VALUES ('article', 5, 'everyone', 1, ?)`, db.FormatUTC(t0))
		return err
	})
	if err == nil {
		t.Fatal("同一篇同时只能排一个上线时的通知")
	}

	// 上线：放出去一次
	var sent bool
	for i := 0; i < 2; i++ {
		err = e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
			s, err := SendWaiting(ctx, tx, KindArticle, 5, planned)
			if i == 0 {
				sent = s
			} else if s {
				return errors.New("第二次不该再放")
			}
			return err
		})
		if err != nil {
			t.Fatal(err)
		}
	}
	if !sent || e.count(`SELECT COUNT(*) FROM jobs WHERE kind = ?`, JobDeliver) != 1 {
		t.Fatalf("上线那一刻该放出一个下发任务：%v %d", sent, e.count(`SELECT COUNT(*) FROM jobs WHERE kind = ?`, JobDeliver))
	}
	if e.count(`SELECT COUNT(*) FROM broadcasts WHERE waits_for_publish = 1`) != 0 {
		t.Fatal("放出去后不再是等着的")
	}
	// 别的对象的等待不受影响
	e.exec(`INSERT INTO broadcasts (kind, object_id, audience, waits_for_publish, created_at) VALUES ('article', 6, 'everyone', 1, ?)`, db.FormatUTC(t0))
	_ = e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := SendWaiting(ctx, tx, KindArticle, 5, planned)
		return err
	})
	if e.count(`SELECT COUNT(*) FROM broadcasts WHERE object_id = 6 AND waits_for_publish = 1`) != 1 {
		t.Fatal("上线 5 号不该动 6 号等着的通知")
	}
}

func TestRecordParticipantsCountsEveryEarlierMailAndWritesTheNotice(t *testing.T) {
	e := newEnv(t)
	admin := e.ctxAt(e.user("管理"), t0)
	note := func() string {
		var n string
		err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
			var err error
			n, err = RecordParticipants(ctx, tx, ParticipantsNote{Kind: KindTournament, ObjectID: 3, Noun: "这场赛事", Title: "秋季赛",
				Subject: "赛事有更新：秋季赛", Note: "改到周六", Actor: admin.Viewer.ID, Recipients: 12}, t0)
			return err
		})
		if err != nil {
			t.Fatal(err)
		}
		return n
	}
	if n := note(); n != "" {
		t.Fatalf("第一封没有提示：%q", n)
	}
	if n := note(); n != "关于这场赛事「秋季赛」，之前已经发过 1 次邮件，这次可能有修改，请以这封为准。" {
		t.Fatalf("第二封：%q", n)
	}
	if n := note(); !strings.Contains(n, "之前已经发过 2 次") {
		t.Fatalf("第三封：%q", n)
	}
	// 「通知报名的人」和「通知全体」共用历史数
	e.exec(`INSERT INTO broadcasts (kind, object_id, audience, created_at) VALUES ('tournament', 3, 'everyone', ?)`, db.FormatUTC(t0))
	if n := note(); !strings.Contains(n, "之前已经发过 4 次") {
		t.Fatalf("历史该算上全体通知：%q", n)
	}
	if e.count(`SELECT COUNT(*) FROM audit_log WHERE action = 'tournaments.notify_participants'`) != 4 {
		t.Fatal("每次都该记操作记录")
	}
}

// 契约 R212、R213：退订体系（签名 Token、一键退订与本人有关信件不可退）
func TestUnsubscribeByLinkIsSignedIdempotentAndOnlyForActiveAccounts(t *testing.T) {
	e := newEnv(t)
	id := e.user("乙")
	ctx := &app.Ctx{Context: context.Background()}
	token := e.svc.Token(id)

	info, err := e.svc.UnsubscribeInfo(ctx, token)
	if err != nil || !info.Accepts || info.Nickname != "乙" {
		t.Fatalf("打开页面：%+v %v", info, err)
	}
	for i := 0; i < 2; i++ { // 点两次结果一样
		p, err := e.svc.Unsubscribe(ctx, token)
		if err != nil || p.Accepts {
			t.Fatalf("退订：%+v %v", p, err)
		}
	}
	var accepts int
	_ = e.d.ReadPool().QueryRow(`SELECT accepts_announcements FROM users WHERE id = ?`, id).Scan(&accepts)
	if accepts != 0 {
		t.Fatal("没关上")
	}
	// 篡改、别的盐、不是令牌：都 404
	for _, bad := range []string{token + "x", "abc", "", strings.Replace(token, token[:3], "zzz", 1)} {
		if _, err := e.svc.Unsubscribe(ctx, bad); err == nil {
			t.Fatalf("坏令牌 %q 不该通过", bad)
		}
	}
	// 另一个签名密钥签的不认
	other := NewService(e.d, "https://sjtu.example", "another-signing-key-0123456789-abcdefgh", nil)
	if _, err := e.svc.Unsubscribe(ctx, other.Token(id)); err == nil {
		t.Fatal("别的密钥签的令牌不该通过")
	}
	// 账号停用后，链接无效，也不会改任何东西
	other2 := e.user("丙")
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, other2)
	if _, err := e.svc.Unsubscribe(ctx, e.svc.Token(other2)); err == nil {
		t.Fatal("停用账号的链接该无效")
	}
	// 本人的开关：关了再打开；与本人有关的信不看这个开关
	me := e.ctxAt(id, t0)
	if p, err := e.svc.SetMyPrefs(me, true); err != nil || !p.Accepts {
		t.Fatalf("打开：%+v %v", p, err)
	}
	if p, err := e.svc.MyPrefs(me); err != nil || !p.Accepts {
		t.Fatalf("读：%+v %v", p, err)
	}
	e.exec(`UPDATE users SET accepts_announcements = 0 WHERE id = ?`, id)
	n, err := func() (int, error) {
		var n int
		err := e.d.WriteTx(context.Background(), func(c context.Context, tx *db.Tx) error {
			var err error
			n, err = outbox.Send(c, tx, nil, "https://sjtu.example", mail.Letter{Subject: "报名通过", Lead: "x"},
				[]mail.Person{{Address: "u2@sjtu.example", Name: "乙"}}, t0)
			return err
		})
		return n, err
	}()
	if err != nil || n != 1 {
		t.Fatalf("关了活动通知，本人相关的信照发：%d %v", n, err)
	}
}

func TestOneClickUnsubscribePostWorksWithoutLoginOrCSRF(t *testing.T) {
	e := newEnv(t)
	id := e.user("乙")
	h := e.handler()
	path := "/unsubscribe/" + e.svc.Token(id) + "/"
	req := httptest.NewRequest("POST", path, strings.NewReader("List-Unsubscribe=One-Click"))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != 200 {
		t.Fatalf("一键退订：%d %s", rec.Code, rec.Body.String())
	}
	var accepts int
	_ = e.d.ReadPool().QueryRow(`SELECT accepts_announcements FROM users WHERE id = ?`, id).Scan(&accepts)
	if accepts != 0 {
		t.Fatal("一键退订没生效")
	}
	bad := httptest.NewRecorder()
	h.ServeHTTP(bad, httptest.NewRequest("POST", "/unsubscribe/not-a-token/", nil))
	if bad.Code != 404 {
		t.Fatalf("坏令牌该 404：%d", bad.Code)
	}
	// 页面用的 JSON 接口同样公开
	code, out := e.call(h, "GET", "/api/announcements/unsubscribe/"+e.svc.Token(id), 0, "")
	if code != 200 || out["accepts"] != false {
		t.Fatalf("查看：%d %v", code, out)
	}
}
