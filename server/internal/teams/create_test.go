package teams

import (
	"net/http"
	"strings"
	"testing"
)

// 契约 R083：队名 2–16 字，不分大小写不能和任何未解散战队重名；唯一索引兜底；解散后名字可再用
func TestTeamNameRules(t *testing.T) {
	e := newEnv(t)
	u := e.user("甲")
	ctx := e.ctx(u, false)

	_, err := e.svc.CreateTeam(ctx, CreateTeamInput{Name: "队"})
	wantField(t, err, "name", "2 到 16")
	_, err = e.svc.CreateTeam(ctx, CreateTeamInput{Name: strings.Repeat("长", 17)})
	wantField(t, err, "name", "2 到 16")
	_, err = e.svc.CreateTeam(ctx, CreateTeamInput{Name: "   "})
	wantField(t, err, "name", "2 到 16")

	// 按字数不按字节：16 个汉字合法
	long, err := e.svc.CreateTeam(ctx, CreateTeamInput{Name: strings.Repeat("长", 16)})
	if err != nil {
		t.Fatalf("16 个汉字应合法：%v", err)
	}
	if long.Name != strings.Repeat("长", 16) {
		t.Fatalf("队名被改了：%q", long.Name)
	}

	alpha := e.team(u, "Alpha")
	v := e.user("乙")
	_, err = e.svc.CreateTeam(e.ctx(v, false), CreateTeamInput{Name: "aLPHA"})
	wantField(t, err, "name", NameTaken)

	// 唯一索引是并发时的兜底：绕过服务直接插同名（大小写不同）的未解散战队要被拒
	_, ierr := e.d.WritePool().Exec(`INSERT INTO teams (name, created_at, updated_at) VALUES ('ALPHA', 'x', 'x')`)
	if ierr == nil {
		t.Fatal("唯一索引应拦住未解散战队的同名（不分大小写）")
	}

	// 解散后名字释放
	if err := e.svc.Disband(e.ctx(u, false), alpha.ID); err != nil {
		t.Fatalf("Disband: %v", err)
	}
	if _, err := e.svc.CreateTeam(e.ctx(v, false), CreateTeamInput{Name: "alpha"}); err != nil {
		t.Fatalf("解散后同名应可再建：%v", err)
	}
}

// 契约 R084：每人每天最多建 3 支战队，表单合法才计数，重名不消耗额度
func TestTeamCreateDailyLimit(t *testing.T) {
	e := newEnv(t)
	e.limits(10, 10) // 把「同时担任队长」的上限放开，单独看每天 3 次
	u := e.user("甲")
	ctx := e.ctx(u, false)
	e.team(u, "第一队")

	for i := 0; i < 6; i++ { // 重名、太短都不应消耗额度
		if _, err := e.svc.CreateTeam(ctx, CreateTeamInput{Name: "第一队"}); err == nil {
			t.Fatal("重名应被拒")
		}
		if _, err := e.svc.CreateTeam(ctx, CreateTeamInput{Name: "短"}); err == nil {
			t.Fatal("太短应被拒")
		}
	}
	e.team(u, "第二队")
	e.team(u, "第三队")
	_, err := e.svc.CreateTeam(ctx, CreateTeamInput{Name: "第四队"})
	wantErr(t, err, http.StatusTooManyRequests, "")

	// 额度按人算，别人不受影响
	w := e.user("乙")
	e.team(w, "乙的队")
}

// 契约 R085：每人最多同时担任 N 支未解散战队的队长（默认 3，全站设置）
func TestCaptainedCap(t *testing.T) {
	e := newEnv(t)
	u := e.user("甲")
	a := e.team(u, "一队")
	e.team(u, "二队")
	e.team(u, "三队")
	_, err := e.svc.CreateTeam(e.ctx(u, false), CreateTeamInput{Name: "四队"})
	wantField(t, err, "__all__", "最多同时担任 3 支")

	// 解散一支，额度空出来
	if err := e.svc.Disband(e.ctx(u, false), a.ID); err != nil {
		t.Fatal(err)
	}
	e.resetCounters() // 每天 3 次的额度另有测试，这里只看同时担任的上限
	e.team(u, "四队")

	// 全站设置改成 1，立刻生效
	e.limits(10, 1)
	_, err = e.svc.CreateTeam(e.ctx(u, false), CreateTeamInput{Name: "五队"})
	wantField(t, err, "__all__", "最多同时担任 1 支")
}

