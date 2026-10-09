package scrims

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"
)

func (e *env) draft() *Scrim {
	e.t.Helper()
	sc, err := e.svc.CreateScrim(e.mgr())
	if err != nil {
		e.t.Fatal(err)
	}
	return sc
}

func (e *env) patch(sc *Scrim, ch Changes) *SaveResult {
	e.t.Helper()
	var v int64
	e.d.ReadPool().QueryRow(`SELECT version FROM scrims WHERE id = ?`, sc.ID).Scan(&v)
	r, err := e.svc.UpdateScrim(e.mgr(), sc.ID, v, ch)
	if err != nil {
		e.t.Fatal(err)
	}
	return r
}

func (e *env) get(id int64) *Scrim {
	sc, err := GetScrim(context.Background(), e.d.ReadPool(), id)
	if err != nil || sc == nil {
		e.t.Fatalf("GetScrim: %v", err)
	}
	return sc
}

// 契约 R144、R145、R146：状态只能前进；发布门槛；没填好的草稿不能取消；只有无人报名的草稿能删
func TestScrimLifecycle(t *testing.T) {
	e := newEnv(t)
	d := e.draft()
	_, err := e.svc.Publish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "标题、开始时间")
	_, err = e.svc.Cancel(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "直接删除")
	_, err = e.svc.Finish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "只有已发布")
	e.patch(d, Changes{Title: str("周五内战"), StartsAt: rfc(t0.Add(72 * time.Hour))})
	pub, err := e.svc.Publish(e.mgr(), d.ID)
	if err != nil || pub.Status != StatusPublished {
		t.Fatalf("发布：%+v %v", pub, err)
	}
	_, err = e.svc.Publish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "已经发布了")
	if _, err := e.svc.Finish(e.mgr(), d.ID); err != nil {
		t.Fatal(err)
	}
	_, err = e.svc.Publish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "已结束的内战不能再发布")
	_, err = e.svc.Finish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "只有已发布")

	c := e.draft()
	e.patch(c, Changes{Title: str("要取消的"), StartsAt: rfc(t0.Add(72 * time.Hour))})
	if _, err := e.svc.Cancel(e.mgr(), c.ID); err != nil {
		t.Fatalf("填好的草稿可以取消：%v", err)
	}
	_, err = e.svc.Publish(e.mgr(), c.ID)
	wantErr(t, err, http.StatusConflict, "已取消的内战不能再发布")
	_, err = e.svc.Cancel(e.mgr(), c.ID)
	wantErr(t, err, http.StatusConflict, "已经取消了")

	// 删除：只有草稿，且没人报名
	x := e.draft()
	if err := e.svc.DeleteScrim(e.mgr(), x.ID); err != nil {
		t.Fatalf("空草稿可以删：%v", err)
	}
	y := e.draft()
	u := e.user("甲", 2000, 2000, 2000)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, created_at, updated_at) VALUES (?, ?, 1, ?, ?)`, y.ID, u, ts(t0), ts(t0))
	wantErr(t, e.svc.DeleteScrim(e.mgr(), y.ID), http.StatusConflict, "已经有人报名")
	wantErr(t, e.svc.DeleteScrim(e.mgr(), d.ID), http.StatusConflict, "只能取消")
	// 没有能力
	_, err = e.svc.CreateScrim(e.ctx(u))
	wantErr(t, err, http.StatusForbidden, "")
	// 自动保存：落后版本 409
	_, err = e.svc.UpdateScrim(e.mgr(), d.ID, 1, Changes{Title: str("x")})
	wantErr(t, err, http.StatusConflict, "另一个人刚改过")
}

// 契约 R148、R149：草稿对外 404；已结束的在列表保留 30 天；取消的保留详情页但离开列表
func TestScrimVisibility(t *testing.T) {
	e := newEnv(t)
	pub := e.scrim()
	dr := e.scrim(withStatus(StatusDraft))
	fresh := e.scrim(withStatus(StatusFinished), withStart(t0.Add(-29*24*time.Hour)))
	old := e.scrim(withStatus(StatusFinished), withStart(t0.Add(-31*24*time.Hour)))
	can := e.scrim(withStatus(StatusCancelled))

	list, err := e.svc.List(context.Background(), t0)
	if err != nil {
		t.Fatal(err)
	}
	got := map[int64]bool{}
	for _, c := range list {
		got[c.ID] = true
	}
	if !got[pub] || !got[fresh] || got[old] || got[can] || got[dr] {
		t.Fatalf("列表：%v", got)
	}
	_, err = e.svc.Detail(e.anon(), dr)
	wantErr(t, err, http.StatusNotFound, "")
	if _, err := e.svc.Detail(e.anon(), can); err != nil {
		t.Fatalf("取消的内战保留详情页：%v", err)
	}
	if _, err := e.svc.Detail(e.anon(), old); err != nil {
		t.Fatalf("过了 30 天的详情页仍在：%v", err)
	}
	u := e.user("甲", 2000, 2000, 2000)
	_, err = e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: dr, GameAccountID: e.account(u), Roles: []string{Tank}})
	wantErr(t, err, http.StatusNotFound, "")
}

// 契约 R147：开始后 6 小时自动结束；未发布的不动
func TestAutoFinish(t *testing.T) {
	e := newEnv(t)
	started := e.scrim(withStart(t0.Add(-7 * time.Hour)))
	recent := e.scrim(withStart(t0.Add(-5 * time.Hour)))
	draft := e.scrim(withStatus(StatusDraft), withStart(t0.Add(-9*time.Hour)))
	if err := e.svc.AutoFinish(context.Background(), t0); err != nil {
		t.Fatal(err)
	}
	if e.get(started).Status != StatusFinished || e.get(recent).Status != StatusPublished || e.get(draft).Status != StatusDraft {
		t.Fatal("过了 6 小时的结束，没过的和草稿不动")
	}
	// 开始时间后移：重读后不结束
	e.exec(`UPDATE scrims SET starts_at = ? WHERE id = ?`, ts(t0.Add(time.Hour)), recent)
	e.svc.AutoFinish(context.Background(), t0.Add(2*time.Hour))
	if e.get(recent).Status != StatusPublished {
		t.Fatal("时间后移不该结束")
	}
}

// 契约 R150：取消内战通知所有活跃且有邮箱的报名者
func TestCancelNotifiesSignups(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	a, b, gone := e.user("甲", 2000, 2000, 2000), e.user("乙", 2000, 2000, 2000), e.user("停用", 2000, 2000, 2000)
	for _, u := range []int64{a, b, gone} {
		e.signup(sid, u, Tank)
	}
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, gone)
	e.clearMails()
	if _, err := e.svc.Cancel(e.mgr(), sid); err != nil {
		t.Fatal(err)
	}
	if len(e.mailsTo(a)) != 1 || len(e.mailsTo(b)) != 1 || len(e.mailsTo(gone)) != 0 {
		t.Fatalf("取消通知：a=%d b=%d 停用=%d", len(e.mailsTo(a)), len(e.mailsTo(b)), len(e.mailsTo(gone)))
	}
	if m := e.mailsTo(a)[0]; !strings.Contains(m, "内战已取消") {
		t.Fatalf("信：%s", m)
	}
}

// 契约 R151：开赛前提醒一次，每名报名者一封，含本人分队去向和社团 QQ 群
func TestReminder(t *testing.T) {
	e := newEnv(t)
	start := t0.Add(5 * time.Hour)
	sid := e.scrim(withStart(start))
	e.exec(`UPDATE site_settings SET qq_group_url = 'https://qm.qq.com/xyz' WHERE id = 1`)
	a, b := e.user("甲", 2000, 2000, 2000), e.user("乙", 2000, 2000, 2000)
	e.signup(sid, a, Tank)
	e.signup(sid, b, Damage)
	e.exec(`UPDATE scrim_signups SET team = 'a', assigned_role = 'tank', is_selected = 1 WHERE user_id = ?`, a)
	e.exec(`UPDATE scrim_signups SET is_selected = 1 WHERE user_id = ?`, b)
	e.exec(`UPDATE scrims SET updated_at = ? WHERE id = ?`, ts(t0.Add(-time.Hour)), sid)
	ctx := context.Background()
	if n, _ := e.svc.SendDueReminders(ctx, t0); n != 0 {
		t.Fatalf("开始前 5 小时还没到 2 小时：%d", n)
	}
	e.clearMails()
	now := t0.Add(3*time.Hour + 30*time.Minute)
	n, err := e.svc.SendDueReminders(ctx, now)
	if err != nil || n != 2 {
		t.Fatalf("两封：%d %v", n, err)
	}
	ma, mb := e.mailsTo(a), e.mailsTo(b)
	if len(ma) != 1 || !strings.Contains(ma[0], "A 队 · 坦克") || !strings.Contains(ma[0], "https://qm.qq.com/xyz") {
		t.Fatalf("甲的提醒：%v", ma)
	}
	if len(mb) != 1 || !strings.Contains(mb[0], "替补") {
		t.Fatalf("乙的提醒：%v", mb)
	}
	if n, _ := e.svc.SendDueReminders(ctx, now.Add(time.Minute)); n != 0 {
		t.Fatalf("一场一次：%d", n)
	}
	// 刚保存的至少等 10 分钟
	s2 := e.scrim(withStart(t0.Add(time.Hour)))
	e.exec(`UPDATE scrims SET updated_at = ? WHERE id = ?`, ts(t0.Add(-5*time.Minute)), s2)
	e.signup(s2, a, Tank)
	if n, _ := e.svc.SendDueReminders(ctx, t0); n != 0 {
		t.Fatalf("刚保存 5 分钟，再等：%d", n)
	}
	e.exec(`UPDATE scrims SET updated_at = ? WHERE id = ?`, ts(t0.Add(-11*time.Minute)), s2)
	if n, _ := e.svc.SendDueReminders(ctx, t0); n != 1 {
		t.Fatalf("过了宽限期该发：%d", n)
	}
}

// 契约 R152：改期同赛事规则；「通知报名的人」写明原来和现在
func TestScrimTimeChangeAndNotify(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	a := e.user("甲", 2000, 2000, 2000)
	e.signup(sid, a, Tank)
	orig := t0.Add(10 * 24 * time.Hour)
	e.exec(`UPDATE scrims SET reminder_sent_at = ? WHERE id = ?`, ts(t0), sid)
	e.patch(&Scrim{ID: sid}, Changes{StartsAt: rfc(orig.Add(24 * time.Hour))})
	got := e.get(sid)
	if got.MovedFrom == nil || !got.MovedFrom.Equal(orig) || got.ReminderSentAt != nil {
		t.Fatalf("改期：%+v", got)
	}
	e.clearMails()
	n, err := e.svc.NotifyParticipants(e.mgr(), sid, "改到周六")
	if err != nil || n != 1 {
		t.Fatalf("通知：%d %v", n, err)
	}
	if m := e.mailsTo(a); len(m) != 1 || !strings.Contains(m[0], "开始时间改了：原来") || !strings.Contains(m[0], "改到周六") {
		t.Fatalf("信：%v", m)
	}
	if e.get(sid).MovedFrom != nil {
		t.Fatal("通知后清 moved_from")
	}
	// 通知之后，大家知道的时间是 orig+24h：移走再移回这个时间，moved_from 清空
	known := orig.Add(24 * time.Hour)
	e.patch(&Scrim{ID: sid}, Changes{StartsAt: rfc(orig)})
	if got := e.get(sid).MovedFrom; got == nil || !got.Equal(known) {
		t.Fatalf("移走后记下大家知道的时间：%v", got)
	}
	e.patch(&Scrim{ID: sid}, Changes{StartsAt: rfc(orig.Add(48 * time.Hour))})
	if got := e.get(sid).MovedFrom; got == nil || !got.Equal(known) {
		t.Fatalf("多次移动保留最早那次：%v", got)
	}
	e.patch(&Scrim{ID: sid}, Changes{StartsAt: rfc(known)})
	if e.get(sid).MovedFrom != nil {
		t.Fatal("改回大家知道的时间应清空")
	}
}

// 契约 R169：复制只抄标题/说明/规格/仅限交大，两个时间整周平移
func TestScrimCopy(t *testing.T) {
	e := newEnv(t)
	start := t0.Add(-20 * 24 * time.Hour)
	sid := e.scrim(withFormat(FormatRQ6), withStart(start), withCloses(start.Add(-time.Hour)), sjtuOnly())
	e.exec(`UPDATE scrims SET description = '**说明**', reminder_sent_at = ?, teams_generated_at = ? WHERE id = ?`, ts(t0), ts(t0), sid)
	u := e.user("甲", 2000, 2000, 2000)
	e.exec(`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, created_at, updated_at) VALUES (?, ?, 1, ?, ?)`, sid, u, ts(t0), ts(t0))
	c, err := e.svc.Copy(e.mgr(), sid)
	if err != nil {
		t.Fatal(err)
	}
	if c.Status != StatusDraft || c.Format != FormatRQ6 || !c.SjtuOnly || c.Description != "**说明**" || c.ReminderSentAt != nil || c.TeamsGeneratedAt != nil {
		t.Fatalf("复制：%+v", c)
	}
	shift := c.StartsAt.Sub(start)
	if shift%(7*24*time.Hour) != 0 || !c.StartsAt.After(t0) || c.StartsAt.Sub(*c.SignupClosesAt) != time.Hour {
		t.Fatalf("平移整周且落在未来：%v", shift)
	}
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE scrim_id = ?`, c.ID) != 0 {
		t.Fatal("报名不带")
	}
}
