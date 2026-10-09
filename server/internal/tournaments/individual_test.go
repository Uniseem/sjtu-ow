package tournaments

import (
	"net/http"
	"strconv"
	"strings"
	"testing"
	"time"
)

func (e *env) signup(tid, uid int64, roles ...string) {
	e.t.Helper()
	if _, err := e.svc.SignUpIndividual(e.ctx(uid), SignupInput{TournamentID: tid, GameAccountID: e.firstAccount(uid), Roles: roles}); err != nil {
		e.t.Fatalf("SignUpIndividual: %v", err)
	}
}

func (e *env) signupID(tid, uid int64) int64 {
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT id FROM individual_signups WHERE tournament_id = ? AND user_id = ?`, tid, uid).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return id
}

// 契约 R128：个人报名条件——个人模式、时间窗内、成员检查、无名单冲突、自己的游戏 ID、至少一个位置；重复提交是更新
func TestIndividualSignupRules(t *testing.T) {
	e := newEnv(t)
	u, v := e.user("甲"), e.user("乙")
	tid := e.tour(withMode(ModeIndividual), withSjtuOnly())
	acc := e.firstAccount(u)

	for name, in := range map[string]SignupInput{
		"没勾位置":    {TournamentID: tid, GameAccountID: acc},
		"别人的游戏ID": {TournamentID: tid, GameAccountID: e.firstAccount(v), Roles: []string{"tank"}},
		"没选游戏ID":  {TournamentID: tid, Roles: []string{"tank"}},
	} {
		if _, err := e.svc.SignUpIndividual(e.ctx(u), in); err == nil {
			t.Fatalf("%s 应被拒", name)
		}
	}
	wantMsg := func(err error, want string) {
		t.Helper()
		wantErr(t, err, http.StatusUnprocessableEntity, want)
	}
	_, err := e.svc.SignUpIndividual(e.ctx(u), SignupInput{TournamentID: tid, GameAccountID: acc})
	wantMsg(err, "至少要勾选一个能打的位置")
	_, err = e.svc.SignUpIndividual(e.ctx(u), SignupInput{TournamentID: tid, GameAccountID: e.firstAccount(v), Roles: []string{"tank"}})
	wantMsg(err, "请选择你自己的游戏 ID")

	// 仅限交大、窗口、整队赛事
	out := e.outsider("校外")
	_, err = e.svc.SignUpIndividual(e.ctx(out), SignupInput{TournamentID: tid, GameAccountID: e.firstAccount(out), Roles: []string{"tank"}})
	wantMsg(err, "该赛事仅限交大用户参加，你不符合")
	team := e.tour(withMode(ModeTeam))
	_, err = e.svc.SignUpIndividual(e.ctx(u), SignupInput{TournamentID: team, GameAccountID: acc, Roles: []string{"tank"}})
	wantMsg(err, IndividualsRefused)
	closed := e.tour(withMode(ModeIndividual), withWindow(t0.Add(-48*time.Hour), t0.Add(-time.Hour)))
	_, err = e.svc.SignUpIndividual(e.ctx(u), SignupInput{TournamentID: closed, GameAccountID: acc, Roles: []string{"tank"}})
	wantMsg(err, NotInWindow)

	// 提交、再提交（更新同一条）
	e.signup(tid, u, "tank")
	e.signup(tid, u, "damage", "support")
	if e.count(`SELECT COUNT(*) FROM individual_signups WHERE tournament_id = ? AND user_id = ?`, tid, u) != 1 {
		t.Fatal("重复提交是更新，不是新增")
	}
	if e.count(`SELECT COUNT(*) FROM individual_signups WHERE user_id = ? AND role_tank = 0 AND role_damage = 1 AND role_support = 1`, u) != 1 {
		t.Fatal("位置没更新")
	}
	// 数据库兜底：至少一个位置
	if _, err := e.d.WritePool().Exec(`INSERT INTO individual_signups (tournament_id, user_id, created_at, updated_at) VALUES (?, ?, 'x', 'x')`, tid, v); err == nil {
		t.Fatal("没有位置的个人报名应被约束拦下")
	}
	// 已在别的队名单上：冲突
	w := e.user("丙")
	other := e.tour(withMode(ModeIndividual))
	e.exec(`INSERT INTO registrations (tournament_id, team_id, status, team_name, submitted_at, created_at, updated_at) VALUES (?, NULL, 'approved', '先到队', ?, ?, ?)`, other, ts(t0), ts(t0), ts(t0))
	var rid int64
	e.d.ReadPool().QueryRow(`SELECT MAX(id) FROM registrations`).Scan(&rid)
	e.exec(`INSERT INTO registration_members (registration_id, tournament_id, user_id, nickname, battletag, is_active) VALUES (?, ?, ?, '丙', 'x', 1)`, rid, other, w)
	_, err = e.svc.SignUpIndividual(e.ctx(w), SignupInput{TournamentID: other, GameAccountID: e.firstAccount(w), Roles: []string{"tank"}})
	wantMsg(err, "丙 已经在该赛事的战队「先到队」名单中")
}

// 契约 R129：已被编入队伍后不能自行改报名信息；截止前可取消，已编队则须先退出队伍；截止后不能取消
func TestIndividualPlacedAndCancel(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	tid := e.tour(withMode(ModeIndividual))
	e.signup(tid, a, "tank")
	e.signup(tid, b, "support")
	if _, err := e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "临时一队", SignupIDs: []int64{e.signupID(tid, a), e.signupID(tid, b)}}}); err != nil {
		t.Fatal(err)
	}
	_, err := e.svc.SignUpIndividual(e.ctx(a), SignupInput{TournamentID: tid, GameAccountID: e.firstAccount(a), Roles: []string{"damage"}})
	wantErr(t, err, http.StatusConflict, "你已经被编入队伍")
	wantErr(t, e.svc.CancelIndividual(e.ctx(a), tid), http.StatusConflict, "要退出请在报名详情页")

	c := e.user("丙")
	e.signup(tid, c, "tank")
	e.exec(`UPDATE tournaments SET registration_closes_at = ? WHERE id = ?`, ts(t0.Add(-time.Minute)), tid)
	wantErr(t, e.svc.CancelIndividual(e.ctx(c), tid), http.StatusConflict, "报名已截止")
	e.exec(`UPDATE tournaments SET registration_closes_at = ? WHERE id = ?`, ts(t0.Add(time.Hour)), tid)
	if err := e.svc.CancelIndividual(e.ctx(c), tid); err != nil {
		t.Fatal(err)
	}
	wantErr(t, e.svc.CancelIndividual(e.ctx(c), tid), http.StatusConflict, "你还没有个人报名")
}

// 契约 R130：编队先全部校验再写入，任何一条错误整个操作不生效
func TestFormTeamsValidatesBeforeWriting(t *testing.T) {
	e := newEnv(t)
	tid := e.tour(withMode(ModeIndividual), withRoster(2, 3))
	var ids []int64
	var users []int64
	for _, n := range []string{"甲", "乙", "丙", "丁", "戊"} {
		u := e.user(n)
		users = append(users, u)
		e.signup(tid, u, "tank")
		ids = append(ids, e.signupID(tid, u))
	}
	before := func() int { return e.count(`SELECT COUNT(*) FROM registrations WHERE tournament_id = ?`, tid) }
	try := func(layout []LayoutTeam, want string) {
		t.Helper()
		_, err := e.svc.FormTeams(e.mgr(), tid, layout)
		wantErr(t, err, http.StatusUnprocessableEntity, want)
		if before() != 0 || e.count(`SELECT COUNT(*) FROM individual_signups WHERE registration_id IS NOT NULL`) != 0 {
			t.Fatalf("出错时什么都不该写入（%s）", want)
		}
	}
	try([]LayoutTeam{{Name: "一队", SignupIDs: ids[:2]}, {Name: "二队", SignupIDs: []int64{ids[1], ids[2]}}}, "乙 被放进了两支队伍")
	try([]LayoutTeam{{Name: "", SignupIDs: ids[:2]}}, "队伍要有名字")
	try([]LayoutTeam{{Name: strings.Repeat("长", 17), SignupIDs: ids[:2]}}, "超过 16 字")
	try([]LayoutTeam{{Name: "太大队", SignupIDs: ids[:4]}}, "超过上限 3")
	try([]LayoutTeam{{Name: "重名队", SignupIDs: ids[:2]}, {Name: "重名队", SignupIDs: ids[2:4]}}, "两支队伍不能同名")
	try([]LayoutTeam{{Name: "一队", SignupIDs: []int64{999999}}}, "不属于这项赛事")
	// 成员自己有问题（功能被限制）：整个操作不生效
	e.denied[users[2]] = true
	try([]LayoutTeam{{Name: "一队", SignupIDs: ids[:2]}, {Name: "二队", SignupIDs: ids[2:4]}}, "暂时无法参加赛事报名")
	delete(e.denied, users[2])
	// 现有队名不能和新队重名（不分大小写）
	if _, err := e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "Alpha", SignupIDs: ids[:2]}}); err != nil {
		t.Fatal(err)
	}
	_, err := e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "alpha", SignupIDs: ids[2:4]}})
	wantErr(t, err, http.StatusUnprocessableEntity, "在这项赛事里已经有了")
	// 空的新队被忽略
	if res, err := e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "空队"}, {RegistrationID: liveRegID(e, tid), Name: "Alpha", SignupIDs: ids[:2]}}); err != nil || res.Created != 0 {
		t.Fatalf("空队忽略：%+v %v", res, err)
	}
}

func liveRegID(e *env, tid int64) *int64 {
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT id FROM registrations WHERE tournament_id = ? AND team_id IS NULL AND status IN ('pending','approved') ORDER BY id LIMIT 1`, tid).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return &id
}

