package accounts

import (
	"context"
	"strconv"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func execAll(t *testing.T, d *db.DB, stmts ...string) {
	t.Helper()
	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		for _, s := range stmts {
			if _, err := tx.ExecContext(ctx, s); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

func countOf(t *testing.T, d *db.DB, q string, args ...any) int {
	t.Helper()
	var n int
	if err := d.ReadPool().QueryRow(q, args...).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}

// 契约 R029、R031：在任队长不能注销；注销时退出所有战队、删退役记录、撤回待审申请、移出成员分组
func TestDeleteAccountLeavesTeamsAndGroups(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sess := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sess, nil)

	u := newVerifiedUser(t, d, "leaver@sjtu.edu.cn", "离开的人", "Password123!@#", true)
	boss := newVerifiedUser(t, d, "boss@sjtu.edu.cn", "别人的队长", "Password123!@#", true)
	token, _ := sess.Create(ctx, u.ID)
	appCtx := newTestCtx(ctx, u, token, false)

	execAll(t, d,
		`INSERT INTO teams (id, name, created_at, updated_at) VALUES (1, '我的队', 'x', 'x'), (2, '别的队', 'x', 'x'), (3, '待审队', 'x', 'x'), (4, '旧队', 'x', 'x')`,
		`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (1, `+itoa(u.ID)+`, 'captain', 'x'), (2, `+itoa(boss.ID)+`, 'captain', 'x'), (3, `+itoa(boss.ID)+`, 'captain', 'x')`,
		`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (2, `+itoa(u.ID)+`, 'member', 'x')`,
		`INSERT INTO team_alumni (team_id, user_id, role, joined_at, left_at, reason) VALUES (4, `+itoa(u.ID)+`, 'member', 'x', 'x', 'left')`,
		`INSERT INTO team_applications (team_id, applicant_id, role_tank, status, created_at) VALUES (3, `+itoa(u.ID)+`, 1, 'pending', 'x')`,
		`INSERT INTO member_groups (id, name, created_at, updated_at) VALUES (1, '干部', 'x', 'x')`,
		`INSERT INTO member_group_memberships (group_id, user_id) VALUES (1, `+itoa(u.ID)+`)`,
	)

	// 在任队长：拦下，什么都不动
	_, err := svc.DeleteAccount(appCtx, DeleteAccountInput{Password: "Password123!@#"})
	if err == nil || !isInvalid(err) {
		t.Fatalf("在任队长应被拦下：%v", err)
	}
	if countOf(t, d, `SELECT COUNT(*) FROM users WHERE id = ? AND is_active = 1`, u.ID) != 1 {
		t.Fatal("被拦下时账号不该被动")
	}

	// 解散自己的队后可以注销
	execAll(t, d, `UPDATE teams SET disbanded_at = 'x' WHERE id = 1`, `DELETE FROM team_memberships WHERE team_id = 1`)
	if _, err := svc.DeleteAccount(appCtx, DeleteAccountInput{Password: "Password123!@#"}); err != nil {
		t.Fatalf("注销失败：%v", err)
	}
	for q, want := range map[string]int{
		`SELECT COUNT(*) FROM team_memberships WHERE user_id = ?`:                                0,
		`SELECT COUNT(*) FROM team_alumni WHERE user_id = ?`:                                     0,
		`SELECT COUNT(*) FROM member_group_memberships WHERE user_id = ?`:                        0,
		`SELECT COUNT(*) FROM team_applications WHERE applicant_id = ? AND status = 'pending'`:   0,
		`SELECT COUNT(*) FROM team_applications WHERE applicant_id = ? AND status = 'cancelled'`: 1,
	} {
		if got := countOf(t, d, q, u.ID); got != want {
			t.Fatalf("%s = %d，应为 %d", q, got, want)
		}
	}
}

// 契约 R035：停用账号时撤回它的待审申请，并让它任队长的战队停止招募
func TestDeactivateSuspendsTeamActivity(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", auth.NewStore(d, nil), nil)
	cap := newVerifiedUser(t, d, "cap@sjtu.edu.cn", "队长", "Password123!@#", true)
	other := newVerifiedUser(t, d, "other@sjtu.edu.cn", "别队队长", "Password123!@#", true)
	execAll(t, d,
		`INSERT INTO teams (id, name, is_recruiting, created_at, updated_at) VALUES (1, '停招队', 1, 'x', 'x'), (2, '别队', 1, 'x', 'x'), (3, '申请去的队', 1, 'x', 'x')`,
		`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (1, `+itoa(cap.ID)+`, 'captain', 'x'), (2, `+itoa(other.ID)+`, 'captain', 'x'), (3, `+itoa(other.ID)+`, 'captain', 'x')`,
		`INSERT INTO team_applications (team_id, applicant_id, role_tank, status, created_at) VALUES (3, `+itoa(cap.ID)+`, 1, 'pending', 'x')`,
	)
	admin := newTestCtx(ctx, nil, "", true)
	if _, err := svc.DeactivateUser(admin, DeactivateUserInput{ID: api.ID(cap.ID), Reason: "测试"}); err != nil {
		t.Fatal(err)
	}
	if countOf(t, d, `SELECT COUNT(*) FROM teams WHERE id = 1 AND is_recruiting = 0`) != 1 {
		t.Fatal("停用的队长，战队该停招")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM teams WHERE id = 2 AND is_recruiting = 1`) != 1 {
		t.Fatal("别人的战队不受影响")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM team_applications WHERE applicant_id = ? AND status = 'cancelled'`, cap.ID) != 1 {
		t.Fatal("停用的人的待审申请该撤回")
	}
}

// 契约 R038：导出覆盖战队、入队申请、退役记录、成员分组
func TestExportCoversTeamData(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sess := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sess, nil)
	u := newVerifiedUser(t, d, "export@sjtu.edu.cn", "导出的人", "Password123!@#", true)
	token, _ := sess.Create(ctx, u.ID)
	execAll(t, d,
		`INSERT INTO teams (id, name, created_at, updated_at) VALUES (1, '现队', 'x', 'x'), (2, '旧队', 'x', 'x'), (3, '申请队', 'x', 'x')`,
		`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (1, `+itoa(u.ID)+`, 'member', '2026-10-01T00:00:00.000000Z')`,
		`INSERT INTO team_alumni (team_id, user_id, role, joined_at, left_at, reason) VALUES (2, `+itoa(u.ID)+`, 'member', '2026-09-01T00:00:00.000000Z', '2026-09-20T00:00:00.000000Z', 'removed')`,
		`INSERT INTO team_applications (team_id, applicant_id, role_tank, role_support, message, status, created_at) VALUES (3, `+itoa(u.ID)+`, 1, 1, '带我', 'pending', '2026-10-02T00:00:00.000000Z')`,
		`INSERT INTO member_groups (id, name, created_at, updated_at) VALUES (1, '干部', 'x', 'x')`,
		`INSERT INTO member_group_memberships (group_id, user_id, title) VALUES (1, `+itoa(u.ID)+`, '社长')`,
	)
	out, err := svc.ExportAccount(newTestCtx(ctx, u, token, false))
	if err != nil {
		t.Fatal(err)
	}
	if len(out.Teams) != 1 || out.Teams[0].Name != "现队" || out.Teams[0].Role != "member" {
		t.Fatalf("战队：%+v", out.Teams)
	}
	if len(out.TeamApplications) != 1 || out.TeamApplications[0].Message != "带我" ||
		len(out.TeamApplications[0].Roles) != 2 || out.TeamApplications[0].Roles[1] != "support" {
		t.Fatalf("入队申请：%+v", out.TeamApplications)
	}
	if len(out.TeamAlumni) != 1 || out.TeamAlumni[0].Reason != "removed" || out.TeamAlumni[0].TeamName != "旧队" {
		t.Fatalf("退役记录：%+v", out.TeamAlumni)
	}
	if len(out.MemberGroups) != 1 || out.MemberGroups[0].Title != "社长" {
		t.Fatalf("分组：%+v", out.MemberGroups)
	}
}

func itoa(n int64) string {
	return strconv.FormatInt(n, 10)
}

func isInvalid(err error) bool {
	ae, ok := err.(*api.Error)
	return ok && ae.Status == 400
}

// 契约 R031：注销时退出进行中的临时队伍、删个人报名；最后一人退出时队伍自动解散；整队报名的名单快照保留
func TestDeleteAccountLeavesTournaments(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sess := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sess, nil)
	u1 := newVerifiedUser(t, d, "one@sjtu.edu.cn", "一号", "Password123!@#", true)
	u2 := newVerifiedUser(t, d, "two@sjtu.edu.cn", "二号", "Password123!@#", true)
	execAll(t, d,
		`INSERT INTO tournaments (id, title, status, registration_mode, created_at, updated_at) VALUES (1, '赛', 'published', 'individual', 'x', 'x')`,
		`INSERT INTO registrations (id, tournament_id, team_id, status, team_name, submitted_at, created_at, updated_at) VALUES (1, 1, NULL, 'approved', '临时队', 'x', 'x', 'x')`,
		`INSERT INTO registration_members (registration_id, tournament_id, user_id, nickname, battletag, is_active) VALUES (1, 1, `+itoa(u1.ID)+`, '一号', 'a#1', 1), (1, 1, `+itoa(u2.ID)+`, '二号', 'b#2', 1)`,
		`INSERT INTO individual_signups (tournament_id, user_id, role_tank, registration_id, created_at, updated_at) VALUES (1, `+itoa(u1.ID)+`, 1, 1, 'x', 'x'), (1, `+itoa(u2.ID)+`, 1, 1, 'x', 'x')`,
	)
	del := func(u *User) {
		tok, _ := sess.Create(ctx, u.ID)
		if _, err := svc.DeleteAccount(newTestCtx(ctx, u, tok, false), DeleteAccountInput{Password: "Password123!@#"}); err != nil {
			t.Fatal(err)
		}
	}
	del(u1)
	if countOf(t, d, `SELECT COUNT(*) FROM individual_signups WHERE user_id = ?`, u1.ID) != 0 ||
		countOf(t, d, `SELECT COUNT(*) FROM registration_members WHERE user_id = ?`, u1.ID) != 0 {
		t.Fatal("个人报名和临时队名单行应删除")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM registrations WHERE id = 1 AND status = 'approved'`) != 1 {
		t.Fatal("队里还有人，不解散")
	}
	del(u2)
	if countOf(t, d, `SELECT COUNT(*) FROM registrations WHERE id = 1 AND status = 'withdrawn'`) != 1 ||
		countOf(t, d, `SELECT COUNT(*) FROM registration_status_logs WHERE registration_id = 1 AND action = 'dissolve' AND actor_type = 'system'`) != 1 {
		t.Fatal("最后一人退出，临时队伍自动解散并记 SYSTEM 日志")
	}
}

// 契约 R031、R158：注销时撤内战报名；已分队或进了替补的，给那场内战打「名单有变动」标记
func TestDeleteAccountRemovesScrimSignups(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sess := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sess, nil)
	u := newVerifiedUser(t, d, "scrim@sjtu.edu.cn", "内战人", "Password123!@#", true)
	w := newVerifiedUser(t, d, "bench@sjtu.edu.cn", "没排上", "Password123!@#", true)
	execAll(t, d,
		`INSERT INTO scrims (id, title, status, created_at, updated_at) VALUES (1, '甲', 'published', 'x', 'x'), (2, '乙', 'published', 'x', 'x')`,
		`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, is_selected, team, assigned_role, created_at, updated_at) VALUES (1, `+itoa(u.ID)+`, 1, 1, 'a', 'tank', 'x', 'x')`,
		`INSERT INTO scrim_signups (scrim_id, user_id, role_tank, created_at, updated_at) VALUES (2, `+itoa(w.ID)+`, 1, 'x', 'x')`,
	)
	del := func(u *User) {
		tok, _ := sess.Create(ctx, u.ID)
		if _, err := svc.DeleteAccount(newTestCtx(ctx, u, tok, false), DeleteAccountInput{Password: "Password123!@#"}); err != nil {
			t.Fatal(err)
		}
	}
	del(u)
	del(w)
	if countOf(t, d, `SELECT COUNT(*) FROM scrim_signups`) != 0 {
		t.Fatal("内战报名都该撤掉")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM scrims WHERE id = 1 AND roster_changed_at IS NOT NULL`) != 1 {
		t.Fatal("已分队的人注销，那场内战要打名单变动标记")
	}
	if countOf(t, d, `SELECT COUNT(*) FROM scrims WHERE id = 2 AND roster_changed_at IS NULL`) != 1 {
		t.Fatal("没被安排过的人注销，不用打标记")
	}
}
