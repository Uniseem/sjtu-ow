"""250 的变异：把审核域的关键规则逐条改坏，确认对应测试会红（硬规则 7）。
注意：替换后的代码里，原来用到的变量要保持被用到，否则是编译失败冒充测试失败（249 的教训）。
用法：bash scripts/remote-check.sh run uv run python -u handoff/rounds/250-moderation-audit/mutate.py [标签片段…]
`--check` 只核对每处变异的目标在文件里恰好出现一次，不跑测试。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"
MOD = SERVER / "internal/moderation/service.go"
P = "./internal/moderation/"

M = [
    ("R185 只看开关不看配置", MOD, "return enabled == 1 && configured == 1", "return enabled == 1 && configured >= 0", P, "TestSubmitNeedsEnabledAndConfigured"),
    ("R185 只看配置不看开关", MOD, "return enabled == 1 && configured == 1", "return enabled >= 0 && configured == 1", P, "TestSubmitNeedsEnabledAndConfigured"),
    ("R185 空文本也入队", MOD, "if text == \"\" || !s.Enabled(ctx, s.d.ReadPool()) {", "if !s.Enabled(ctx, s.d.ReadPool()) {", P, "TestSubmitNeedsEnabledAndConfigured"),
    ("R187 旧文本不替换", MOD, "AND checked_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 1`, targetType, targetID, field).Scan(&stale)", "AND checked_at IS NULL AND 1 = 0 ORDER BY created_at DESC, id DESC LIMIT 1`, targetType, targetID, field).Scan(&stale)", P, "TestUnreadTextIsReplaced"),
    ("R187 读过的旧记录也被删", MOD, "DELETE FROM moderation_items WHERE target_type = ? AND target_id = ? AND field = ?\n\t\t\t\tAND checked_at IS NULL AND text_hash <> ?", "DELETE FROM moderation_items WHERE target_type = ? AND target_id = ? AND field = ?\n\t\t\t\tAND text_hash <> ?", P, "TestUnreadTextIsReplaced"),
    ("R187 替换时不清失败计数", MOD, "attempts = 0, last_error = '', failed_at = NULL WHERE id = ?", "attempts = attempts, last_error = last_error, failed_at = failed_at WHERE id = ?", P, "TestUnreadTextIsReplaced"),
    ("R188 短文也存整篇", MOD, "var shortTypes = map[string]bool{TargetNickname: true, TargetMotto: true, TargetTeamName: true, TargetComment: true}", "var shortTypes = map[string]bool{TargetNickname: true, TargetMotto: true, TargetTeamName: true}", P, "TestExcerptAndFullText"),
    ("R188 摘录字数放宽", MOD, "ExcerptChars = 2000", "ExcerptChars = 20000", P, "TestExcerptAndFullText"),
    ("R202 不查复核能力", MOD, "if !v.HasCap(accounts.CapModerationReview) {", "if !v.HasCap(accounts.CapModerationReview) && v == nil {", P, "TestReviewerGateAndList"),
    ("R202 列表含无风险", MOD, "where := []string{\"risk <> 'none'\"}", "where := []string{\"1 = 1\"}", P, "TestReviewerGateAndList"),
    ("R202 待复核含没读过的", MOD, "if status == StatusPending {\n\t\twhere = append(where, \"checked_at IS NOT NULL\")", "if false {\n\t\twhere = append(where, \"checked_at IS NOT NULL\")", P, "TestReviewerGateAndList"),
    ("R202 处置不记复核人", MOD, "UPDATE moderation_items SET status = ?, reviewed_by = ?, reviewed_at = ?, handling_note = ? WHERE id = ?`,\n\t\t\tstatus, v.ID, db.FormatUTC(now), note, id", "UPDATE moderation_items SET status = ?, reviewed_by = NULL, reviewed_at = ?, handling_note = ? WHERE id = ?`,\n\t\t\tstatus, db.FormatUTC(now), note, id", P, "TestHandle"),
    ("R203 说明可以不填", MOD, "if message == \"\" {\n\t\treturn nil, api.InvalidFields(map[string][]string{\"message\"", "if false {\n\t\treturn nil, api.InvalidFields(map[string][]string{\"message\"", P, "TestAskAuthor"),
    ("R203 说明字数放宽", MOD, "ReviseMaxChars = 500", "ReviseMaxChars = 5000", P, "TestAskAuthor"),
    ("R203 停用的作者也能发", MOD, "if active != 1 {\n\t\treturn \"作者的账号已停用，不能发信。\", nil", "if active < 0 {\n\t\treturn \"作者的账号已停用，不能发信。\", nil", P, "TestAskAuthor"),
    ("R203 不记之前发过几次", MOD, "WHERE object_type = 'moderation_item' AND object_id = ? AND action = 'moderation.ask_author'", "WHERE object_type = 'moderation_item' AND object_id = ? AND action = 'moderation.nothing'", P, "TestAskAuthor"),
    ("R203 发信后不算已处置", MOD, "UPDATE moderation_items SET status = 'handled', handling_note = '已发信要求作者修改',", "UPDATE moderation_items SET status = status, handling_note = '已发信要求作者修改',", P, "TestAskAuthor"),
    ("R204 清理保留天数缩短", MOD, "KeepDays = 180", "KeepDays = 1", P, "TestCleanup"),
    ("R204 没处理过的也清", MOD, "DELETE FROM moderation_items WHERE status <> 'pending'", "DELETE FROM moderation_items WHERE status <> 'nothing'", P, "TestCleanup"),
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
    if go_test(P, None) != 0:
        print("基线是红的，变异没有意义，停")
        return 1
    print("基线绿")
    missed = []
    for label, path, target, rep, pkg, test in muts:
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace(target, rep), encoding="utf-8")
        build = subprocess.run(["go", "vet", pkg], cwd=SERVER, capture_output=True).returncode
        try:
            rc = go_test(pkg, test) if build == 0 else -1
        finally:
            path.write_text(original, encoding="utf-8")
        if rc == -1:
            print(f"  变异本身编译不过（不算数）：{label}", flush=True)
            missed.append(label + "（编译失败）")
            continue
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