// 契约 R131、R132、R133：两阶段写（人在两队之间移动不触发一人一活跃名单约束）；布局里缺席的现有队全员回散人池并解散；通知
func TestFormTeamsMovesAndDissolves(t *testing.T) {
	e := newEnv(t)
	tid := e.tour(withMode(ModeIndividual), withRoster(1, 3))
	var ids []int64
	var users []int64
	for _, n := range []string{"甲", "乙", "丙", "丁"} {
		u := e.user(n)
		users = append(users, u)
		e.signup(tid, u, "tank")
		ids = append(ids, e.signupID(tid, u))
	}
	res, err := e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{
		{Name: "一队", SignupIDs: []int64{ids[0], ids[1]}},
		{Name: "二队", SignupIDs: []int64{ids[2]}},
	})
	if err != nil || res.Created != 2 {
		t.Fatalf("建两支队：%+v %v", res, err)
	}
	if got := e.mailsTo(users[0]); len(got) != 1 || !strings.Contains(got[0], "已编入临时队伍") {
		t.Fatalf("新编入的人收信：%v", got)
	}
	if len(e.mailsTo(users[3])) != 0 {
		t.Fatal("还在散人池的人不收编队信")
	}
	var r1, r2 int64
	e.d.ReadPool().QueryRow(`SELECT id FROM registrations WHERE team_name = '一队'`).Scan(&r1)
	e.d.ReadPool().QueryRow(`SELECT id FROM registrations WHERE team_name = '二队'`).Scan(&r2)
	e.clearMails()
	// 把乙从一队移到二队，丁加入一队：一次保存，不触发约束
	res, err = e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{
		{RegistrationID: &r1, Name: "一队", SignupIDs: []int64{ids[0], ids[3]}},
		{RegistrationID: &r2, Name: "二队", SignupIDs: []int64{ids[2], ids[1]}},
	})
	if err != nil || res.Updated != 2 {
		t.Fatalf("移动：%+v %v", res, err)
	}
	if e.count(`SELECT COUNT(*) FROM registration_members WHERE registration_id = ? AND user_id = ?`, r2, users[1]) != 1 {
		t.Fatal("乙应在二队")
	}
	if len(e.mailsTo(users[1])) != 1 || len(e.mailsTo(users[3])) != 1 || len(e.mailsTo(users[0])) != 0 {
		t.Fatal("只通知新进队的人")
	}
	// 一队不在布局里：全员回散人池并解散
	e.clearMails()
	res, err = e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{RegistrationID: &r2, Name: "二队", SignupIDs: []int64{ids[2], ids[1]}}})
	if err != nil || res.Dissolved != 1 || res.Returned != 2 {
		t.Fatalf("缺席的队解散：%+v %v", res, err)
	}
	if e.regStatus(r1) != RegWithdrawn || e.count(`SELECT COUNT(*) FROM individual_signups WHERE registration_id IS NULL`) != 2 {
		t.Fatal("一队应已撤回，两人回池")
	}
	if got := e.mailsTo(users[0]); len(got) != 1 || !strings.Contains(got[0], "回到了散人池") && !strings.Contains(got[0], "移回了散人池") {
		t.Fatalf("回池信：%v", got)
	}
	// 赛事结束后不能再编队（R126）
	e.exec(`UPDATE tournaments SET status = 'finished' WHERE id = ?`, tid)
	_, err = e.svc.FormTeams(e.mgr(), tid, nil)
	wantErr(t, err, http.StatusConflict, "赛事已结束")
}

