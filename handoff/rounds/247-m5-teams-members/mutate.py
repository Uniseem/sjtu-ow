"""247 的变异：把 M5 的关键规则逐条改坏，确认对应测试会红（硬规则 7）。
用法：bash scripts/remote-check.sh run uv run python handoff/rounds/247-m5-teams-members/mutate.py [标签片段…]
`--check` 只核对每处变异的目标在文件里恰好出现一次，不跑测试。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"
T = SERVER / "internal/teams"
M = SERVER / "internal/members"
A = SERVER / "internal/accounts"

# (标签, 文件, 目标, 替换, 包, 测试名正则)
MUTATIONS = [
    ("R83 队名长度上限放宽", T / "service.go", "n < NameMin || n > NameMax {", "n < NameMin || n > NameMax+10 {", "./internal/teams/", "TestTeamNameRules"),
    # 服务层的预查重和唯一索引是两道防线，改坏预查重时索引兜底给出同样的提示，是等价变异；
    # 所以改索引本身（并发时的最后一道）：测试里绕过服务直接插同名要被拦
    ("R83 唯一索引不分大小写失效", SERVER / "db/migrations/00011_teams_members.sql", "CREATE UNIQUE INDEX teams_active_name ON teams (lower(name))", "CREATE UNIQUE INDEX teams_active_name ON teams (name)", "./internal/teams/", "TestTeamNameRules"),
    ("R84 建队不计每日额度", T / "service.go", "if s.limiter != nil {\n\t\tretry, ok, err := s.limiter.Allow(ctx.Context, fmt.Sprintf(\"u:%d\", v.ID), ratelimit.TeamCreate)", "if false && s.limiter != nil {\n\t\tretry, ok, err := s.limiter.Allow(ctx.Context, fmt.Sprintf(\"u:%d\", v.ID), ratelimit.TeamCreate)", "./internal/teams/", "TestTeamCreateDailyLimit"),
    ("R85 队长数上限差一", T / "service.go", "if n >= lim.MaxCaptained {\n\t\treturn fmt.Sprintf(", "if n > lim.MaxCaptained {\n\t\treturn fmt.Sprintf(", "./internal/teams/", "TestCaptainedCap"),
    ("R86 满员仍可申请", T / "applications.go", "if n >= lim.MaxMembers {\n\t\treturn false, \"战队人数已满。\", nil", "if n > lim.MaxMembers {\n\t\treturn false, \"战队人数已满。\", nil", "./internal/teams/", "TestTeamMemberCap"),
    ("R87 成员也能当管理者", T / "service.go", "return m != nil && m.Role == RoleCaptain, nil", "return m != nil, nil", "./internal/teams/", "TestOnlyCaptainEditsProfile"),
    ("R88 不检查队长账号停用", T / "store.go", "WHERE m.team_id = ? AND m.role = 'captain' AND u.is_active = 1", "WHERE m.team_id = ? AND m.role = 'captain'", "./internal/teams/", "TestApplyConditions"),
    ("R89 申请限流放宽", SERVER / "internal/platform/ratelimit/limits.go", "TeamApply = Decl{Name: \"team_apply\", Kind: PerUser, N: 20,", "TeamApply = Decl{Name: \"team_apply\", Kind: PerUser, N: 200,", "./internal/teams/", "TestApplyDailyLimit"),
    ("R90 不要求意向位置", T / "applications.go", "if len(roles) == 0 {", "if false && len(roles) == 0 {", "./internal/teams/", "TestApplyInputAndModeration"),
    ("R92 通过时不看申请人是否停用", T / "applications.go", "case applicant == nil || !applicant.Active:", "case applicant == nil:", "./internal/teams/", "TestApproveRechecksAndEffects"),
    ("R92 通过时不拦满员", T / "applications.go", "if n >= lim.MaxMembers {\n\t\t\t\treturn refuse(\"战队人数已满，无法通过。\")", "if false && n >= lim.MaxMembers {\n\t\t\t\treturn refuse(\"战队人数已满，无法通过。\")", "./internal/teams/", "TestTeamMemberCap"),
    ("R93 通过时不删退役记录", T / "applications.go", "if err := s.store.UnretireTx(txCtx, tx, a.TeamID, a.ApplicantID); err != nil {", "if err := error(nil); err != nil {", "./internal/teams/", "TestApproveRechecksAndEffects"),
    ("R94 提醒不记已提醒", T / "applications.go", "AND a.captain_reminded_at IS NULL", "", "./internal/teams/", "TestRemindCaptains"),
    ("R95 自动关闭天数放宽", T / "model.go", "StaleApplicationDays = 14", "StaleApplicationDays = 30", "./internal/teams/", "TestCloseStaleApplications"),
    ("R96 待审列表显示停用账号", T / "views.go", "AND a.status = 'pending' AND u.is_active = 1", "AND a.status = 'pending'", "./internal/teams/", "TestPendingHidesDeactivatedApplicants"),
    ("R97 队长可直接退出", T / "members.go", "if m.Role == RoleCaptain {\n\t\t\treturn refuse(\"队长不能直接退出", "if false && m.Role == RoleCaptain {\n\t\t\treturn refuse(\"队长不能直接退出", "./internal/teams/", "TestLeaveAndAlumni"),
    ("R98 退出不写退役记录", T / "members.go", "if err := s.store.RetireTx(txCtx, tx, m, LeaveLeft, now); err != nil {", "if err := error(nil); err != nil {", "./internal/teams/", "TestLeaveAndAlumni"),
    ("R100 可以移除自己", T / "members.go", "if userID == v.ID {\n\t\t\treturn refuse(\"不能移除自己。\")", "if false && userID == v.ID {\n\t\t\treturn refuse(\"不能移除自己。\")", "./internal/teams/", "TestRemoveMemberRules"),
    ("R100 超管可以移除队长", T / "members.go", "if m.Role == RoleCaptain {\n\t\t\t// 超管也不行", "if false && m.Role == RoleCaptain {\n\t\t\t// 超管也不行", "./internal/teams/", "TestRemoveMemberRules"),
    ("R101 任何人能删退役记录", T / "members.go", "allowed := v.Superuser || v.ID == userID", "allowed := true", "./internal/teams/", "TestRemoveAlumnusPermission"),
    ("R102 停用账号可当队长", T / "members.go", "if u == nil || !u.Active {\n\t\t// 停用的人当队长", "if u == nil {\n\t\t// 停用的人当队长", "./internal/teams/", "TestTransferCaptain"),
    ("R102 队长数达上限仍可接任", T / "members.go", "if n >= lim.MaxCaptained {\n\t\treturn refuse(\"对方担任", "if false && n >= lim.MaxCaptained {\n\t\treturn refuse(\"对方担任", "./internal/teams/", "TestTransferCaptain"),
    ("R103 非超管能指定队长", T / "members.go", "if !v.Superuser {\n\t\treturn deny(\"只有超级管理员可以指定队长。\")", "if v == nil {\n\t\treturn deny(\"只有超级管理员可以指定队长。\")", "./internal/teams/", "TestAssignCaptain"),
    ("R104 解散不看进行中的报名", T / "members.go", "if len(blockers) > 0 {", "if false {", "./internal/teams/", "TestDisband"),
    ("R105 解散不删成员关系", T / "members.go", "DELETE FROM team_memberships WHERE team_id = ?`, teamID); err != nil {", "DELETE FROM team_memberships WHERE team_id = ? AND 1 = 0`, teamID); err != nil {", "./internal/teams/", "TestDisband"),
    ("R105 解散不取消待审申请", T / "members.go", "SET status = 'cancelled', decided_at = ?, decision_note = '战队已解散'", "SET status = status, decided_at = ?, decision_note = '战队已解散'", "./internal/teams/", "TestDisband"),
    ("R106 队标大小上限放宽", T / "model.go", "LogoMaxBytes = 5 * 1024 * 1024", "LogoMaxBytes = 50 * 1024 * 1024", "./internal/teams/", "TestLogoRules"),
    ("R106 队标可用别人的图", T / "service.go", "if !v.Superuser && (!uploader.Valid || uploader.Int64 != v.ID) {", "if false {", "./internal/teams/", "TestLogoRules"),
    ("R107 送审失败挡住操作", T / "service.go", "slog.Warn(\"送审失败\", \"target\", \"team_name\"", "panic(\"送审失败\"); slog.Warn(\"送审失败\", \"target\", \"team_name\"", "./internal/teams/", "TestModerationNeverBlocks"),
    ("设计7.1 队内联系方式对所有人可见", T / "views.go", "if !page.Viewer.IsMember && !(loggedIn && v.Superuser) {", "if false {", "./internal/teams/", "TestMemberContactVisibility"),
    ("R236 未验证邮箱也算已加入", M / "service.go", "const joinedWhere = `u.is_active = 1 AND u.email_verified_at IS NOT NULL`", "const joinedWhere = `u.is_active = 1`", "./internal/members/", "TestJoinedUsersOnly"),
    ("R237 单个职务字数放宽", M / "service.go", "TitleEachMax = 10", "TitleEachMax = 100", "./internal/members/", "TestTitleLimits"),
    ("R237 搜人上限放宽", M / "service.go", "SearchLimit = 10", "SearchLimit = 100", "./internal/members/", "TestSearchPeople"),
    ("R237 内容编辑也能按邮箱搜", M / "service.go", "if v.Superuser {\n\t\tcond =", "if true {\n\t\tcond =", "./internal/members/", "TestSearchPeople"),
    ("R31 在任队长也能注销", A / "service.go", "WHERE m.user_id = ? AND m.role = 'captain' AND t.disbanded_at IS NULL", "WHERE m.user_id = ? AND m.role = 'nobody' AND t.disbanded_at IS NULL", "./internal/accounts/", "TestDeleteAccountLeavesTeamsAndGroups"),
    ("R31 注销不清退役记录", A / "store.go", "{`DELETE FROM team_alumni WHERE user_id = ?`, []any{userID}},", "", "./internal/accounts/", "TestDeleteAccountLeavesTeamsAndGroups"),
    ("R35 停用不停招", A / "store.go", "`UPDATE teams SET is_recruiting = 0, version", "`UPDATE teams SET is_recruiting = 1, version", "./internal/accounts/", "TestDeactivateSuspendsTeamActivity"),
]


def go_test(pkg: str, run: str | None) -> int:
    cmd = ["go", "test", "-count=1", pkg]
    if run:
        cmd += ["-run", run]
    return subprocess.run(cmd, cwd=SERVER).returncode


def main() -> int:
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    if only:
        global MUTATIONS
        MUTATIONS = [m for m in MUTATIONS if any(o in m[0] for o in only)]
    for label, path, target, _rep, _pkg, _test in MUTATIONS:
        n = path.read_text(encoding="utf-8").count(target)
        if n != 1:
            print(f"目标出现 {n} 次（要恰好 1 次）：{label}")
            return 2
    if "--check" in sys.argv:
        print(f"{len(MUTATIONS)} 处变异的目标都恰好出现一次。")
        return 0

    print("== 基线 ==")
    for pkg in ("./internal/teams/", "./internal/members/", "./internal/accounts/", "./internal/platform/ratelimit/"):
        if go_test(pkg, None) != 0:
            print("基线是红的，变异没有意义，停")
            return 1
    print("基线绿")

    missed = []
    for label, path, target, replacement, pkg, test_name in MUTATIONS:
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace(target, replacement), encoding="utf-8")
        try:
            rc = go_test(pkg, test_name)
        finally:
            path.write_text(original, encoding="utf-8")
        if rc == 0:
            print(f"  变异漏抓：{label}")
            missed.append(label)
        else:
            print(f"  抓到（红）：{label}")

    if missed:
        print(f"\n有 {len(missed)} 处没抓到：")
        for m in missed:
            print("  -", m)
        return 1
    print(f"\n全部 {len(MUTATIONS)} 处变异抓到并已恢复代码。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
