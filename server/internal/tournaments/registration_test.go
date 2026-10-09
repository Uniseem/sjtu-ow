package tournaments

import (
	"net/http"
	"strconv"
	"strings"
	"testing"
	"time"
)

// 契约 R115：预检把所有问题一次列出
func TestPrecheckListsEveryProblem(t *testing.T) {
	e := newEnv(t)
	cap, m1, m2 := e.user("队长"), e.user("队员一"), e.user("队员二")
	e.exec(`UPDATE users SET is_sjtu = 0 WHERE id = ?`, m1)
	e.exec(`DELETE FROM contacts WHERE user_id = ?`, m2)
	e.denied[m1] = true
	tid := e.tour(withSjtuOnly(), withRoster(5, 6), withWindow(t0.Add(-48*time.Hour), t0.Add(-24*time.Hour)))
	team := e.team("问题队", cap, m1, m2)
	_, err := e.svc.Submit(e.ctx(m2), SubmitInput{TournamentID: tid, TeamID: team})
	wantErr(t, err, http.StatusUnprocessableEntity, NotInWindow)
	for _, want := range []string{
		"只有队长可以为战队报名", "该赛事要求 5 到 6 人，你的战队现在有 3 人", "队员一 暂时无法参加赛事报名",
		"队员二 的资料不完整（缺少联系方式）", "该赛事仅限交大用户参加，队员一不符合",
	} {
		wantErr(t, err, http.StatusUnprocessableEntity, want)
	}
	// 个人报名的赛事不收战队
	ind := e.tour(withMode(ModeIndividual))
	_, err = e.svc.Submit(e.ctx(cap), SubmitInput{TournamentID: ind, TeamID: team})
	wantErr(t, err, http.StatusUnprocessableEntity, TeamsRefused)
	// 草稿对外 404
	dr := e.tour(withStatus(StatusDraft))
	_, err = e.svc.Submit(e.ctx(cap), SubmitInput{TournamentID: dr, TeamID: team})
	wantErr(t, err, http.StatusNotFound, "")
}

// 契约 R116：对队长隐藏原因（功能被限制的成员只显示「暂时无法参加」，不说是哪项规则）；本人自己看到固定文案
func TestMemberCheckHidesReason(t *testing.T) {
	e := newEnv(t)
	cap, m := e.user("队长"), e.user("队员")
	e.denied[m] = true
	tid := e.tour()
	team := e.team("隐藏队", cap, m)
	_, err := e.svc.Submit(e.ctx(cap), SubmitInput{TournamentID: tid, TeamID: team})
	wantErr(t, err, http.StatusUnprocessableEntity, "队员 暂时无法参加赛事报名")
	ps, err := e.svc.individualProblems(e.ctx(m).Context, e.d.ReadPool(), &Tournament{ID: tid, RegistrationMode: ModeIndividual}, m, t0)
	if err != nil || len(ps) == 0 || !strings.Contains(strings.Join(ps, "|"), "你暂时无法使用此功能") {
		t.Fatalf("本人看到固定文案：%v %v", ps, err)
	}
}

// 契约 R117：一人同一赛事只能在一个活跃名单上；被驳回释放名额后可以去别的队
func TestOneActiveRoster(t *testing.T) {
	e := newEnv(t)
	a, b, c := e.user("甲"), e.user("乙"), e.user("丙")
	tid := e.tour()
	t1, t2 := e.team("一队", a, b), e.team("二队", c, b)
	r1 := e.register(tid, t1, a)
	_, err := e.svc.Submit(e.ctx(c), SubmitInput{TournamentID: tid, TeamID: t2})
	wantErr(t, err, http.StatusUnprocessableEntity, "乙 已经在该赛事的战队「一队」名单中")
	if _, err := e.svc.Reject(e.mgr(), r1.ID, "名单不对"); err != nil {
		t.Fatal(err)
	}
	if e.count(`SELECT COUNT(*) FROM registration_members WHERE registration_id = ? AND is_active = 1`, r1.ID) != 0 {
		t.Fatal("驳回后名单不再占名额")
	}
	e.register(tid, t2, c)
}

