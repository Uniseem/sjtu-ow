"""240 的五处变异：不存验证码哈希、跳过昵称长度校验、跳过协议勾选校验、防枚举分支失效、移除注册限流。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 不存验证码哈希",
        SERVER / "internal/accounts/service.go",
        'if err := s.store.InsertEmailCode(ctx, tx, "signup", emailNorm, codeHash, now, now.Add(15*time.Minute)); err != nil {',
        'if false { _ = s.store.InsertEmailCode(ctx, tx, "signup", emailNorm, codeHash, now, now.Add(15*time.Minute));',
        "TestRegisterSuccess",
    ),
    (
        "B 跳过昵称长度校验",
        SERVER / "internal/accounts/service.go",
        "} else if runeLen < 2 || runeLen > 16 {",
        "} else if false && (runeLen < 2 || runeLen > 16) {",
        "TestRegisterFieldValidation",
    ),
    (
        "C 跳过协议勾选校验",
        SERVER / "internal/accounts/service.go",
        "if !in.AgreeTerms {",
        "if false && !in.AgreeTerms {",
        "TestRegisterFieldValidation",
    ),
    (
        "D 防枚举分支失效",
        SERVER / "internal/accounts/service.go",
        "if existing != nil {",
        "if false && existing != nil {",
        "TestRegisterAntiEnumeration",
    ),
    (
        "E 注册接口移除限流",
        SERVER / "internal/accounts/api.go",
        "api.Limit(ratelimit.AuthSignup)",
        'api.NoLimit("变异测试")',
        "TestRegisterApiRateLimit",
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
