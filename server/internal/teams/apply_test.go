package teams

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// 契约 R086：战队人数上限 = 全站设置；满员不能申请、也不能再通过
func TestTeamMemberCap(t *testing.T) {
	e := newEnv(t)
	e.limits(2, 3)
	cap, a, b, c := e.user("队长"), e.user("甲"), e.user("乙"), e.user("丙")
	team := e.team(cap, "满员队")
	e.join(team, cap, a) // 现在 2 人，满了
	_, err := e.svc.Apply(e.ctx(b, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	wantErr(t, err, http.StatusConflict, "战队人数已满")

	// 满员前就递上的两条申请：第一条通过后第二条通过不了（R092）
	e.limits(3, 3)
	appB, err := e.svc.Apply(e.ctx(b, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	if err != nil {
		t.Fatal(err)
	}
	appC, err := e.svc.Apply(e.ctx(c, false), ApplyInput{TeamID: team.ID, Roles: []string{"support"}})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := e.svc.Approve(e.ctx(cap, false), appB.ID); err != nil {
		t.Fatal(err)
	}
	_, err = e.svc.Approve(e.ctx(cap, false), appC.ID)
	wantErr(t, err, http.StatusConflict, "战队人数已满，无法通过")
	if st := e.appStatus(appC.ID); st != StatusPending {
		t.Fatalf("满员拒绝通过，申请应仍待审，现在是 %s", st)
	}
}

func (e *env) appStatus(id int64) string {
	e.t.Helper()
	var s string
	if err := e.d.ReadPool().QueryRow(`SELECT status FROM team_applications WHERE id = ?`, id).Scan(&s); err != nil {
		e.t.Fatal(err)
	}
	return s
}

// 契约 R088：可申请条件逐条
func TestApplyConditions(t *testing.T) {
	e := newEnv(t)
	cap := e.user("队长")
	team := e.team(cap, "招募队")
	apply := func(u int64) error {
		_, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"damage"}})
		return err
	}

	// 未登录
	_, err := e.svc.Apply(e.anon(), ApplyInput{TeamID: team.ID, Roles: []string{"damage"}})
	wantErr(t, err, http.StatusUnauthorized, "")

	// 没有游戏 ID
	wantErr(t, apply(e.bare("无号")), http.StatusConflict, "至少一个游戏 ID")

	// 已是成员（队长自己）
	wantErr(t, apply(cap), http.StatusConflict, "已经是这支战队的成员")

	// 功能被单人规则禁用：固定文案，不说原因（规则 12）
	banned := e.ctx(e.user("被禁"), false)
	banned.Viewer.FeatureDenied = map[app.Feature]struct{}{accounts.FeatureTeamApply: {}}
	_, err = e.svc.Apply(banned, ApplyInput{TeamID: team.ID, Roles: []string{"damage"}})
	wantErr(t, err, http.StatusConflict, accounts.FeatureDeniedMessage)

	// 不招募
	off := false
	if _, err := e.svc.UpdateTeam(e.ctx(cap, false), team.ID, e.versionOf(team.ID), ProfileChanges{IsRecruiting: &off}); err != nil {
		t.Fatal(err)
	}
	wantErr(t, apply(e.user("丁")), http.StatusConflict, "暂时不招募")
	on := true
	if _, err := e.svc.UpdateTeam(e.ctx(cap, false), team.ID, e.versionOf(team.ID), ProfileChanges{IsRecruiting: &on}); err != nil {
		t.Fatal(err)
	}

	// 已有待审申请
	u := e.user("戊")
	if err := apply(u); err != nil {
		t.Fatalf("条件都满足应能申请：%v", err)
	}
	wantErr(t, apply(u), http.StatusConflict, "还有一条待审批")

	// 队长账号停用：无队长战队不能收申请（规则 108）
	e.deactivate(cap)
	wantErr(t, apply(e.user("己")), http.StatusConflict, "队长账号已停用")

	// 已解散
	cap2 := e.user("队长二")
	t2 := e.team(cap2, "散伙队")
	if err := e.svc.Disband(e.ctx(cap2, false), t2.ID); err != nil {
		t.Fatal(err)
	}
	_, err = e.svc.Apply(e.ctx(e.user("庚"), false), ApplyInput{TeamID: t2.ID, Roles: []string{"tank"}})
	wantErr(t, err, http.StatusConflict, "战队已解散")
}

// 契约 R089：申请限流 20 次/天/人
func TestApplyDailyLimit(t *testing.T) {
	e := newEnv(t)
	e.limits(10, 30)
	u := e.user("勤奋")
	boss := e.user("队长")
	var teams []*Team
	for i := 0; i < 21; i++ {
		teams = append(teams, e.team(boss, fmt.Sprintf("申请队%02d", i)))
		if i%3 == 2 {
			e.resetCounters() // 建队每天 3 次的额度和这条测试无关
		}
	}
	for i := 0; i < 20; i++ {
		if _, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: teams[i].ID, Roles: []string{"tank"}}); err != nil {
			t.Fatalf("第 %d 次申请应成功：%v", i+1, err)
		}
	}
	_, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: teams[20].ID, Roles: []string{"tank"}})
	wantErr(t, err, http.StatusTooManyRequests, "")
}