// 契约 R118、R119：所选游戏 ID 必须是成员自己的；没选回落到第一个；名单是快照
func TestAccountSelectionAndSnapshot(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	e.exec(`INSERT INTO game_accounts (user_id, battletag, battletag_norm, rank_tank, ranks_updated_at, created_at, updated_at)
		VALUES (?, 'Second#2', 'second#2', 4000, ?, ?, ?)`, b, ts(t0), ts(t0), ts(t0))
	tid := e.tour()
	team := e.team("快照队", a, b)
	bOther := e.firstAccount(a) // 别人的游戏 ID
	_, err := e.svc.Submit(e.ctx(a), SubmitInput{TournamentID: tid, TeamID: team, Accounts: map[string]int64{strconv.FormatInt(b, 10): bOther}})
	wantErr(t, err, http.StatusUnprocessableEntity, "游戏 ID 选择有误")

	var second int64
	e.d.ReadPool().QueryRow(`SELECT id FROM game_accounts WHERE battletag = 'Second#2'`).Scan(&second)
	r, err := e.svc.Submit(e.ctx(a), SubmitInput{TournamentID: tid, TeamID: team, Accounts: map[string]int64{strconv.FormatInt(b, 10): second}})
	if err != nil {
		t.Fatal(err)
	}
	rows, _ := roster(e.mgr().Context, e.d.ReadPool(), r.ID)
	byNick := map[string]RosterMember{}
	for _, m := range rows {
		byNick[m.Nickname] = m
	}
	if byNick["乙"].Battletag != "Second#2" || byNick["甲"].Battletag != "P1#1000" || !byNick["甲"].IsCaptain || byNick["乙"].IsCaptain {
		t.Fatalf("没选的回落到第一个，选了的用所选的：%+v", rows)
	}
	if byNick["乙"].RankTank == nil || *byNick["乙"].RankTank != 4000 || !byNick["甲"].IsSJTU {
		t.Fatalf("段位、是否交大要定格：%+v", byNick["乙"])
	}
	// 快照：之后改昵称、改游戏 ID、改段位都不影响
	e.exec(`UPDATE users SET nickname = '改名了' WHERE id = ?`, b)
	e.exec(`UPDATE game_accounts SET battletag = 'Changed#9', rank_tank = 1 WHERE id = ?`, second)
	rows, _ = roster(e.mgr().Context, e.d.ReadPool(), r.ID)
	for _, m := range rows {
		if m.UserID == b && (m.Nickname != "乙" || m.Battletag != "Second#2" || *m.RankTank != 4000) {
			t.Fatalf("快照被改了：%+v", m)
		}
	}
	// 一个游戏 ID 都没有：报错
	c := e.user("无号")
	e.exec(`DELETE FROM game_accounts WHERE user_id = ?`, c)
	t2 := e.team("无号队", e.user("队长二"), c)
	_, err = e.svc.Submit(e.ctx(t2Captain(e, t2)), SubmitInput{TournamentID: tid, TeamID: t2})
	wantErr(t, err, http.StatusUnprocessableEntity, "还没有填写游戏 ID")
}

func t2Captain(e *env, team int64) int64 {
	var id int64
	e.d.ReadPool().QueryRow(`SELECT user_id FROM team_memberships WHERE team_id = ? AND role = 'captain'`, team).Scan(&id)
	return id
}

