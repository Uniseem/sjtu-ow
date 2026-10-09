package teams

import (
	"bytes"
	"context"
	"net/http"
	"os"
	"strings"
	"testing"
)

// 契约 R097、R098：队长不能直接退出；队员退出写退役记录；重新入队删退役记录
func TestLeaveAndAlumni(t *testing.T) {
	e := newEnv(t)
	cap, m := e.user("队长"), e.user("队员")
	team := e.team(cap, "进出队")
	e.join(team, cap, m)

	wantErr(t, e.svc.Leave(e.ctx(cap, false), team.ID), http.StatusConflict, "队长不能直接退出")
	wantErr(t, e.svc.Leave(e.ctx(e.user("路人"), false), team.ID), http.StatusConflict, "不是这支战队的成员")

	if err := e.svc.Leave(e.ctx(m, false), team.ID); err != nil {
		t.Fatal(err)
	}
	if e.role(team.ID, m) != "" {
		t.Fatal("退出后不该还在队里")
	}
	var reason, role string
	if err := e.d.ReadPool().QueryRow(`SELECT reason, role FROM team_alumni WHERE team_id = ? AND user_id = ?`, team.ID, m).Scan(&reason, &role); err != nil {
		t.Fatalf("应写入退役记录：%v", err)
	}
	if reason != LeaveLeft || role != RoleMember {
		t.Fatalf("退役记录不对：%s %s", reason, role)
	}
	// 再被移除再覆盖，不重复
	e.join(team, cap, m)
	if e.count(`SELECT COUNT(*) FROM team_alumni WHERE user_id = ?`, m) != 0 {
		t.Fatal("重新入队应删退役记录")
	}
	if err := e.svc.RemoveMember(e.ctx(cap, false), team.ID, m); err != nil {
		t.Fatal(err)
	}
	if err := e.svc.Leave(e.ctx(e.user("另一人"), false), team.ID); err == nil {
		t.Fatal("非成员退出应失败")
	}
	if e.count(`SELECT COUNT(*) FROM team_alumni WHERE user_id = ? AND reason = 'removed'`, m) != 1 {
		t.Fatal("被移除应写 removed 的退役记录")
	}
}

// 契约 R099：队员退出时，若仍留在已提交的赛事报名名单里，邮件告知队长哪些名单还留着
func TestLeaveMailListsRosters(t *testing.T) {
	e := newEnv(t)
	cap, m := e.user("队长"), e.user("队员")
	team := e.team(cap, "名单队")
	e.join(team, cap, m)
	g := &guard{listing: []ListedEntry{{Title: "春季赛", DetailURL: "/registrations/7/"}}}
	e.svc.SetRosterGuard(g)
	e.exec(`DELETE FROM jobs`)
	if err := e.svc.Leave(e.ctx(m, false), team.ID); err != nil {
		t.Fatal(err)
	}
	got := e.mailsTo(email(cap))
	if len(got) != 1 || !strings.Contains(got[0], "还在报名名单里") || !strings.Contains(got[0], "春季赛") ||
		!strings.Contains(got[0], "/registrations/7/") {
		t.Fatalf("队长应收到带名单的退队信：%v", got)
	}
	// 没有名单时是普通退队信，不带这一项
	m2 := e.user("队员二")
	e.join(team, cap, m2)
	g.listing = nil
	e.exec(`DELETE FROM jobs`)
	if err := e.svc.Leave(e.ctx(m2, false), team.ID); err != nil {
		t.Fatal(err)
	}
	got = e.mailsTo(email(cap))
	if len(got) != 1 || strings.Contains(got[0], "还在报名名单里") {
		t.Fatalf("没有名单就不该提：%v", got)
	}
}