// 契约 R134：队员在截止前自行退出临时队（成员行硬删除）；最后一人退出时队伍自动解散并通知赛事管理员；截止后不能退
func TestLeaveAdhoc(t *testing.T) {
	e := newEnv(t)
	tid := e.tour(withMode(ModeIndividual), withRoster(1, 3))
	a, b, admin := e.user("甲"), e.user("乙"), e.user("管理")
	e.exec(`INSERT INTO user_roles (user_id, role, created_at) VALUES (?, 'tournament_admin', ?)`, admin, ts(t0))
	e.signup(tid, a, "tank")
	e.signup(tid, b, "tank")
	e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "退出队", SignupIDs: []int64{e.signupID(tid, a), e.signupID(tid, b)}}})
	rid := *liveRegID(e, tid)

	_, err := e.svc.LeaveAdhoc(e.ctx(e.user("外人")), rid)
	wantErr(t, err, http.StatusConflict, "你不在这支队伍的名单里")
	e.exec(`UPDATE tournaments SET registration_closes_at = ? WHERE id = ?`, ts(t0.Add(-time.Minute)), tid)
	_, err = e.svc.LeaveAdhoc(e.ctx(a), rid)
	wantErr(t, err, http.StatusConflict, "报名已截止")
	e.exec(`UPDATE tournaments SET registration_closes_at = ? WHERE id = ?`, ts(t0.Add(time.Hour)), tid)
	e.clearMails()
	dissolved, err := e.svc.LeaveAdhoc(e.ctx(a), rid)
	if err != nil || dissolved {
		t.Fatalf("还有人，不解散：%v %v", dissolved, err)
	}
	if e.count(`SELECT COUNT(*) FROM registration_members WHERE registration_id = ? AND user_id = ?`, rid, a) != 0 {
		t.Fatal("成员行应硬删除")
	}
	if e.count(`SELECT COUNT(*) FROM individual_signups WHERE user_id = ? AND registration_id IS NULL`, a) != 1 {
		t.Fatal("回到散人池")
	}
	if got := e.mailsTo(admin); len(got) != 1 || !strings.Contains(got[0], "临时队伍成员退出") {
		t.Fatalf("管理员应收到通知：%v", got)
	}
	e.clearMails()
	dissolved, err = e.svc.LeaveAdhoc(e.ctx(b), rid)
	if err != nil || !dissolved || e.regStatus(rid) != RegWithdrawn {
		t.Fatalf("最后一人退出自动解散：%v %v", dissolved, err)
	}
	if got := e.mailsTo(admin); len(got) != 1 || !strings.Contains(got[0], "已自动解散") {
		t.Fatalf("解散的通知：%v", got)
	}
	if e.count(`SELECT COUNT(*) FROM registration_status_logs WHERE registration_id = ? AND action = 'dissolve' AND actor_type = 'system'`, rid) != 1 {
		t.Fatal("自动解散记 SYSTEM 日志")
	}
}

