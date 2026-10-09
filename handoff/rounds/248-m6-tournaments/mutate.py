"""248 的变异：把赛事域的关键规则逐条改坏，确认对应测试会红（硬规则 7）。
用法：bash scripts/remote-check.sh run uv run python -u handoff/rounds/248-m6-tournaments/mutate.py [标签片段…]
`--check` 只核对每处变异的目标在文件里恰好出现一次，不跑测试。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"
T = SERVER / "internal/tournaments"
A = SERVER / "internal/accounts"
PT, PA = "./internal/tournaments/", "./internal/accounts/"

M = [
    ("R109 发布不看截止时间", T / "service.go", "if t.RegistrationClosesAt == nil {\n\t\tgaps", "if false {\n\t\tgaps", PT, "TestPublishCancelFinishDelete"),
    ("R109 截止要晚于开始", T / "service.go", "if okAll && opens != nil && closes != nil && !opens.Before(*closes) {", "if okAll && opens != nil && closes != nil && false {", PT, "TestPublishCancelFinishDelete"),
    ("R110 已取消可再发布", T / "service.go", "if t.Status == StatusCancelled {\n\t\t\treturn \"\", refuse(\"已取消的赛事不能再发布。\")", "if false {\n\t\t\treturn \"\", refuse(\"已取消的赛事不能再发布。\")", PT, "TestPublishCancelFinishDelete"),
    ("R110 未发布也能标结束", T / "service.go", "if t.Status != StatusPublished {\n\t\t\treturn \"\", refuse(\"只有已发布的赛事可以标记为已结束。\")", "if false {\n\t\t\treturn \"\", refuse(\"只有已发布的赛事可以标记为已结束。\")", PT, "TestPublishCancelFinishDelete"),
    ("R110 发布过的也能删", T / "service.go", "if t.PublishedAt != nil || t.Status != StatusDraft {", "if false {", PT, "TestPublishCancelFinishDelete"),
    ("R111 散人池不锁报名方式", T / "service.go", "locked, err := hasEntries(txCtx, tx, id)", "locked, err := hasRegistrations(txCtx, tx, id)", PT, "TestModeAndAutoApproveLocks"),
    ("R112 散人池也锁自动通过", T / "service.go", "locked, err := hasRegistrations(txCtx, tx, id)", "locked, err := hasEntries(txCtx, tx, id)", PT, "TestModeAndAutoApproveLocks"),
    ("R113 人数下限不看战队上限", T / "service.go", "if tm := teamMaxMembers(txCtx, tx); min > tm {", "if tm := teamMaxMembers(txCtx, tx); min > tm+100 {", PT, "TestRosterBounds"),
    ("R114 清空说明也送审", T / "service.go", "if s.mod == nil || t.Description == \"\" {", "if s.mod == nil {", PT, "TestDescriptionGoesToModeration"),
    ("R116 不看仅限交大", T / "registration.go", "if t.SjtuOnly && !u.IsSJTU {", "if false && t.SjtuOnly && !u.IsSJTU {", PT, "TestPrecheckListsEveryProblem"),
    ("R116 不看资料完整", T / "registration.go", "if len(gaps) > 0 {", "if false {", PT, "TestPrecheckListsEveryProblem"),
    ("R117 驳回的名单仍占名额", T / "registration.go", "AND rm.is_active = 1 AND rm.registration_id <> ?", "AND rm.registration_id <> ?", PT, "TestOneActiveRoster"),
    ("R118 可选别人的游戏ID", T / "registration.go", "FROM game_accounts WHERE id = ? AND user_id = ?`, id, m.UserID)", "FROM game_accounts WHERE id = ? AND 0 = ?`, id, 0)", PT, "TestAccountSelectionAndSnapshot"),
    ("R120 自动通过失效", T / "registration.go", "if t.AutoApprove {", "if false && t.AutoApprove {", PT, "TestSubmitAutoApproveAndMails"),
    ("R121 同步名单也通知老队员", T / "registration.go", "if !row.IsCaptain && !alreadyOn[row.UserID] {", "if !row.IsCaptain {", PT, "TestSubmitAutoApproveAndMails"),
    ("R123 系统通过也发状态信", T / "registration.go", "if actorType != ActorSystem {", "if true {", PT, "TestSubmitAutoApproveAndMails"),
    ("R124 截止后仍可撤回", T / "registration.go", "if t.RegistrationClosesAt != nil && now.After(*t.RegistrationClosesAt) {\n\t\t\treturn refuse(\"报名已截止，不能再修改\")", "if false {\n\t\t\treturn refuse(\"报名已截止，不能再修改\")", PT, "TestWithdraw"),
    ("R124 非队长可撤回", T / "registration.go", "return deny(\"只有队长可以撤回报名\")", "return nil", PT, "TestWithdraw"),
    ("R125 备注不截断", T / "registration.go", "note = string([]rune(note)[:NoteMax])", "_ = NoteMax", PT, "TestRejectNoteAndAdhoc"),
    ("R125 驳回可不填备注", T / "registration.go", "if note == \"\" {\n\t\t\treturn api.InvalidFields(map[string][]string{\"note\": {\"驳回必须填写备注\"}})", "if false {\n\t\t\treturn api.InvalidFields(map[string][]string{\"note\": {\"驳回必须填写备注\"}})", PT, "TestStatusMachine"),
    ("R125 临时队伍可在审核页驳回", T / "registration.go", "if r.Adhoc() {\n\t\t\treturn refuse(\"临时队伍请在", "if false {\n\t\t\treturn refuse(\"临时队伍请在", PT, "TestRejectNoteAndAdhoc"),
    ("R126 结束后仍可审核", T / "registration.go", "case StatusFinished:\n\t\treturn refuse(\"赛事已结束", "case \"nope\":\n\t\treturn refuse(\"赛事已结束", PT, "TestStatusMachine"),
    ("R127 路人能看报名详情", T / "views.go", "if !captain && onRoster == 0 {", "if false {", PT, "TestRegistrationVisibility"),
    ("R127 未激活名单也给联系方式", T / "views.go", "if active > 0 {\n\t\tpage.ParticipantContact", "if true {\n\t\tpage.ParticipantContact", PT, "TestRegistrationVisibility"),
    ("R128 个人报名可不勾位置", T / "individual.go", "if tank+damage+support == 0 {", "if false {", PT, "TestIndividualSignupRules"),
    ("R129 已编队仍可自行改", T / "individual.go", "if existing != nil && existing.Placed() {", "if false {", PT, "TestIndividualPlacedAndCancel"),
    ("R129 已编队仍可取消", T / "individual.go", "if sg.Placed() {\n\t\t\treturn refuse(\"你已经被编入队伍，要退出请在", "if false {\n\t\t\treturn refuse(\"你已经被编入队伍，要退出请在", PT, "TestIndividualPlacedAndCancel"),
    ("R129 截止后仍可取消", T / "individual.go", "if t.RegistrationClosesAt != nil && now.After(*t.RegistrationClosesAt) {\n\t\t\treturn refuse(\"报名已截止，不能再取消\")", "if false {\n\t\t\treturn refuse(\"报名已截止，不能再取消\")", PT, "TestIndividualPlacedAndCancel"),
    ("R130 一人可进两队", T / "individual.go", "if seen[sid] {", "if false {", PT, "TestFormTeamsValidatesBeforeWriting"),
    ("R130 两队可同名", T / "individual.go", "if names[k] {", "if false {", PT, "TestFormTeamsValidatesBeforeWriting"),
    ("R130 不看人数上限", T / "individual.go", "if len(ids) > t.RosterMax {", "if false {", PT, "TestFormTeamsValidatesBeforeWriting"),
    ("R132 缺席的队不解散", T / "individual.go", "for _, r := range liveList {\n\t\t\tif !mentioned[r.ID] {", "for _, r := range liveList {\n\t\t\tif false {", PT, "TestFormTeamsMovesAndDissolves"),
    ("R133 编入不通知", T / "individual.go", "if err := s.notifyAdhocFormed(txCtx, tx, ctx, t, f.reg, f.users, now); err != nil {", "if err := error(nil); err != nil {", PT, "TestFormTeamsMovesAndDissolves"),
    ("R134 退出不删成员行", T / "individual.go", "DELETE FROM registration_members WHERE registration_id = ? AND user_id = ?`, regID, v.ID); err != nil {", "DELETE FROM registration_members WHERE registration_id = ? AND user_id = ? AND 1 = 0`, regID, v.ID); err != nil {", PT, "TestLeaveAdhoc"),
    ("R134 最后一人退出不解散", T / "individual.go", "dissolved = left == 0", "dissolved = false", PT, "TestLeaveAdhoc"),
    ("R134 截止后仍可退出", T / "individual.go", "if t.RegistrationClosesAt != nil && now.After(*t.RegistrationClosesAt) {\n\t\t\treturn refuse(\"报名已截止，不能再退出\")", "if false {\n\t\t\treturn refuse(\"报名已截止，不能再退出\")", PT, "TestLeaveAdhoc"),
    ("R135 解散不放人回池", T / "individual.go", "SET registration_id = NULL WHERE registration_id = ?`, r.ID); err != nil {", "SET registration_id = NULL WHERE registration_id = ? AND 1 = 0`, r.ID); err != nil {", PT, "TestDissolveAdhoc"),
    ("R136 多次移动不留最早时间", T / "service.go", "told := t.MovedFrom\n\t\t\tif told == nil {\n\t\t\t\ttold = t.StartsAt\n\t\t\t}", "told := t.StartsAt", PT, "TestTimeChange"),
    ("R136 改到过去也触发", T / "service.go", "newStarts != nil && newStarts.After(now) {", "newStarts != nil {", PT, "TestTimeChange"),
    ("R137 通知后不清 moved_from", T / "service.go", "UPDATE tournaments SET moved_from = NULL WHERE id = ?`, id)", "UPDATE tournaments SET moved_from = NULL WHERE id = ? AND 1 = 0`, id)", PT, "TestNotifyParticipants"),
    ("R138 提醒不标记已发", T / "reminder.go", "UPDATE tournaments SET reminder_sent_at = ? WHERE id = ? AND reminder_sent_at IS NULL`,", "UPDATE tournaments SET reminder_sent_at = ? WHERE id = ? AND 1 = 0`,", PT, "TestReminders"),
    ("R139 不等 10 分钟", T / "model.go", "ReminderGrace = 10 * time.Minute", "ReminderGrace = 0", PT, "TestReminders"),
    ("R140 没人通过也标记已发", T / "reminder.go", "if len(items) == 0 {\n\t\t\t\treturn nil", "if false {\n\t\t\t\treturn nil", PT, "TestReminders"),
    ("R141 取消通知全体队员", T / "service.go", "WHERE r.tournament_id = ? AND r.status IN ('pending', 'approved') AND m.role = 'captain'", "WHERE r.tournament_id = ? AND r.status IN ('pending', 'approved')", PT, "TestCancelNotifies"),
    ("R143 复制不保证落在未来", T / "service.go", "n := now.Sub(*earliest)/week + 1", "n := now.Sub(*earliest) / week", PT, "TestCopy"),
    ("门 后台不查能力", T / "service.go", "if !v.HasCap(accounts.CapTournamentsManage) {", "if false {", PT, "TestPublishCancelFinishDelete"),
    ("R148 草稿对外可见", T / "views.go", "if t == nil || (!t.IsPublic() && !manager) {", "if t == nil {", PT, "TestListAndDetail"),
    ("R31 注销不删个人报名", A / "store.go", "_, err = tx.ExecContext(ctx, `DELETE FROM individual_signups WHERE user_id = ?`, userID)", "_, err = tx.ExecContext(ctx, `DELETE FROM individual_signups WHERE user_id = ? AND 1 = 0`, userID)", PA, "TestDeleteAccountLeavesTournaments"),
    ("R31 最后一人注销不解散临时队", A / "store.go", "if left > 0 {\n\t\t\tcontinue\n\t\t}", "if true {\n\t\t\tcontinue\n\t\t}", PA, "TestDeleteAccountLeavesTournaments"),
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
    for pkg in (PT, PA):
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