// 契约 R100：不能移除自己；不能移除队长（超管也不行）
func TestRemoveMemberRules(t *testing.T) {
	e := newEnv(t)
	cap, m, other, admin := e.user("队长"), e.user("队员"), e.user("旁人"), e.user("超管")
	team := e.team(cap, "移除队")
	e.join(team, cap, m)

	wantErr(t, e.svc.RemoveMember(e.ctx(cap, false), team.ID, cap), http.StatusConflict, "不能移除自己")
	wantErr(t, e.svc.RemoveMember(e.ctx(admin, true), team.ID, cap), http.StatusConflict, "不能移除队长")
	wantErr(t, e.svc.RemoveMember(e.ctx(cap, false), team.ID, other), http.StatusConflict, "不是战队成员")
	wantErr(t, e.svc.RemoveMember(e.ctx(m, false), team.ID, cap), http.StatusForbidden, "只有队长")
	e.exec(`DELETE FROM jobs`)
	if err := e.svc.RemoveMember(e.ctx(admin, true), team.ID, m); err != nil {
		t.Fatalf("超管可以移除队员：%v", err)
	}
	if got := e.mailsTo(email(m)); len(got) != 1 || !strings.Contains(got[0], "你已被移出战队") {
		t.Fatalf("被移除的人应收到信：%v", got)
	}
}

// 契约 R101：退役记录只有本人、该队队长或超管能删
func TestRemoveAlumnusPermission(t *testing.T) {
	e := newEnv(t)
	cap, other, admin := e.user("队长"), e.user("旁人"), e.user("超管")
	team := e.team(cap, "退役队")
	mk := func(name string) (int64, int64) {
		u := e.user(name)
		e.join(team, cap, u)
		if err := e.svc.Leave(e.ctx(u, false), team.ID); err != nil {
			t.Fatal(err)
		}
		var id int64
		if err := e.d.ReadPool().QueryRow(`SELECT id FROM team_alumni WHERE user_id = ?`, u).Scan(&id); err != nil {
			t.Fatal(err)
		}
		return u, id
	}
	u1, id1 := mk("退一")
	_, id2 := mk("退二")
	_, id3 := mk("退三")

	wantErr(t, e.svc.RemoveAlumnus(e.ctx(other, false), id1), http.StatusForbidden, "只有本人或队长")
	if err := e.svc.RemoveAlumnus(e.ctx(u1, false), id1); err != nil {
		t.Fatalf("本人可以删：%v", err)
	}
	if err := e.svc.RemoveAlumnus(e.ctx(cap, false), id2); err != nil {
		t.Fatalf("队长可以删：%v", err)
	}
	if err := e.svc.RemoveAlumnus(e.ctx(admin, true), id3); err != nil {
		t.Fatalf("超管可以删：%v", err)
	}
	if e.count(`SELECT COUNT(*) FROM team_alumni`) != 0 {
		t.Fatal("三条都该删掉")
	}
}

// 契约 R102：转让队长只能给现有成员；不能给停用账号；对方担任队长数达上限则拒绝
func TestTransferCaptain(t *testing.T) {
	e := newEnv(t)
	cap, m, outsider := e.user("队长"), e.user("队员"), e.user("外人")
	team := e.team(cap, "传承队")
	e.join(team, cap, m)

	wantErr(t, e.svc.TransferCaptain(e.ctx(m, false), team.ID, m), http.StatusForbidden, "只有队长")
	wantErr(t, e.svc.TransferCaptain(e.ctx(cap, false), team.ID, outsider), http.StatusConflict, "只能转让给现有成员")
	wantErr(t, e.svc.TransferCaptain(e.ctx(cap, false), team.ID, cap), http.StatusConflict, "已经是队长")

	e.deactivate(m)
	wantErr(t, e.svc.TransferCaptain(e.ctx(cap, false), team.ID, m), http.StatusConflict, "已停用")
	e.exec(`UPDATE users SET is_active = 1 WHERE id = ?`, m)

	// 对方已经是 3 支队的队长
	for _, n := range []string{"甲队", "乙队", "丙队"} {
		e.team(m, n)
	}
	wantErr(t, e.svc.TransferCaptain(e.ctx(cap, false), team.ID, m), http.StatusConflict, "已达上限")
	e.limits(10, 4)

	e.exec(`DELETE FROM jobs`)
	if err := e.svc.TransferCaptain(e.ctx(cap, false), team.ID, m); err != nil {
		t.Fatal(err)
	}
	if e.role(team.ID, m) != RoleCaptain || e.role(team.ID, cap) != RoleMember {
		t.Fatalf("身份没换：%s / %s", e.role(team.ID, m), e.role(team.ID, cap))
	}
	if e.count(`SELECT COUNT(*) FROM team_memberships WHERE team_id = ? AND role = 'captain'`, team.ID) != 1 {
		t.Fatal("每队有且只有一个队长")
	}
	if got := e.mailsTo(email(m)); len(got) != 1 || !strings.Contains(got[0], "你已成为队长") {
		t.Fatalf("新队长应收到信：%v", got)
	}
}