// 契约 R087：改资料只有队长（或超管）；改名同样查重；已解散不能改
func TestOnlyCaptainEditsProfile(t *testing.T) {
	e := newEnv(t)
	cap, member, stranger, admin := e.user("队长"), e.user("队员"), e.user("路人"), e.user("管理")
	team := e.team(cap, "星队")
	e.team(e.user("别人"), "月队")
	e.join(team, cap, member)
	name := "新名字"

	for _, who := range []int64{member, stranger} {
		_, err := e.svc.UpdateTeam(e.ctx(who, false), team.ID, team.Version+1, ProfileChanges{Name: &name})
		wantErr(t, err, http.StatusForbidden, "只有队长")
	}
	v := e.versionOf(team.ID)
	res, err := e.svc.UpdateTeam(e.ctx(cap, false), team.ID, v, ProfileChanges{Name: &name})
	if err != nil || len(res.Saved) != 1 || res.Version != v+1 {
		t.Fatalf("队长改名失败：%+v %v", res, err)
	}
	// 超管可以
	desc := "由超管写的简介"
	if _, err := e.svc.UpdateTeam(e.ctx(admin, true), team.ID, e.versionOf(team.ID), ProfileChanges{Description: &desc}); err != nil {
		t.Fatalf("超管应可改资料：%v", err)
	}
	// 改成别队的名字：只有这个字段报错，别的照存
	taken := "月队"
	contact := "QQ 群 123456"
	res, err = e.svc.UpdateTeam(e.ctx(cap, false), team.ID, e.versionOf(team.ID), ProfileChanges{Name: &taken, MemberContact: &contact})
	if err != nil {
		t.Fatal(err)
	}
	if got := strings.Join(res.Fields["name"], ""); got != NameTaken {
		t.Fatalf("重名应报在 name 上：%v", res.Fields)
	}
	if len(res.Saved) != 1 || res.Saved[0] != "member_contact" {
		t.Fatalf("别的字段应照存：%+v", res)
	}
	if got, _ := e.nameOf(team.ID); got != "新名字" {
		t.Fatalf("重名的改名不该存，现在是 %q", got)
	}
	// 落后的版本号 409
	_, err = e.svc.UpdateTeam(e.ctx(cap, false), team.ID, 1, ProfileChanges{Description: &desc})
	wantErr(t, err, http.StatusConflict, "另一个人刚改过")
	// 没改动不涨版本
	same := "新名字"
	v = e.versionOf(team.ID)
	res, err = e.svc.UpdateTeam(e.ctx(cap, false), team.ID, v, ProfileChanges{Name: &same})
	if err != nil || res.Version != v || len(res.Saved) != 0 {
		t.Fatalf("没改动不该涨版本：%+v %v", res, err)
	}
	// 解散后不能改（队长的成员关系已删，要超管才进得了这一关）
	if err := e.svc.Disband(e.ctx(cap, false), team.ID); err != nil {
		t.Fatal(err)
	}
	_, err = e.svc.UpdateTeam(e.ctx(admin, true), team.ID, e.versionOf(team.ID), ProfileChanges{Description: &desc})
	wantErr(t, err, http.StatusConflict, "已解散")
}

func (e *env) versionOf(id int64) int64 {
	e.t.Helper()
	var v int64
	if err := e.d.ReadPool().QueryRow(`SELECT version FROM teams WHERE id = ?`, id).Scan(&v); err != nil {
		e.t.Fatal(err)
	}
	return v
}

func (e *env) nameOf(id int64) (string, error) {
	var n string
	err := e.d.ReadPool().QueryRow(`SELECT name FROM teams WHERE id = ?`, id).Scan(&n)
	return n, err
}

// 契约 R107：队名和简介每次变更都送审；送审失败只记日志、绝不阻塞操作
func TestModerationNeverBlocks(t *testing.T) {
	e := newEnv(t)
	s := &sink{}
	e.svc.SetModeration(s)
	u := e.user("甲")
	team, err := e.svc.CreateTeam(e.ctx(u, false), CreateTeamInput{Name: "审核队", Description: "我们的简介"})
	if err != nil {
		t.Fatal(err)
	}
	if len(s.got) != 2 || !strings.Contains(s.got[0], "team_name#") || !strings.Contains(s.got[1], "team_description#") {
		t.Fatalf("建队应送审队名和简介：%v", s.got)
	}
	s.got = nil
	nn := "审核队二号"
	if _, err := e.svc.UpdateTeam(e.ctx(u, false), team.ID, team.Version, ProfileChanges{Name: &nn}); err != nil {
		t.Fatal(err)
	}
	if len(s.got) != 1 || !strings.Contains(s.got[0], "审核队二号") {
		t.Fatalf("改名应只送审队名：%v", s.got)
	}
	// 审核服务挂了，操作照样成功
	s.fail = true
	d := "新的简介"
	if _, err := e.svc.UpdateTeam(e.ctx(u, false), team.ID, e.versionOf(team.ID), ProfileChanges{Description: &d}); err != nil {
		t.Fatalf("送审失败不该挡住改资料：%v", err)
	}
	if _, err := e.svc.CreateTeam(e.ctx(e.user("乙"), false), CreateTeamInput{Name: "照样能建"}); err != nil {
		t.Fatalf("送审失败不该挡住建队：%v", err)
	}
}

// 契约 R087：未登录一律 401
func TestUnauthenticatedRefused(t *testing.T) {
	e := newEnv(t)
	_, err := e.svc.CreateTeam(e.anon(), CreateTeamInput{Name: "无名氏的队"})
	wantErr(t, err, http.StatusUnauthorized, "")
	_, err = e.svc.Apply(e.anon(), ApplyInput{TeamID: 1, Roles: []string{"tank"}})
	wantErr(t, err, http.StatusUnauthorized, "")
}
