package teams

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

// 契约 12 号文档 8.1：导入器编号沿用、可重复跑、读旧库不写旧库
func TestImportLegacyTeams(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	legacy, err := sql.Open("sqlite", "file:"+filepath.Join(t.TempDir(), "legacy.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, s := range []string{
		`CREATE TABLE core_sitesettings (id INTEGER, team_max_members INTEGER, team_max_captained INTEGER)`,
		`INSERT INTO core_sitesettings VALUES (1, 12, 2)`,
		`CREATE TABLE teams_team (id INTEGER, name TEXT, description TEXT, logo_id INTEGER, is_recruiting INTEGER,
			recruiting_roles TEXT, member_contact TEXT, disbanded_at TEXT, created_at TEXT, updated_at TEXT)`,
		`INSERT INTO teams_team VALUES (7, '老队', '简介', 999, 1, 'tank,damage', 'QQ 1', NULL, '2026-05-01 10:00:00.123456', '2026-06-01 10:00:00')`,
		`INSERT INTO teams_team VALUES (8, '散了的队', '', NULL, 0, '', '', '2026-07-01 00:00:00', '2026-05-02 10:00:00', '2026-07-01 00:00:00')`,
		`CREATE TABLE teams_teammembership (id INTEGER, team_id INTEGER, user_id INTEGER, role TEXT, joined_at TEXT)`,
		`INSERT INTO teams_teammembership VALUES (3, 7, ` + itoa(a) + `, 'captain', '2026-05-01 10:00:00')`,
		`CREATE TABLE teams_teamapplication (id INTEGER, team_id INTEGER, applicant_id INTEGER, role_tank INTEGER,
			role_damage INTEGER, role_support INTEGER, message TEXT, status TEXT, decided_by_id INTEGER,
			decided_at TEXT, decision_note TEXT, captain_reminded_at TEXT, created_at TEXT)`,
		`INSERT INTO teams_teamapplication VALUES (5, 7, ` + itoa(b) + `, 1, 0, 1, '带我', 'rejected', ` + itoa(a) + `, '2026-05-03 00:00:00', '满了', NULL, '2026-05-02 00:00:00')`,
		`CREATE TABLE teams_teamalumnus (id INTEGER, team_id INTEGER, user_id INTEGER, role TEXT, joined_at TEXT, left_at TEXT, reason TEXT)`,
		`INSERT INTO teams_teamalumnus VALUES (2, 7, ` + itoa(b) + `, 'member', '2026-05-02 00:00:00', '2026-05-20 00:00:00', 'left')`,
	} {
		if _, err := legacy.Exec(s); err != nil {
			t.Fatalf("%s: %v", s, err)
		}
	}
	for i := 0; i < 2; i++ { // 反复导入结果一样
		if err := ImportLegacyTeams(context.Background(), e.d, legacy); err != nil {
			t.Fatalf("第 %d 次导入：%v", i+1, err)
		}
	}
	tm, err := e.svc.store.GetTeam(context.Background(), e.d.ReadPool(), 7)
	if err != nil || tm == nil || tm.Name != "老队" || tm.MemberContact != "QQ 1" || len(tm.RecruitingRoles) != 2 {
		t.Fatalf("战队 7：%+v %v", tm, err)
	}
	if tm.LogoImageID != nil {
		t.Fatal("指向不存在图片的队标该置空，不能让外键失败")
	}
	if tm.CreatedAt.Format("2006-01-02T15:04:05.000000Z") != "2026-05-01T10:00:00.123456Z" {
		t.Fatalf("时间没按 UTC 沿用：%v", tm.CreatedAt)
	}
	if t8, _ := e.svc.store.GetTeam(context.Background(), e.d.ReadPool(), 8); t8 == nil || t8.DisbandedAt == nil {
		t.Fatalf("解散状态要保留：%+v", t8)
	}
	lim, _ := e.svc.store.GetLimits(context.Background(), e.d.ReadPool())
	if lim.MaxMembers != 12 || lim.MaxCaptained != 2 {
		t.Fatalf("全站设置里的上限要带过来：%+v", lim)
	}
	if e.count(`SELECT COUNT(*) FROM team_memberships`) != 1 || e.count(`SELECT COUNT(*) FROM team_applications WHERE id = 5 AND status = 'rejected' AND decision_note = '满了'`) != 1 ||
		e.count(`SELECT COUNT(*) FROM team_alumni WHERE id = 2 AND reason = 'left'`) != 1 {
		t.Fatal("成员、申请、退役记录没原样导入")
	}
	// 新建的战队编号接在导入的后面，不撞车
	c := e.user("丙")
	nt, err := e.svc.CreateTeam(e.ctx(c, false), CreateTeamInput{Name: "新队"})
	if err != nil || nt.ID <= 8 {
		t.Fatalf("新队编号应大于导入的最大编号：%+v %v", nt, err)
	}
}