// 契约 R103：超管指定队长；非超管不可；已解散不可；停用账号不可；目标不在队时先入队，满员则拒绝，整个流程一个事务
func TestAssignCaptain(t *testing.T) {
	e := newEnv(t)
	cap, outsider, admin := e.user("队长"), e.user("外人"), e.user("超管")
	team := e.team(cap, "救援队")

	wantErr(t, e.svc.AssignCaptain(e.ctx(cap, false), team.ID, outsider), http.StatusForbidden, "只有超级管理员")
	e.deactivate(outsider)
	wantErr(t, e.svc.AssignCaptain(e.ctx(admin, true), team.ID, outsider), http.StatusConflict, "已停用")
	e.exec(`UPDATE users SET is_active = 1 WHERE id = ?`, outsider)

	// 目标在别处已是 3 支队的队长：转让会被拒，刚入的队要一起回滚
	for _, n := range []string{"甲队", "乙队", "丙队"} {
		e.team(outsider, n)
	}
	wantErr(t, e.svc.AssignCaptain(e.ctx(admin, true), team.ID, outsider), http.StatusConflict, "已达上限")
	if e.role(team.ID, outsider) != "" {
		t.Fatal("被拒时不该留下一个刚入队的人（216 T4）")
	}
	e.limits(10, 4)

	// 满员时不能先入队
	e.limits(1, 4)
	wantErr(t, e.svc.AssignCaptain(e.ctx(admin, true), team.ID, outsider), http.StatusConflict, "战队人数已满")
	e.limits(10, 4)

	if err := e.svc.AssignCaptain(e.ctx(admin, true), team.ID, outsider); err != nil {
		t.Fatal(err)
	}
	if e.role(team.ID, outsider) != RoleCaptain || e.role(team.ID, cap) != RoleMember {
		t.Fatal("指定后外人该是队长，原队长降为队员")
	}

	// 已解散
	if err := e.svc.Disband(e.ctx(admin, true), team.ID); err != nil {
		t.Fatal(err)
	}
	wantErr(t, e.svc.AssignCaptain(e.ctx(admin, true), team.ID, cap), http.StatusConflict, "已经解散")
}

