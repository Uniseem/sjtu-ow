"""242 的七处变异：旧码不作废、账号不限流、未注册泄露（防枚举失效）、已验证仍发验证码、停用账号仍发信、秒级时间片退化为分钟、resend-code 偷发会话 Cookie。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 重发不作废旧码",
        SERVER / "internal/accounts/service.go",
        "\terr = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {\n\t\tif err := s.store.DeleteEmailCodes(ctx, tx, \"signup\", emailNorm); err != nil {",
        "\terr = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {\n\t\tif false && s.store.DeleteEmailCodes(ctx, tx, \"signup\", emailNorm) != nil {",
        "./internal/accounts/",
        "TestResendCodeUnverifiedUser",
    ),
    (
        "B 账号级 10 秒限流失效",
        SERVER / "internal/accounts/service.go",
        "if !ok {\n\t\t\treturn nil, api.TooManyRequests(retry)\n\t\t}",
        "if false && !ok {\n\t\t\treturn nil, api.TooManyRequests(retry)\n\t\t}",
        "./internal/accounts/",
        "TestResendCodeRateLimitKey",
    ),
    (
        "C 未注册邮箱报错（防枚举 R004 破功）",
        SERVER / "internal/accounts/service.go",
        "\tif u == nil || !u.IsActive {\n\t\t// 账号不存在或已停用：静默成功，不发信（R004 防枚举）\n\t\treturn successRes, nil\n\t}",
        "\tif u == nil || !u.IsActive {\n\t\treturn nil, api.NotFound(\"账号不存在\")\n\t}",
        "./internal/accounts/",
        "TestResendCodeUnregisteredEmail",
    ),
    (
        "D 已验证账号仍走生成验证码逻辑",
        SERVER / "internal/accounts/service.go",
        "\tif u.EmailVerifiedAt != nil {\n\t\t// 账号已验证过：发提示信告知无需再次验证，不生成验证码（防枚举）",
        "\tif false && u.EmailVerifiedAt != nil {\n\t\t// 账号已验证过：发提示信告知无需再次验证，不生成验证码（防枚举）",
        "./internal/accounts/",
        "TestResendCodeAlreadyVerifiedUser",
    ),
    (
        "E 停用账号仍发信",
        SERVER / "internal/accounts/service.go",
        "\tif u == nil || !u.IsActive {\n\t\t// 账号不存在或已停用：静默成功，不发信（R004 防枚举）\n\t\treturn successRes, nil\n\t}",
        "\tif u == nil {\n\t\treturn successRes, nil\n\t}",
        "./internal/accounts/",
        "TestResendCodeDeactivatedUser",
    ),
    (
        "F 秒级时间片退化为分钟片（10秒窗口被扩大为整分钟）",
        SERVER / "internal/platform/ratelimit/ratelimit.go",
        "\tcase window < time.Minute:\n\t\treturn t.Truncate(window).Format(\"20060102T150405\")",
        "\tcase window < time.Minute:\n\t\treturn t.Format(\"20060102T1504\")",
        "./internal/platform/ratelimit/",
        "TestSliceMatchesWindow",
    ),
    (
        "G resend-code 发出会话 Cookie（破坏唯一建会话入口）",
        SERVER / "internal/accounts/api.go",
        "func (m *Module) resendCode(ctx *app.Ctx, in ResendCodeIn) (ResendCodeOut, error) {\n\tres, err := m.svc.ResendCode(ctx.Context, ResendCodeInput(in))\n\tif err != nil {\n\t\treturn ResendCodeOut{}, err\n\t}\n\treturn ResendCodeOut{",
        "func (m *Module) resendCode(ctx *app.Ctx, in ResendCodeIn) (ResendCodeOut, error) {\n\tres, err := m.svc.ResendCode(ctx.Context, ResendCodeInput(in))\n\tif err != nil {\n\t\treturn ResendCodeOut{}, err\n\t}\n\tctx.SetSessionCookie(\"mutated-token\")\n\treturn ResendCodeOut{",
        "./internal/accounts/",
        "TestResendCodeApi",
    ),
]


def go_test(pkg: str, run: str | None) -> int:
    cmd = ["go", "test", pkg]
    if run:
        cmd += ["-count=1", "-run", run]
    return subprocess.run(cmd, cwd=SERVER).returncode


def main() -> int:
    print("== 基线 ==")
    if go_test("./internal/accounts/", None) != 0 or go_test("./internal/platform/ratelimit/", None) != 0:
        print("基线是红的，变异没有意义，停")
        return 1
    print("基线绿")

    failed = []

    for label, path, target, replacement, pkg, test_name in MUTATIONS:
        original = path.read_text(encoding="utf-8")
        if target not in original:
            print(f"变异 {label} 找不到目标代码：{target[:40]!r}")
            return 2
        if original.count(target) != 1:
            print(f"变异 {label} 目标出现 {original.count(target)} 次（要恰好 1 次），停")
            return 2

        mutated = original.replace(target, replacement)
        path.write_text(mutated, encoding="utf-8")
        try:
            rc = go_test(pkg, test_name)
            if rc == 0:
                print(f"  变异 {label} 居然绿了（漏测！）")
                failed.append(label)
            else:
                print(f"  变异 {label} 被测试抓到了（退出码 {rc}）")
        finally:
            path.write_text(original, encoding="utf-8")

    if failed:
        print(f"\n有 {len(failed)} 处变异没被抓到：{failed}")
        return 1

    print(f"\n全部 {len(MUTATIONS)} 处变异均被测试抓到")
    return 0


if __name__ == "__main__":
    sys.exit(main())