// 契约 R090：意向位置至少一个；留言 ≤200 字；有留言才送审
func TestApplyInputAndModeration(t *testing.T) {
	e := newEnv(t)
	s := &sink{}
	e.svc.SetModeration(s)
	cap, u := e.user("队长"), e.user("申请人")
	team := e.team(cap, "审核申请队")
	s.got = nil

	_, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID})
	wantField(t, err, "roles", "至少选择一个")
	_, err = e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"sniper"}})
	wantField(t, err, "roles", "至少选择一个")
	_, err = e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}, Message: strings.Repeat("话", 201)})
	wantField(t, err, "message", "最多 200")

	// 恰好 200 字合法，并且送审；送审失败不挡申请
	s.fail = true
	a, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank", "support"}, Message: strings.Repeat("话", 200)})
	if err != nil {
		t.Fatalf("200 字留言应合法：%v", err)
	}
	if len(s.got) != 1 || !strings.HasPrefix(s.got[0], fmt.Sprintf("application_message#%d:message=", a.ID)) {
		t.Fatalf("有留言应送审：%v", s.got)
	}
	if !a.RoleTank || a.RoleDamage || !a.RoleSupport {
		t.Fatalf("位置没存对：%+v", a)
	}
	// 没留言不送审
	s.got = nil
	u2 := e.user("申请人二")
	if _, err := e.svc.Apply(e.ctx(u2, false), ApplyInput{TeamID: team.ID, Roles: []string{"damage"}}); err != nil {
		t.Fatal(err)
	}
	if len(s.got) != 0 {
		t.Fatalf("没留言不该送审：%v", s.got)
	}
}

// 契约 R091：提交申请后邮件通知队长
func TestApplyMailsCaptain(t *testing.T) {
	e := newEnv(t)
	cap, u := e.user("队长"), e.user("申请人")
	team := e.team(cap, "来信队")
	if _, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}, Message: "带我一个"}); err != nil {
		t.Fatal(err)
	}
	got := e.mailsTo(email(cap))
	if len(got) != 1 || !strings.Contains(got[0], "新的入队申请：来信队") || !strings.Contains(got[0], "带我一个") {
		t.Fatalf("队长应收到一封申请通知：%v", got)
	}
	if len(e.mailsTo(email(u))) != 0 {
		t.Fatal("申请人自己不该收到信")
	}
}

