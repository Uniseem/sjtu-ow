"""241 的九处变异：核验不比哈希、码不作废、密码错也过、停用放行、未验证发会话、PBKDF2 不升级、失败不限流、Cookie 不写、防枚举文案破功。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 核验不比哈希（任何码都过）",
        SERVER / "internal/accounts/service.go",
        "if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {",
        "if len(sum) > 999 && subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {",
        "TestVerifyEmailAttempts",
    ),
    (
        "B 3 次用尽不删码",
        SERVER / "internal/accounts/service.go",
        "if c.Attempts+1 >= 3 {",
        "if false && c.Attempts+1 >= 3 {",
        "TestVerifyEmailAttempts",
    ),
    (
        "C 密码错也放行",
        SERVER / "internal/accounts/service.go",
        "if !ok {\n\t\ts.hitLoginFailure(ctx, emailNorm)",
        "if ok && false {\n\t\ts.hitLoginFailure(ctx, emailNorm)",
        "TestLoginWrongPasswordUnified",
    ),
    (
        "D 停用账号放行",
        SERVER / "internal/accounts/service.go",
        "if !u.IsActive {\n\t\t// 密码已经对了",
        "if false && !u.IsActive {\n\t\t// 密码已经对了",
        "TestLoginDisabled",
    ),
    (
        "E 未验证也发会话（verify_required 分支失效）",
        SERVER / "internal/accounts/service.go",
        "if u.EmailVerifiedAt == nil {",
        "if false && u.EmailVerifiedAt == nil {",
        "TestLoginUnverifiedResendsCode",
    ),
    (
        "F PBKDF2 验过不升级",
        SERVER / "internal/accounts/service.go",
        "if upgrade {",
        "if false && upgrade {",
        "TestLoginPBKDF2Upgrade",
    ),
    (
        "G 失败锁先查失效（锁定期放行）",
        SERVER / "internal/accounts/service.go",
        "if err == nil && n >= int64(ratelimit.AuthLoginFailedKey.N) {",
        "if false && err == nil && n >= int64(ratelimit.AuthLoginFailedKey.N) {",
        "TestLoginFailedRateLimitPerAccount",
    ),
    (
        "H 会话 Cookie 不写响应头",
        SERVER / "internal/platform/api/registry.go",
        "for _, tok := range ctx.DrainSessionCookies() {",
        "for _, tok := range []string{} {",
        "TestVerifyEmailApi",
    ),
    (
        "I 密码错时文案破功（防枚举）",
        SERVER / "internal/accounts/service.go",
        "\tif !ok {\n\t\ts.hitLoginFailure(ctx, emailNorm)\n\t\treturn nil, api.Unauthorized(\"邮箱或密码不正确\")",
        "\tif !ok {\n\t\ts.hitLoginFailure(ctx, emailNorm)\n\t\treturn nil, api.Unauthorized(\"变异：邮箱或密码不正确\")",
        "TestLoginWrongPasswordUnified",
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
        if original.count(target) != 1:
            print(f"变异 {label} 目标出现 {original.count(target)} 次（要恰好 1 次），停")
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