// 契约 R135：管理员解散临时队：全员回散人池，报名置已撤回，不发状态信、另有回池信
func TestDissolveAdhoc(t *testing.T) {
	e := newEnv(t)
	tid := e.tour(withMode(ModeIndividual), withRoster(1, 3))
	a, b := e.user("甲"), e.user("乙")
	e.signup(tid, a, "tank")
	e.signup(tid, b, "tank")
	e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "解散队", SignupIDs: []int64{e.signupID(tid, a), e.signupID(tid, b)}}})
	rid := *liveRegID(e, tid)
	e.clearMails()
	if err := e.svc.DissolveTeam(e.mgr(), rid); err != nil {
		t.Fatal(err)
	}
	if e.regStatus(rid) != RegWithdrawn || e.count(`SELECT COUNT(*) FROM individual_signups WHERE registration_id IS NULL`) != 2 {
		t.Fatal("解散后全员回池")
	}
	for _, u := range []int64{a, b} {
		got := e.mailsTo(u)
		if len(got) != 1 || !strings.Contains(got[0], "已由赛事管理员解散") || strings.Contains(got[0], "报名已撤回") {
			t.Fatalf("只发回池信：%v", got)
		}
	}
	wantErr(t, e.svc.DissolveTeam(e.mgr(), rid), http.StatusConflict, "已经不在报名中")
	// 整队报名不能这样解散
	cap, m := e.user("队长"), e.user("队员")
	t2 := e.tour()
	r := e.register(t2, e.team("整队", cap, m), cap)
	wantErr(t, e.svc.DissolveTeam(e.mgr(), r.ID), http.StatusConflict, "只有临时队伍能解散")
	// 没有编队版本冲突：base_version 落后 409
	e.signup(tid, a, "tank")
	e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{Name: "新队", SignupIDs: []int64{e.signupID(tid, a)}}})
	rid2 := *liveRegID(e, tid)
	_, err := e.svc.FormTeams(e.mgr(), tid, []LayoutTeam{{RegistrationID: &rid2, Name: "新队", SignupIDs: []int64{e.signupID(tid, a)}, BaseVersion: 99}})
	wantErr(t, err, http.StatusConflict, "刷新页面")
}