// 契约 R104、R105：有进行中的报名不能解散；解散置时间、删成员关系、取消待审申请、通知全体成员、不写退役记录
func TestDisband(t *testing.T) {
	e := newEnv(t)
	cap, m, applicant := e.user("队长"), e.user("队员"), e.user("申请人")
	team := e.team(cap, "解散队")
	e.join(team, cap, m)
	app1, err := e.svc.Apply(e.ctx(applicant, false), ApplyInput{TeamID: team.ID, Roles: []string{"tank"}})
	if err != nil {
		t.Fatal(err)
	}

	g := &guard{live: []string{"春季赛"}}
	e.svc.SetRosterGuard(g)
	wantErr(t, e.svc.Disband(e.ctx(cap, false), team.ID), http.StatusConflict, "还在赛事「春季赛」的报名里")
	wantErr(t, e.svc.Disband(e.ctx(m, false), team.ID), http.StatusForbidden, "只有队长或超级管理员")
	if e.count(`SELECT COUNT(*) FROM teams WHERE id = ? AND disbanded_at IS NULL`, team.ID) != 1 {
		t.Fatal("被拦下就不该解散")
	}

	g.live = nil
	e.exec(`DELETE FROM jobs`)
	if err := e.svc.Disband(e.ctx(cap, false), team.ID); err != nil {
		t.Fatal(err)
	}
	if e.count(`SELECT COUNT(*) FROM team_memberships WHERE team_id = ?`, team.ID) != 0 {
		t.Fatal("成员关系应全部删除")
	}
	if e.appStatus(app1.ID) != StatusCancelled {
		t.Fatal("待审申请应取消")
	}
	if e.count(`SELECT COUNT(*) FROM team_applications WHERE id = ? AND decision_note = '战队已解散'`, app1.ID) != 1 {
		t.Fatal("取消原因应写「战队已解散」")
	}
	if e.count(`SELECT COUNT(*) FROM team_alumni`) != 0 {
		t.Fatal("解散不写退役记录")
	}
	for _, u := range []int64{cap, m} {
		if got := e.mailsTo(email(u)); len(got) != 1 || !strings.Contains(got[0], "战队已解散") {
			t.Fatalf("成员 %d 应收到解散通知：%v", u, got)
		}
	}
	wantErr(t, e.svc.Disband(e.ctx(e.user("超管"), true), team.ID), http.StatusConflict, "已经解散")
	// 解散后详情页还看得见，只是没有成员和退役名单；列表里没有
	page, err := e.svc.Detail(e.anon(), team.ID)
	if err != nil || page.Team.DisbandedAt == nil || len(page.Members) != 0 || len(page.Alumni) != 0 {
		t.Fatalf("解散后详情：%+v %v", page, err)
	}
	list, _ := e.svc.List(context.Background(), ListInput{})
	if list.TeamTotal != 0 {
		t.Fatalf("解散的队不该在列表里：%+v", list)
	}
}

