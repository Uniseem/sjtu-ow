package scrims

import (
	"context"
	"net/http"
	"testing"
	"time"
)

// 契约 R153：报名检查——登录、未停用、功能可用、资料完整、仅限交大、已发布且未截止
func TestSignupEligibility(t *testing.T) {
	e := newEnv(t)
	u := e.user("甲", 2000, 2000, 2000)
	sid := e.scrim(sjtuOnly())
	in := func(uid int64) SignupInput {
		return SignupInput{ScrimID: sid, GameAccountID: e.account(uid), Roles: []string{Tank}}
	}
	_, err := e.svc.SignUp(e.anon(), in(u))
	wantErr(t, err, http.StatusUnauthorized, "")

	// 功能被限制：固定文案
	b := e.user("被禁", 2000, 2000, 2000)
	e.denied[b] = true
	_, err = e.svc.SignUp(e.ctx(b), in(b))
	wantErr(t, err, http.StatusUnprocessableEntity, "你暂时无法使用此功能")
	// 资料不完整
	c := e.user("无联系", 2000, 2000, 2000)
	e.exec(`DELETE FROM contacts WHERE user_id = ?`, c)
	_, err = e.svc.SignUp(e.ctx(c), in(c))
	wantErr(t, err, http.StatusUnprocessableEntity, "资料不完整（缺少联系方式）")
	// 仅限交大
	d := e.user("校外", 2000, 2000, 2000)
	e.exec(`UPDATE users SET is_sjtu = 0 WHERE id = ?`, d)
	_, err = e.svc.SignUp(e.ctx(d), in(d))
	wantErr(t, err, http.StatusUnprocessableEntity, "这场内战仅限交大用户参加")
	// 停用
	f := e.user("停用", 2000, 2000, 2000)
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, f)
	_, err = e.svc.SignUp(e.ctx(f), in(f))
	wantErr(t, err, http.StatusUnprocessableEntity, "账号已停用")
	// 草稿以外的非发布状态
	fin := e.scrim(withStatus(StatusFinished))
	_, err = e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: fin, GameAccountID: e.account(u), Roles: []string{Tank}})
	wantErr(t, err, http.StatusUnprocessableEntity, "这场内战当前不接受报名")
	if _, err := e.svc.SignUp(e.ctx(u), in(u)); err != nil {
		t.Fatalf("条件都满足应能报名：%v", err)
	}
}

// 契约 R154：报名截止留空 = 开始前都能报；设了就以它为准
func TestSignupDeadline(t *testing.T) {
	e := newEnv(t)
	u := e.user("甲", 2000, 2000, 2000)
	open := e.scrim(withStart(t0.Add(time.Hour)))
	if _, err := e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: open, GameAccountID: e.account(u), Roles: []string{Tank}}); err != nil {
		t.Fatalf("没设截止，开始前能报：%v", err)
	}
	started := e.scrim(withStart(t0.Add(-time.Minute)))
	_, err := e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: started, GameAccountID: e.account(u), Roles: []string{Tank}})
	wantErr(t, err, http.StatusUnprocessableEntity, "报名已截止")
	closed := e.scrim(withStart(t0.Add(48*time.Hour)), withCloses(t0.Add(-time.Minute)))
	_, err = e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: closed, GameAccountID: e.account(u), Roles: []string{Tank}})
	wantErr(t, err, http.StatusUnprocessableEntity, "报名已截止")
	later := e.scrim(withStart(t0.Add(48*time.Hour)), withCloses(t0.Add(24*time.Hour)))
	if _, err := e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: later, GameAccountID: e.account(u), Roles: []string{Tank}}); err != nil {
		t.Fatalf("设了截止，之前能报：%v", err)
	}
}