// 契约 R120、R121、R123：提交→待审；自动通过在同一事务由系统完成且不另发状态信；新进名单的队员各收一封，同步名单时只通知新增的
func TestSubmitAutoApproveAndMails(t *testing.T) {
	e := newEnv(t)
	a, b, c := e.user("队长"), e.user("队员"), e.user("新队员")
	tid := e.tour(withAuto(), withContact("QQ 群 5"), withRoster(2, 3))
	team := e.team("自动队", a, b)
	r := e.register(tid, team, a)
	if r.Status != RegApproved {
		t.Fatalf("自动通过：%s", r.Status)
	}
	var logs []string
	rows, _ := e.d.ReadPool().Query(`SELECT action || ':' || actor_type FROM registration_status_logs WHERE registration_id = ? ORDER BY id`, r.ID)
	for rows.Next() {
		var s string
		rows.Scan(&s)
		logs = append(logs, s)
	}
	rows.Close()
	if strings.Join(logs, ",") != "submit:captain,approve:system" {
		t.Fatalf("日志：%v", logs)
	}
	capMails := e.mailsTo(a)
	if len(capMails) != 1 || !strings.Contains(capMails[0], "并且已经通过") || strings.Contains(capMails[0], "状态变成了") {
		t.Fatalf("队长只收提交信，写明已通过：%v", capMails)
	}
	if got := e.mailsTo(b); len(got) != 1 || !strings.Contains(got[0], "你已被报名参加") {
		t.Fatalf("队员收到被报名的信：%v", got)
	}
	// 队里加一个人，同步名单：只有新增的人收信
	e.exec(`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)`, team, c, ts(t0))
	e.clearMails()
	r2 := e.register(tid, team, a)
	if r2.RosterVersion != 2 || r2.ID != r.ID {
		t.Fatalf("同步名单版本加一：%+v", r2)
	}
	if len(e.mailsTo(b)) != 0 || len(e.mailsTo(c)) != 1 {
		t.Fatalf("只通知新增的人：b=%d c=%d", len(e.mailsTo(b)), len(e.mailsTo(c)))
	}
	// 不自动通过的赛事是待审
	t2 := e.tour()
	other := e.team("手动队", e.user("队长三"), e.user("队员三"))
	if r3 := e.register(t2, other, t2Captain(e, other)); r3.Status != RegPending {
		t.Fatalf("默认待审：%s", r3.Status)
	}
}

// 契约 R122、R123、R126：状态机——通过/驳回/撤销；驳回释放名额；队长收到每次管理员变更的通知；赛事取消/结束后不能再审核
func TestStatusMachine(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("队长"), e.user("队员")
	tid := e.tour()
	team := e.team("状态队", a, b)
	r := e.register(tid, team, a)

	if _, err := e.svc.Approve(e.mgr(), r.ID); err != nil {
		t.Fatal(err)
	}
	_, err := e.svc.Approve(e.mgr(), r.ID)
	wantErr(t, err, http.StatusConflict, "当前状态不能通过")
	if got := e.mailsTo(a); len(got) != 2 || !strings.Contains(got[1], "报名已通过") {
		t.Fatalf("管理员通过要通知队长：%v", got)
	}
	if _, err := e.svc.Reject(e.mgr(), r.ID, "  "); err == nil {
		t.Fatal("驳回必须填备注")
	}
	if _, err := e.svc.Reject(e.mgr(), r.ID, "名单有误"); err != nil { // 撤销已通过
		t.Fatal(err)
	}
	var actions []string
	rows, _ := e.d.ReadPool().Query(`SELECT action FROM registration_status_logs WHERE registration_id = ? ORDER BY id`, r.ID)
	for rows.Next() {
		var s string
		rows.Scan(&s)
		actions = append(actions, s)
	}
	rows.Close()
	if strings.Join(actions, ",") != "submit,approve,revoke" {
		t.Fatalf("日志：%v", actions)
	}
	_, err = e.svc.Reject(e.mgr(), r.ID, "再驳回")
	wantErr(t, err, http.StatusConflict, "当前状态不能驳回")
	// 重新提交：回到待审，版本加一
	r2 := e.register(tid, team, a)
	if r2.Status != RegPending || r2.RosterVersion != 2 {
		t.Fatalf("重新提交：%+v", r2)
	}
	// 赛事结束后不能审核
	e.exec(`UPDATE tournaments SET status = 'finished' WHERE id = ?`, tid)
	_, err = e.svc.Approve(e.mgr(), r.ID)
	wantErr(t, err, http.StatusConflict, "赛事已结束")
	e.exec(`UPDATE tournaments SET status = 'cancelled' WHERE id = ?`, tid)
	_, err = e.svc.Reject(e.mgr(), r.ID, "x")
	wantErr(t, err, http.StatusConflict, "赛事已取消")
	// 没有能力不能审核
	_, err = e.svc.Approve(e.ctx(b), r.ID)
	wantErr(t, err, http.StatusForbidden, "")
}