// 契约 R106：队标仅 JPG/PNG/WebP、≤5MB；只能用自己传到「队标」集合里的图；建队失败时刚传的队标立即删除；换掉的队标随之清理
func TestLogoRules(t *testing.T) {
	e := newEnv(t)
	u, w := e.user("甲"), e.user("乙")
	png := pngBytes(t)

	up := func(who int64, name string) (int64, error) {
		img, err := e.svc.UploadLogo(e.ctx(who, false), UploadLogoInput{FileName: name, FileSize: int64(len(png)), Reader: bytes.NewReader(png)})
		if err != nil {
			return 0, err
		}
		return img.ID, nil
	}
	_, err := e.svc.UploadLogo(e.ctx(u, false), UploadLogoInput{FileName: "a.png", FileSize: 5*1024*1024 + 1, Reader: bytes.NewReader(png)})
	wantField(t, err, "logo", "5MB")
	_, err = up(u, "a.gif")
	wantField(t, err, "logo", "JPG、PNG 或 WebP")
	_, err = up(u, "a.exe")
	wantField(t, err, "logo", "JPG、PNG 或 WebP")

	id1, err := up(u, "logo.PNG")
	if err != nil {
		t.Fatalf("PNG 应可上传：%v", err)
	}
	if e.count(`SELECT COUNT(*) FROM images i JOIN image_collections c ON c.id = i.collection_id WHERE i.id = ? AND c.key = 'team_logo'`, id1) != 1 {
		t.Fatal("队标应在「队标」集合里")
	}
	// 别人的图、不在队标集合的图都不能当队标
	idOther, _ := up(w, "他的.png")
	_, err = e.svc.CreateTeam(e.ctx(u, false), CreateTeamInput{Name: "偷图队", LogoImageID: &idOther})
	wantField(t, err, "logo_image_id", "自己上传")
	e.exec(`UPDATE images SET collection_id = 1 WHERE id = ?`, id1)
	_, err = e.svc.CreateTeam(e.ctx(u, false), CreateTeamInput{Name: "错集合队", LogoImageID: &id1})
	wantField(t, err, "logo_image_id", "队标上传入口")
	e.exec(`UPDATE images SET collection_id = 5 WHERE id = ?`, id1)

	team, err := e.svc.CreateTeam(e.ctx(u, false), CreateTeamInput{Name: "有标队", LogoImageID: &id1})
	if err != nil || team.LogoImageID == nil || *team.LogoImageID != id1 {
		t.Fatalf("建队带队标失败：%+v %v", team, err)
	}
	// 建队失败（重名）：刚传的队标立即删除。重名在校验阶段就拦下，所以直接验证清理函数的口径：
	// 没有战队再用的队标集合里的图才删
	id2, _ := up(u, "换标.png")
	if _, err := e.svc.UpdateTeam(e.ctx(u, false), team.ID, e.versionOf(team.ID), ProfileChanges{LogoImageID: &id2}); err != nil {
		t.Fatal(err)
	}
	if e.count(`SELECT COUNT(*) FROM images WHERE id = ?`, id1) != 0 {
		t.Fatal("换掉的队标应连图删除")
	}
	if _, err := os.Stat(e.med.MasterPath(id1)); !os.IsNotExist(err) {
		t.Fatalf("母版文件也该删：%v", err)
	}
	rm := true
	if _, err := e.svc.UpdateTeam(e.ctx(u, false), team.ID, e.versionOf(team.ID), ProfileChanges{RemoveLogo: &rm}); err != nil {
		t.Fatal(err)
	}
	if e.count(`SELECT COUNT(*) FROM images WHERE id = ?`, id2) != 0 {
		t.Fatal("删除队标应连图删除")
	}
	// 别的集合里的图（编辑从图片库挑的）不归战队删
	e.exec(`UPDATE images SET collection_id = 1 WHERE id = ?`, idOther)
	e.svc.discardLogo(e.ctx(w, false), idOther)
	if e.count(`SELECT COUNT(*) FROM images WHERE id = ?`, idOther) != 1 {
		t.Fatal("不在队标集合的图不该被战队删掉")
	}
}

// 设计 7.1：队内联系方式只有本队成员和超管看得到
func TestMemberContactVisibility(t *testing.T) {
	e := newEnv(t)
	cap, m, stranger, admin := e.user("队长"), e.user("队员"), e.user("路人"), e.user("超管")
	team := e.team(cap, "私密队")
	e.join(team, cap, m)
	c := "QQ 群 5566"
	if _, err := e.svc.UpdateTeam(e.ctx(cap, false), team.ID, e.versionOf(team.ID), ProfileChanges{MemberContact: &c}); err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		name string
		ctx  func() (string, error)
		want bool
	}{
		{"访客", func() (string, error) { p, err := e.svc.Detail(e.anon(), team.ID); return p.Team.MemberContact, err }, false},
		{"路人", func() (string, error) {
			p, err := e.svc.Detail(e.ctx(stranger, false), team.ID)
			return p.Team.MemberContact, err
		}, false},
		{"队员", func() (string, error) {
			p, err := e.svc.Detail(e.ctx(m, false), team.ID)
			return p.Team.MemberContact, err
		}, true},
		{"超管", func() (string, error) {
			p, err := e.svc.Detail(e.ctx(admin, true), team.ID)
			return p.Team.MemberContact, err
		}, true},
	}
	for _, c := range cases {
		got, err := c.ctx()
		if err != nil {
			t.Fatal(err)
		}
		if (got != "") != c.want {
			t.Fatalf("%s 看到的联系方式 %q，应有=%v", c.name, got, c.want)
		}
	}
}