// 契约 R092、R093：通过时在写事务内重新检查；通过后建成员、删退役记录、发带联系方式的信
func TestApproveRechecksAndEffects(t *testing.T) {
	e := newEnv(t)
	cap, u := e.user("队长"), e.user("申请人")
	team := e.team(cap, "审批队")
	contact := "QQ 群 99887766"
	if _, err := e.svc.UpdateTeam(e.ctx(cap, false), team.ID, e.versionOf(team.ID), ProfileChanges{MemberContact: &contact}); err != nil {
		t.Fatal(err)
	}

	// 申请人注销/停用：申请自动取消并报错，取消要落库（不随报错回滚）
	gone := e.user("跑路")
	a1, err := e.svc.Apply(e.ctx(gone, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	if err != nil {
		t.Fatal(err)
	}
	e.deactivate(gone)
	_, err = e.svc.Approve(e.ctx(cap, false), a1.ID)
	wantErr(t, err, http.StatusConflict, "已注销或停用")
	if e.appStatus(a1.ID) != StatusCancelled {
		t.Fatal("停用的申请人，申请应已被关闭")
	}
	if e.role(team.ID, gone) != "" {
		t.Fatal("停用的人不该进队")
	}

	// 已经是成员：申请自动取消、报错，不回滚
	dup := e.user("重复")
	a2, err := e.svc.Apply(e.ctx(dup, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	if err != nil {
		t.Fatal(err)
	}
	e.exec(`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (?, ?, 'member', ?)`,
		team.ID, dup, "2026-10-01T00:00:00.000000Z")
	_, err = e.svc.Approve(e.ctx(cap, false), a2.ID)
	wantErr(t, err, http.StatusConflict, "已经是这支战队的成员")
	if e.appStatus(a2.ID) != StatusCancelled {
		t.Fatal("已是成员的申请应被关闭而不是留着待审")
	}

	// 正常通过：有退役记录的话删掉；邮件附队内联系方式
	e.exec(`INSERT INTO team_alumni (team_id, user_id, role, joined_at, left_at, reason) VALUES (?, ?, 'member', ?, ?, 'left')`,
		team.ID, u, "2026-09-01T00:00:00.000000Z", "2026-09-20T00:00:00.000000Z")
	a3, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"support"}})
	if err != nil {
		t.Fatal(err)
	}
	out, err := e.svc.Approve(e.ctx(cap, false), a3.ID)
	if err != nil || out.Status != StatusApproved || out.DecidedBy == nil || *out.DecidedBy != cap {
		t.Fatalf("通过失败：%+v %v", out, err)
	}
	if e.role(team.ID, u) != RoleMember {
		t.Fatal("通过后应成为队员")
	}
	if e.count(`SELECT COUNT(*) FROM team_alumni WHERE team_id = ? AND user_id = ?`, team.ID, u) != 0 {
		t.Fatal("重新入队应删退役记录")
	}
	mails := e.mailsTo(email(u))
	if len(mails) != 1 || !strings.Contains(mails[0], "入队申请已通过") || !strings.Contains(mails[0], contact) {
		t.Fatalf("通过的信应附队内联系方式：%v", mails)
	}
	// 再通过一次：已处理过
	_, err = e.svc.Approve(e.ctx(cap, false), a3.ID)
	wantErr(t, err, http.StatusConflict, "已经处理过")
	// 不是队长不能审批
	a4, _ := e.svc.Apply(e.ctx(e.user("路过"), false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	_, err = e.svc.Approve(e.ctx(u, false), a4.ID)
	wantErr(t, err, http.StatusForbidden, "只有队长")
}

// 契约 R093：拒绝的信写原因；申请人可以撤回自己的申请，别人不行
func TestRejectAndCancel(t *testing.T) {
	e := newEnv(t)
	cap, u, other := e.user("队长"), e.user("申请人"), e.user("旁人")
	team := e.team(cap, "拒绝队")
	a, _ := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	_, err := e.svc.Reject(e.ctx(other, false), RejectInput{ID: a.ID, Note: "x"})
	wantErr(t, err, http.StatusForbidden, "只有队长")
	if _, err := e.svc.Reject(e.ctx(cap, false), RejectInput{ID: a.ID, Note: "位置满了"}); err != nil {
		t.Fatal(err)
	}
	m := e.mailsTo(email(u))
	if len(m) != 1 || !strings.Contains(m[0], "未通过") || !strings.Contains(m[0], "位置满了") {
		t.Fatalf("拒绝信应写原因：%v", m)
	}
	// 撤回
	b, _ := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	_, err = e.svc.Cancel(e.ctx(other, false), b.ID)
	wantErr(t, err, http.StatusForbidden, "只能撤回自己")
	if _, err := e.svc.Cancel(e.ctx(u, false), b.ID); err != nil {
		t.Fatal(err)
	}
	if e.appStatus(b.ID) != StatusCancelled {
		t.Fatal("撤回后应是已取消")
	}
}

// 契约 R094：待审满 7 天给队长发一封汇总提醒，每队一封，只提醒一次
func TestRemindCaptains(t *testing.T) {
	e := newEnv(t)
	cap, a, b, fresh := e.user("队长"), e.user("甲"), e.user("乙"), e.user("新来的")
	team := e.team(cap, "提醒队")
	for _, u := range []int64{a, b} {
		if _, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}}); err != nil {
			t.Fatal(err)
		}
	}
	e.exec(`UPDATE team_applications SET created_at = ?`, db8DaysBefore(t0))
	if _, err := e.svc.Apply(e.ctx(fresh, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}}); err != nil {
		t.Fatal(err)
	}
	e.exec(`DELETE FROM jobs`)

	n, err := e.svc.RemindCaptains(context.Background(), t0)
	if err != nil || n != 1 {
		t.Fatalf("两条旧申请应汇成一封：n=%d err=%v", n, err)
	}
	m := e.mailsTo(email(cap))
	if len(m) != 1 || !strings.Contains(m[0], "有 2 个入队申请") {
		t.Fatalf("汇总信不对：%v", m)
	}
	if n, _ := e.svc.RemindCaptains(context.Background(), t0); n != 0 {
		t.Fatalf("同一批申请只提醒一次，第二次发了 %d 封", n)
	}
	if e.count(`SELECT COUNT(*) FROM team_applications WHERE captain_reminded_at IS NOT NULL`) != 2 {
		t.Fatal("两条旧申请都该记上提醒时间，新的不记")
	}

	// 队长账号停了：不发信，但也记上，免得每晚重试
	cap2, c := e.user("队长二"), e.user("丙")
	t2 := e.team(cap2, "无人队")
	if _, err := e.svc.Apply(e.ctx(c, false), ApplyInput{TeamID: t2.ID, Roles: []string{"tank"}}); err != nil {
		t.Fatal(err)
	}
	e.exec(`UPDATE team_applications SET created_at = ? WHERE team_id = ?`, db8DaysBefore(t0), t2.ID)
	e.deactivate(cap2)
	e.exec(`DELETE FROM jobs`)
	if n, _ := e.svc.RemindCaptains(context.Background(), t0); n != 0 {
		t.Fatalf("停用的队长不该收到信：%d", n)
	}
	if len(e.mails()) != 0 {
		t.Fatal("不该有信")
	}
	if e.count(`SELECT COUNT(*) FROM team_applications WHERE team_id = ? AND captain_reminded_at IS NOT NULL`, t2.ID) != 1 {
		t.Fatal("没发信也要记上提醒时间")
	}
}