// 契约 R125：驳回备注 ≤300 字；临时队伍不能在审核页驳回
func TestRejectNoteAndAdhoc(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("队长"), e.user("队员")
	tid := e.tour()
	r := e.register(tid, e.team("备注队", a, b), a)
	out, err := e.svc.Reject(e.mgr(), r.ID, strings.Repeat("长", 400))
	if err != nil || len([]rune(out.StatusNote)) != 300 {
		t.Fatalf("备注截到 300 字：%d %v", len([]rune(out.StatusNote)), err)
	}
	e.exec(`INSERT INTO registrations (tournament_id, team_id, status, team_name, submitted_at, created_at, updated_at) VALUES (?, NULL, 'approved', '临时队', ?, ?, ?)`, tid, ts(t0), ts(t0), ts(t0))
	var rid int64
	e.d.ReadPool().QueryRow(`SELECT MAX(id) FROM registrations`).Scan(&rid)
	_, err = e.svc.Reject(e.mgr(), rid, "x")
	wantErr(t, err, http.StatusConflict, "临时队伍请在")
}

// 契约 R124：只有队长、仅限活跃状态、且在报名截止前能撤回
func TestWithdraw(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("队长"), e.user("队员")
	tid := e.tour()
	team := e.team("撤回队", a, b)
	r := e.register(tid, team, a)
	_, err := e.svc.Withdraw(e.ctx(b), r.ID)
	wantErr(t, err, http.StatusForbidden, "只有队长")
	e.exec(`UPDATE tournaments SET registration_closes_at = ? WHERE id = ?`, ts(t0.Add(-time.Minute)), tid)
	_, err = e.svc.Withdraw(e.ctx(a), r.ID)
	wantErr(t, err, http.StatusConflict, "报名已截止")
	e.exec(`UPDATE tournaments SET registration_closes_at = ? WHERE id = ?`, ts(t0.Add(time.Hour)), tid)
	out, err := e.svc.Withdraw(e.ctx(a), r.ID)
	if err != nil || out.Status != RegWithdrawn {
		t.Fatalf("撤回：%+v %v", out, err)
	}
	if e.count(`SELECT COUNT(*) FROM registration_members WHERE registration_id = ? AND is_active = 1`, r.ID) != 0 {
		t.Fatal("撤回后释放名额")
	}
	_, err = e.svc.Withdraw(e.ctx(a), r.ID)
	wantErr(t, err, http.StatusConflict, "当前状态不能撤回")
	// 提交者之外的队长换人：新队长也能撤回
}

