"""249 的变异：把内战域的关键规则逐条改坏，确认对应测试会红（硬规则 7）。
用法：bash scripts/remote-check.sh run uv run python -u handoff/rounds/249-m6-scrims/mutate.py [标签片段…]
`--check` 只核对每处变异的目标在文件里恰好出现一次，不跑测试。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"
S = SERVER / "internal/scrims"
A = SERVER / "internal/accounts"
PS, PA = "./internal/scrims/", "./internal/accounts/"

M = [
    ("R159 不查人数", S / "teaming.go", "if len(players) != needed {", "if false {", PS, "TestTeamingFeasibility"),
    ("R159 不查位置够不够", S / "teaming.go", "if able < perTeam*2 {", "if false {", PS, "TestTeamingFeasibility"),
    ("R159 不查段位", S / "teaming.go", "if len(stuck) > 0 {", "if false {", PS, "TestTeamingFeasibility"),
    ("R160 5v5 坦克要 2 个", S / "model.go", "case FormatRQ5:\n\t\treturn map[string]int{Tank: 1, Damage: 2, Support: 2}", "case FormatRQ5:\n\t\treturn map[string]int{Tank: 2, Damage: 2, Support: 2}", PS, "TestTeaming|TestGenerateTeams"),
    ("R161 并列不收集", S / "teaming.go", "case c.score == best:", "case false:", PS, "TestTeamingTiesAreRandom"),
    ("R161 先比位置分差", S / "teaming.go", "return [2]int{abs(a.Total - b.Total), gap}", "return [2]int{gap, abs(a.Total - b.Total)}", PS, "TestTeamingMatchesBruteForce"),
    ("R162 配对不二分定位", S / "teaming.go", "position := sort.SearchInts(totals, a.Total)", "position := 0", PS, "TestTeamingMatchesBruteForce"),
    ("R163 不提醒没段位的位置", S / "teaming.go", "if _, ok := p.Ratings[role]; !ok {", "if false {", PS, "TestUnratedPlacements"),
    ("R163 按最高分算角色限定", S / "teaming.go", "used[id] = p.Rating(role)", "used[id] = p.Best", PS, "TestUnratedPlacements"),
    ("R144 已结束可再发布", S / "service.go", "case StatusFinished:\n\t\t\treturn \"\", refuse(\"已结束的内战不能再发布。\")", "case \"nope\":\n\t\t\treturn \"\", refuse(\"已结束的内战不能再发布。\")", PS, "TestScrimLifecycle"),
    ("R145 发布不看缺什么", S / "service.go", "if gaps := Missing(sc); len(gaps) > 0 {\n\t\t\treturn \"\", refuse(\"还没填好：", "if gaps := Missing(sc); false {\n\t\t\treturn \"\", refuse(\"还没填好：", PS, "TestScrimLifecycle"),
    ("R146 有人报名也能删", S / "service.go", "if n > 0 {\n\t\t\treturn refuse(\"已经有人报名，不能删除。\")", "if false {\n\t\t\treturn refuse(\"已经有人报名，不能删除。\")", PS, "TestScrimLifecycle"),
    ("R147 自动结束提前", S / "model.go", "FinishAfter = 6 * time.Hour", "FinishAfter = 1 * time.Hour", PS, "TestAutoFinish"),
    ("R148 草稿对外可见", S / "views.go", "if sc == nil || !sc.IsPublic() {\n\t\treturn nil, api.NotFound", "if sc == nil {\n\t\treturn nil, api.NotFound", PS, "TestScrimVisibility"),
    ("R149 已结束保留太久", S / "views.go", "-FinishedVisibleDays * 24 * time.Hour", "-FinishedVisibleDays * 240 * time.Hour", PS, "TestScrimVisibility"),
    ("R150 取消也通知停用账号", S / "service.go", "WHERE g.scrim_id = ? AND u.is_active = 1 AND u.email <> ''", "WHERE g.scrim_id = ? AND u.email <> ''", PS, "TestCancelNotifiesSignups"),
    ("R151 提醒不标记已发", S / "service.go", "UPDATE scrims SET reminder_sent_at = ? WHERE id = ? AND reminder_sent_at IS NULL`,", "UPDATE scrims SET reminder_sent_at = ? WHERE id = ? AND 1 = 0`,", PS, "TestReminder"),
    ("R151 不等 10 分钟", S / "model.go", "ReminderGrace = 10 * time.Minute", "ReminderGrace = 0", PS, "TestReminder"),
    ("R153 不看仅限交大", S / "signup.go", "if sc.SjtuOnly && sjtu != 1 {", "if false {", PS, "TestSignupEligibility"),
    ("R153 不看截止", S / "signup.go", "} else if d := sc.Deadline(); d != nil && now.After(*d) {", "} else if false {", PS, "TestSignupEligibility|TestSignupDeadline"),
    ("R155 角色限定不看段位", S / "signup.go", "if acc.Rank(r) == nil {", "if false {", PS, "TestSignupRolesAndRanks"),
    ("R155 开放赛不看有没有段位", S / "signup.go", "return []string{\"这个游戏 ID 一个位置的段位都没填\"}", "return nil", PS, "TestSignupRolesAndRanks"),
    ("R156 可以一个位置都不勾", S / "signup.go", "if len(roles) == 0 {\n\t\treturn []string{\"至少要勾选一个能打的位置\"}", "if false {\n\t\treturn []string{\"至少要勾选一个能打的位置\"}", PS, "TestSignupRolesAndRanks"),
    ("R157 改位置不清分队", S / "signup.go", "if changed {", "if false {", PS, "TestSignupChangeClearsPlacement"),
    ("R157 改位置不打标记", S / "signup.go", "if wasPlaced {\n\t\t\t\t\tif err := markChanged", "if false {\n\t\t\t\t\tif err := markChanged", PS, "TestSignupChangeClearsPlacement"),
    ("R158 截止后可取消", S / "signup.go", "if d := sc.Deadline(); d != nil && now.After(*d) {\n\t\t\treturn refuse(\"报名已截止，不能再取消\")", "if false {\n\t\t\treturn refuse(\"报名已截止，不能再取消\")", PS, "TestSignupChangeClearsPlacement"),
    ("R158 取消不打标记", S / "signup.go", "if g.Placed() {\n\t\t\treturn markChanged", "if false {\n\t\t\treturn markChanged", PS, "TestSignupChangeClearsPlacement"),
    ("R165 保存不清没放进队的人", S / "board.go", "if placed[g.ID] || (g.Team == \"\" && g.AssignedRole == \"\") {", "if true {", PS, "TestSaveTeamsBenchAndWarnings"),
    ("R165 取消勾选不清分队", S / "board.go", "UPDATE scrim_signups SET is_selected = 0, team = '', assigned_role = '', rating_used = NULL, updated_at = ? WHERE id = ?", "UPDATE scrim_signups SET is_selected = 0, rating_used = NULL, updated_at = ? WHERE id = ?", PS, "TestSaveTeamsBenchAndWarnings"),
    ("R166 替补不说替补", S / "service.go", "return \"替补\"", "return \"\"", PS, "TestPlacementPrivacy"),
    ("R167 过期判断反了", S / "board.go", "sc.RosterChangedAt.After(*sc.TeamsGeneratedAt)", "sc.RosterChangedAt.Before(*sc.TeamsGeneratedAt)", PS, "TestTeamsStale"),
    ("R170 同位置不用斜杠分隔", S / "board.go", "strings.Join(entries, \" / \")", "strings.Join(entries, \"、\")", PS, "TestCopyText"),
    ("R169 复制不保证落在未来", S / "service.go", "return (now.Sub(*earliest)/week + 1) * week", "return (now.Sub(*earliest) / week) * week", PS, "TestScrimCopy"),
    ("门 后台不查能力", S / "service.go", "if !v.HasCap(accounts.CapScrimsManage) {", "if false {", PS, "TestScrimLifecycle"),
    ("板版本不校验", S / "board.go", "if base != sc.BoardVersion {", "if false {", PS, "TestBoardVersionConflict"),
    ("R31 注销不撤内战报名", A / "store.go", "if _, err := tx.ExecContext(ctx, `DELETE FROM scrim_signups WHERE user_id = ?`, userID); err != nil {", "if _, err := tx.ExecContext(ctx, `DELETE FROM scrim_signups WHERE user_id = ? AND 1 = 0`, userID); err != nil {", PA, "TestDeleteAccountRemovesScrimSignups"),
    ("R31 已分队的人注销不打标记", A / "store.go", "WHERE id IN (SELECT scrim_id FROM scrim_signups WHERE user_id = ? AND (is_selected = 1 OR team <> ''))", "WHERE id IN (SELECT scrim_id FROM scrim_signups WHERE user_id = ? AND 1 = 0)", PA, "TestDeleteAccountRemovesScrimSignups"),
]


def go_test(pkg, run):
    cmd = ["go", "test", "-count=1", pkg] + (["-run", run] if run else [])
    return subprocess.run(cmd, cwd=SERVER).returncode


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    muts = [m for m in M if not only or any(o in m[0] for o in only)]
    for label, path, target, _rep, _pkg, _test in muts:
        n = path.read_text(encoding="utf-8").count(target)
        if n != 1:
            print(f"目标出现 {n} 次（要恰好 1 次）：{label}")
            return 2
    if "--check" in sys.argv:
        print(f"{len(muts)} 处变异的目标都恰好出现一次。")
        return 0
    print("== 基线 ==")
    for pkg in (PS, PA):
        if go_test(pkg, None) != 0:
            print("基线是红的，变异没有意义，停")
            return 1
    print("基线绿")
    missed = []
    for label, path, target, rep, pkg, test in muts:
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace(target, rep), encoding="utf-8")
        try:
            rc = go_test(pkg, test)
        finally:
            path.write_text(original, encoding="utf-8")
        print(("  抓到（红）：" if rc else "  变异漏抓：") + label, flush=True)
        if rc == 0:
            missed.append(label)
    if missed:
        print(f"\n有 {len(missed)} 处没抓到：")
        for m in missed:
            print("  -", m)
        return 1
    print(f"\n全部 {len(muts)} 处变异抓到并已恢复代码。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
