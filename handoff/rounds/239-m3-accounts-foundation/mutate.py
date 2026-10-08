"""239 的五处变异：停用守卫、单用户规则优先、邮箱验证与投稿者派生、后台入口判定、访客 session 出参。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 停用用户也能使用功能",
        SERVER / "internal/accounts/roles.go",
        "if user == nil || !user.IsActive {",
        "if user == nil {",
        "TestCanUse",
    ),
    (
        "B 单用户规则不覆盖角色限制",
        SERVER / "internal/accounts/roles.go",
        """	// 1. 单用户规则优先
	if userRules != nil {
		if allowed, ok := userRules[feature]; ok {
			return allowed, nil
		}
	}""",
        """	// 1. 单用户规则优先
	if false && userRules != nil {
		if allowed, ok := userRules[feature]; ok {
			return allowed, nil
		}
	}""",
        "TestCanUse",
    ),
    (
        "C 未验证邮箱也能成为投稿者",
        SERVER / "internal/accounts/roles.go",
        "if isActive && emailVerified && canSubmitArticle {",
        "if isActive && canSubmitArticle {",
        "TestDerivedRoles",
    ),
    (
        "D 拥有 CapAdminEnter 不算进后台",
        SERVER / "internal/accounts/roles.go",
        "return viewer.HasCap(CapAdminEnter)",
        "return false",
        "TestRunsAdmin",
    ),
    (
        "E 访客 GET /api/session 返回非空对象",
        SERVER / "internal/accounts/api.go",
        "if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID == 0 {",
        "if false && (ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID == 0) {",
        "TestGetSessionApi",
    ),
]


def go_test(pkg: str, run: str | None) -> int:
    cmd = ["go", "test", pkg]
    if run:
        cmd += ["-count=1", "-run", run]
    return subprocess.run(cmd, cwd=SERVER).returncode


def main() -> int:
    print("== 基线 ==")
    if go_test("./internal/accounts/", None) != 0:
        print("基线是红的，变异没有意义，停")
        return 1
    print("基线绿")

    failed = []
    pkg = "./internal/accounts/"

    for label, path, target, replacement, test_name in MUTATIONS:
        original = path.read_text(encoding="utf-8")
        if target not in original:
            print(f"变异 {label} 找不到目标代码：{target[:40]!r}")
            return 2
        mutated = original.replace(target, replacement, 1)
        path.write_text(mutated, encoding="utf-8")
        try:
            code = go_test(pkg, test_name)
            if code == 0:
                print(f"  变异 {label} 活下来了（测试没抓住）")
                failed.append(label)
            else:
                print(f"  变异 {label} 被测试抓到了（退出码 {code}）")
        finally:
            path.write_text(original, encoding="utf-8")

    if failed:
        print(f"\n有 {len(failed)} 处变异活下来了：{failed}")
        return 1
    print(f"\n全部 {len(MUTATIONS)} 处变异均被测试抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