// 契约 R155、R156：游戏 ID 必须是自己的；角色限定每个勾的位置都要有段位，开放赛至少一个位置有段位；至少勾一个位置
func TestSignupRolesAndRanks(t *testing.T) {
	e := newEnv(t)
	rq := e.scrim()
	open := e.scrim(withFormat(Open5))
	u := e.user("只有输出", 0, 3000, 0)
	other := e.user("别人", 2000, 2000, 2000)
	acc := e.account(u)
	try := func(sid int64, roles ...string) error {
		_, err := e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: sid, GameAccountID: acc, Roles: roles})
		return err
	}
	wantErr(t, try(rq), http.StatusUnprocessableEntity, "至少要勾选一个能打的位置")
	wantErr(t, try(rq, Damage, Tank), http.StatusUnprocessableEntity, "还缺：坦克")
	if err := try(rq, Damage); err != nil {
		t.Fatalf("勾的位置都有段位：%v", err)
	}
	// 开放赛：勾没有段位的位置也行，只要有一个位置有段位
	if err := try(open, Tank); err != nil {
		t.Fatalf("开放赛只要一个位置有段位：%v", err)
	}
	none := e.user("没段位", 0, 0, 0)
	_, err := e.svc.SignUp(e.ctx(none), SignupInput{ScrimID: open, GameAccountID: e.account(none), Roles: []string{Tank}})
	wantErr(t, err, http.StatusUnprocessableEntity, "一个位置的段位都没填")
	// 别人的游戏 ID
	_, err = e.svc.SignUp(e.ctx(u), SignupInput{ScrimID: rq, GameAccountID: e.account(other), Roles: []string{Damage}})
	wantErr(t, err, http.StatusUnprocessableEntity, "请选择你自己的游戏 ID")
}

// 契约 R157、R158：改游戏 ID 或改位置清空已有分队并打标记；报名截止后不能取消；取消时已分队同样打标记
func TestSignupChangeClearsPlacement(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	u, w := e.user("甲", 2000, 2000, 2000), e.user("乙", 2000, 2000, 2000)
	e.signup(sid, u, Tank, Damage)
	e.signup(sid, w, Support)
	e.exec(`UPDATE scrim_signups SET is_selected = 1, team = 'a', assigned_role = 'tank', rating_used = 2000 WHERE user_id = ?`, u)
	e.exec(`UPDATE scrim_signups SET is_selected = 1 WHERE user_id = ?`, w) // 替补
	e.exec(`UPDATE scrims SET teams_generated_at = ?, roster_changed_at = NULL WHERE id = ?`, ts(t0.Add(-time.Hour)), sid)

	// 同样的位置和游戏 ID 再提交：不清
	e.signup(sid, u, Tank, Damage)
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE user_id = ? AND team = 'a'`, u) != 1 || e.get(sid).RosterChangedAt != nil {
		t.Fatal("没改任何东西不该清分队")
	}
	// 改位置：清空，打标记
	e.signup(sid, u, Tank)
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE user_id = ? AND team = '' AND is_selected = 0 AND assigned_role = '' AND rating_used IS NULL`, u) != 1 {
		t.Fatal("改位置应清空分队")
	}
	if got := e.get(sid); got.RosterChangedAt == nil || !teamsStale(got) {
		t.Fatalf("应打名单变动标记：%+v", got)
	}
	// 替补改位置也算
	e.exec(`UPDATE scrims SET roster_changed_at = NULL WHERE id = ?`, sid)
	e.signup(sid, w, Damage)
	if e.get(sid).RosterChangedAt == nil {
		t.Fatal("替补改位置，管理员也要知道")
	}
	// 没被安排过的人改位置：不打标记
	z := e.user("丙", 2000, 2000, 2000)
	e.signup(sid, z, Tank)
	e.exec(`UPDATE scrims SET roster_changed_at = NULL WHERE id = ?`, sid)
	e.signup(sid, z, Damage)
	if e.get(sid).RosterChangedAt != nil {
		t.Fatal("没安排过的人改位置不用打标记")
	}
	// 取消：已安排的打标记，没安排的不打
	e.exec(`UPDATE scrim_signups SET is_selected = 1, team = 'b', assigned_role = 'damage' WHERE user_id = ?`, w)
	if err := e.svc.CancelSignup(e.ctx(w), sid); err != nil {
		t.Fatal(err)
	}
	if e.get(sid).RosterChangedAt == nil {
		t.Fatal("已分队的人取消要打标记")
	}
	e.exec(`UPDATE scrims SET roster_changed_at = NULL WHERE id = ?`, sid)
	if err := e.svc.CancelSignup(e.ctx(z), sid); err != nil {
		t.Fatal(err)
	}
	if e.get(sid).RosterChangedAt != nil {
		t.Fatal("没安排过的人取消不打标记")
	}
	wantErr(t, e.svc.CancelSignup(e.ctx(z), sid), http.StatusConflict, "你还没有报名")
	// 截止后不能取消
	e.exec(`UPDATE scrims SET starts_at = ? WHERE id = ?`, ts(t0.Add(-time.Minute)), sid)
	wantErr(t, e.svc.CancelSignup(e.ctx(u), sid), http.StatusConflict, "报名已截止")
	_ = context.Background
}