// 契约 R127：报名详情只有队长和名单上的人看得到；选手联系方式只给名单上有效的人
func TestRegistrationVisibility(t *testing.T) {
	e := newEnv(t)
	a, b, x := e.user("队长"), e.user("队员"), e.user("路人")
	tid := e.tour(withContact("QQ 群 321"))
	r := e.register(tid, e.team("可见队", a, b), a)
	if _, err := e.svc.RegistrationDetail(e.ctx(x), r.ID); err == nil {
		t.Fatal("路人不该看到")
	} else {
		wantErr(t, err, http.StatusNotFound, "")
	}
	pa, err := e.svc.RegistrationDetail(e.ctx(a), r.ID)
	if err != nil || !pa.IsCaptain || !pa.CanWithdraw || pa.ParticipantContact != "QQ 群 321" || len(pa.Roster) != 2 || len(pa.Logs) != 1 {
		t.Fatalf("队长看到：%+v %v", pa, err)
	}
	pb, err := e.svc.RegistrationDetail(e.ctx(b), r.ID)
	if err != nil || pb.IsCaptain || pb.CanWithdraw || pb.ParticipantContact == "" {
		t.Fatalf("队员看到：%+v %v", pb, err)
	}
	// 驳回后：名单上的人仍能看这条报名，但不再占名额，联系方式不给
	e.svc.Reject(e.mgr(), r.ID, "x")
	pb, err = e.svc.RegistrationDetail(e.ctx(b), r.ID)
	if err != nil || pb.ParticipantContact != "" {
		t.Fatalf("驳回后不给联系方式：%+v %v", pb, err)
	}
	// 赛事页：联系方式只给参赛的人和管理员
	page, _ := e.svc.Detail(e.anon(), tid)
	if page.Tournament.ParticipantContact != "" {
		t.Fatal("访客看不到选手联系方式")
	}
	page, _ = e.svc.Detail(e.ctx(x), tid)
	if page.Tournament.ParticipantContact != "" {
		t.Fatal("路人看不到选手联系方式")
	}
	page, _ = e.svc.Detail(e.mgr(), tid)
	if page.Tournament.ParticipantContact == "" {
		t.Fatal("管理员看得到")
	}
}

// 列表分组、草稿对外 404、已通过的队伍公开
func TestListAndDetail(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("队长"), e.user("队员")
	open := e.tour()
	up := e.tour(withWindow(t0.Add(24*time.Hour), t0.Add(48*time.Hour)))
	closed := e.tour(withWindow(t0.Add(-48*time.Hour), t0.Add(-24*time.Hour)))
	fin := e.tour(withStatus(StatusFinished))
	dr := e.tour(withStatus(StatusDraft))
	can := e.tour(withStatus(StatusCancelled))
	r := e.register(open, e.team("公开队", a, b), a)
	e.svc.Approve(e.mgr(), r.ID)

	groups, err := e.svc.List(e.mgr().Context, t0)
	if err != nil {
		t.Fatal(err)
	}
	ids := map[string][]int64{}
	for _, g := range groups {
		for _, c := range g.Tournaments {
			ids[g.Phase] = append(ids[g.Phase], c.ID)
		}
	}
	if len(ids["open"]) != 1 || ids["open"][0] != open || ids["upcoming"][0] != up || ids["closed"][0] != closed || ids["finished"][0] != fin {
		t.Fatalf("分组不对：%v", ids)
	}
	for _, g := range ids {
		for _, id := range g {
			if id == dr || id == can {
				t.Fatalf("草稿和已取消的不进列表：%v", ids)
			}
		}
	}
	if groups[0].Tournaments[0].ApprovedCount != 1 {
		t.Fatalf("已通过的数量：%+v", groups[0].Tournaments[0])
	}
	_, err = e.svc.Detail(e.anon(), dr)
	wantErr(t, err, http.StatusNotFound, "")
	if _, err := e.svc.Detail(e.mgr(), dr); err != nil {
		t.Fatalf("管理员能看草稿：%v", err)
	}
	if _, err := e.svc.Detail(e.anon(), can); err != nil {
		t.Fatalf("已取消的保留详情页：%v", err)
	}
	page, _ := e.svc.Detail(e.ctx(a), open)
	if len(page.ApprovedTeams) != 1 || page.ApprovedTeams[0].MemberCount != 2 || !page.Viewer.RegistrationOpen ||
		len(page.Viewer.CaptainTeams) != 1 || page.Viewer.CaptainTeams[0].Registration == nil {
		t.Fatalf("详情页：%+v", page)
	}
}