func db8DaysBefore(now time.Time) string {
	return now.Add(-8 * 24 * time.Hour).Format("2006-01-02T15:04:05.000000Z")
}

// 契约 R095：待审满 14 天自动关闭并通知申请人
func TestCloseStaleApplications(t *testing.T) {
	e := newEnv(t)
	cap, old, young, gone := e.user("队长"), e.user("久等"), e.user("刚来"), e.user("已停")
	team := e.team(cap, "过期队")
	ids := map[int64]int64{}
	for _, u := range []int64{old, young, gone} {
		a, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
		if err != nil {
			t.Fatal(err)
		}
		ids[u] = a.ID
	}
	e.exec(`UPDATE team_applications SET created_at = ? WHERE id IN (?, ?)`,
		t0.Add(-15*24*time.Hour).Format("2006-01-02T15:04:05.000000Z"), ids[old], ids[gone])
	e.exec(`UPDATE team_applications SET created_at = ? WHERE id = ?`,
		t0.Add(-13*24*time.Hour).Format("2006-01-02T15:04:05.000000Z"), ids[young])
	e.deactivate(gone)
	e.exec(`DELETE FROM jobs`)

	n, err := e.svc.CloseStaleApplications(context.Background(), t0)
	if err != nil || n != 2 {
		t.Fatalf("应关闭 2 条：%d %v", n, err)
	}
	if e.appStatus(ids[old]) != StatusCancelled || e.appStatus(ids[young]) != StatusPending {
		t.Fatal("15 天的关、13 天的不关")
	}
	if e.count(`SELECT COUNT(*) FROM team_applications WHERE id = ? AND decision_note LIKE '队长 14 天没有处理%'`, ids[old]) != 1 {
		t.Fatal("关闭原因应写进申请")
	}
	if len(e.mailsTo(email(old))) != 1 {
		t.Fatal("申请人应收到关闭通知")
	}
	if len(e.mailsTo(email(gone))) != 0 {
		t.Fatal("停用的申请人不发信")
	}
}

// 契约 R096：队长管理页的待审列表不显示停用账号的申请
func TestPendingHidesDeactivatedApplicants(t *testing.T) {
	e := newEnv(t)
	cap, a, b := e.user("队长"), e.user("甲"), e.user("乙")
	team := e.team(cap, "列表队")
	for _, u := range []int64{a, b} {
		if _, err := e.svc.Apply(e.ctx(u, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}}); err != nil {
			t.Fatal(err)
		}
	}
	e.deactivate(b)
	page, err := e.svc.Manage(e.ctx(cap, false), team.ID)
	if err != nil {
		t.Fatal(err)
	}
	if len(page.Pending) != 1 || page.Pending[0].Applicant.UserID != a {
		t.Fatalf("只该看到启用账号的申请：%+v", page.Pending)
	}
	if len(page.Pending[0].GameIDs) != 1 {
		t.Fatalf("队长要能看到申请人的游戏 ID：%+v", page.Pending[0])
	}
	// 非队长看管理页是 404，不暴露它存在
	_, err = e.svc.Manage(e.ctx(a, false), team.ID)
	wantErr(t, err, http.StatusNotFound, "")
}