// 契约 R108：队长账号停用的战队进入「无队长战队」名单：不能收申请，超管后台列出
func TestTeamsWithoutCaptain(t *testing.T) {
	e := newEnv(t)
	cap, other, admin := e.user("队长"), e.user("另一队长"), e.user("超管")
	stopped := e.team(cap, "卡壳队")
	fine := e.team(other, "正常队")
	e.deactivate(cap)

	rows, err := e.svc.AdminList(e.ctx(admin, true))
	if err != nil {
		t.Fatal(err)
	}
	flags := map[int64]bool{}
	for _, r := range rows {
		flags[r.ID] = r.NoCaptain
	}
	if !flags[stopped.ID] || flags[fine.ID] {
		t.Fatalf("无队长战队名单不对：%+v", flags)
	}
	_, err = e.svc.Apply(e.ctx(e.user("申请人"), false), ApplyInput{TeamID: stopped.ID, Roles: []string{"tank"}})
	wantErr(t, err, http.StatusConflict, "队长账号已停用")
	// 超管指定新队长后恢复
	m := e.user("新队长")
	if err := e.svc.AssignCaptain(e.ctx(admin, true), stopped.ID, m); err != nil {
		t.Fatal(err)
	}
	if _, err := e.svc.Apply(e.ctx(e.user("申请人二"), false), ApplyInput{TeamID: stopped.ID, Roles: []string{"tank"}}); err != nil {
		t.Fatalf("有了新队长应能再申请：%v", err)
	}
}

// 列表与筛选：缺某位置、只看招募中（设计 7.6）；满员的不算「能申请」
func TestListFilters(t *testing.T) {
	e := newEnv(t)
	e.limits(2, 10)
	a, b, c, d := e.user("甲"), e.user("乙"), e.user("丙"), e.user("丁")
	t1 := e.team(a, "缺坦克")
	t2 := e.team(b, "缺支援")
	t3 := e.team(c, "不招募")
	e.team(d, "任意位置")
	roles1, roles2, off := []string{"tank"}, []string{"support"}, false
	e.svc.UpdateTeam(e.ctx(a, false), t1.ID, e.versionOf(t1.ID), ProfileChanges{RecruitingRoles: &roles1})
	e.svc.UpdateTeam(e.ctx(b, false), t2.ID, e.versionOf(t2.ID), ProfileChanges{RecruitingRoles: &roles2})
	e.svc.UpdateTeam(e.ctx(c, false), t3.ID, e.versionOf(t3.ID), ProfileChanges{IsRecruiting: &off})
	// 缺支援的队满员
	e.join(t2, b, e.user("戊"))

	all, _ := e.svc.List(context.Background(), ListInput{})
	if all.TeamTotal != 4 || all.RecruitingTotal != 3 || len(all.Teams) != 4 {
		t.Fatalf("总数不对：%+v", all)
	}
	if all.RoleCounts["tank"] != 2 || all.RoleCounts["support"] != 1 || all.RoleCounts["damage"] != 1 {
		t.Fatalf("各位置能申请的队数不对（满员的和不招募的不算）：%v", all.RoleCounts)
	}
	rec, _ := e.svc.List(context.Background(), ListInput{RecruitingOnly: true})
	if len(rec.Teams) != 3 {
		t.Fatalf("只看招募中应有 3 支：%d", len(rec.Teams))
	}
	tank, _ := e.svc.List(context.Background(), ListInput{Role: "tank"})
	if len(tank.Teams) != 2 || tank.RecruitingOnly {
		t.Fatalf("缺坦克：%+v", tank)
	}
	bad, _ := e.svc.List(context.Background(), ListInput{Role: "sniper"})
	if bad.Role != "" || len(bad.Teams) != 4 {
		t.Fatalf("不认识的位置当没筛：%+v", bad)
	}
}