// 战队解散的拦截和退队信用到的两个查询（规则 104、99）
func TestRosterGuardQueries(t *testing.T) {
	e := newEnv(t)
	cap, m := e.user("队长"), e.user("队员")
	tid := e.tour()
	team := e.team("守卫队", cap, m)
	r := e.register(tid, team, cap)
	ctx := e.mgr().Context
	live, err := LiveRegistrations(ctx, e.d.ReadPool(), team)
	if err != nil || len(live) != 1 || live[0] != "春季赛" {
		t.Fatalf("进行中的报名：%v %v", live, err)
	}
	listed, err := EntriesStillListing(ctx, e.d.ReadPool(), team, m)
	if err != nil || len(listed) != 1 || listed[0].DetailURL != "/registrations/"+strconv.FormatInt(r.ID, 10)+"/" {
		t.Fatalf("还列着他的名单：%+v %v", listed, err)
	}
	// 赛事结束后不再拦
	e.exec(`UPDATE tournaments SET status = 'finished' WHERE id = ?`, tid)
	if live, _ := LiveRegistrations(ctx, e.d.ReadPool(), team); len(live) != 0 {
		t.Fatalf("赛事结束后不再拦：%v", live)
	}
	// 驳回后不再拦
	e.exec(`UPDATE tournaments SET status = 'published' WHERE id = ?`, tid)
	e.svc.Reject(e.mgr(), r.ID, "x")
	if live, _ := LiveRegistrations(ctx, e.d.ReadPool(), team); len(live) != 0 {
		t.Fatalf("驳回后不再拦：%v", live)
	}
	if listed, _ := EntriesStillListing(ctx, e.d.ReadPool(), team, m); len(listed) != 0 {
		t.Fatalf("驳回后名单不占名额：%v", listed)
	}
}
