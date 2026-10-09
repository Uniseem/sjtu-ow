"""243 的七处变异：验证码非 3 分钟有效、重发不作废旧码、未注册泄露状态（防枚举失效）、
账号级限流失效、错码不计数与 3 次不作废、重置后未作废旧会话、reset-password-confirm 偷发会话 Cookie。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 重置验证码有效期非 3 分钟（R003 违背）",
        SERVER / "internal/accounts/service.go",
        'if err := s.store.InsertEmailCode(ctx, tx, "password_reset", emailNorm, codeHash, now, now.Add(3*time.Minute)); err != nil {',
        'if err := s.store.InsertEmailCode(ctx, tx, "password_reset", emailNorm, codeHash, now, now.Add(15*time.Minute)); err != nil {',
        "./internal/accounts/",
        "TestRequestPasswordResetActiveUserCodeAndLetter",
    ),
    (
        "B 重发找回密码验证码不作废旧码",
        SERVER / "internal/accounts/service.go",
        'if err := s.store.DeleteEmailCodes(ctx, tx, "password_reset", emailNorm); err != nil {\n\t\t\treturn err\n\t\t}\n\t\tif err := s.store.InsertEmailCode(ctx, tx, "password_reset", emailNorm, codeHash, now, now.Add(3*time.Minute)); err != nil {',
        'if false && s.store.DeleteEmailCodes(ctx, tx, "password_reset", emailNorm) != nil {\n\t\t\treturn err\n\t\t}\n\t\tif err := s.store.InsertEmailCode(ctx, tx, "password_reset", emailNorm, codeHash, now, now.Add(3*time.Minute)); err != nil {',
        "./internal/accounts/",
        "TestRequestPasswordResetActiveUserCodeAndLetter",
    ),
    (
        "C 未注册邮箱报错泄露账号不存在（R004 防枚举失效）",
        SERVER / "internal/accounts/service.go",
        '\tif u == nil {\n\t\t// 邮箱未注册：发「这个邮箱还没有注册」提醒信',
        '\tif u == nil {\n\t\treturn nil, api.NotFound("邮箱未注册")\n\t\t// 邮箱未注册：发「这个邮箱还没有注册」提醒信',
        "./internal/accounts/",
        "TestRequestPasswordResetUnknownEmailAntiEnumeration",
    ),
    (
        "D 找回密码账号级限流失效（R006）",
        SERVER / "internal/accounts/service.go",
        'retry, ok, err := s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResetPasswordKey)\n\t\tif err != nil {\n\t\t\treturn nil, err\n\t\t}\n\t\tif !ok {\n\t\t\treturn nil, api.TooManyRequests(retry)\n\t\t}',
        'retry, ok, err := s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResetPasswordKey)\n\t\tif err != nil {\n\t\t\treturn nil, err\n\t\t}\n\t\tif false && !ok {\n\t\t\treturn nil, api.TooManyRequests(retry)\n\t\t}',
        "./internal/accounts/",
        "TestRequestPasswordResetRateLimitKey",
    ),
    (
        "E 核验错码不递增 attempts / 3 次不作废（R003）",
        SERVER / "internal/accounts/service.go",
        'c, err := s.store.GetLatestEmailCodeTx(ctx, tx, "password_reset", emailNorm)\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}\n\t\t// 过期、用尽（最多 3 次尝试）、没有码：直接失败，不自增 attempts\n\t\tif c == nil || !now.Before(c.ExpiresAt) || c.Attempts >= 3 {\n\t\t\treturn nil\n\t\t}\n\t\tsum := sha256.Sum256([]byte(code))\n\t\tif subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {\n\t\t\tif err := s.store.BumpEmailCodeAttempts(ctx, tx, c.ID); err != nil {',
        'c, err := s.store.GetLatestEmailCodeTx(ctx, tx, "password_reset", emailNorm)\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}\n\t\t// 过期、用尽（最多 3 次尝试）、没有码：直接失败，不自增 attempts\n\t\tif c == nil || !now.Before(c.ExpiresAt) || c.Attempts >= 3 {\n\t\t\treturn nil\n\t\t}\n\t\tsum := sha256.Sum256([]byte(code))\n\t\tif subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {\n\t\t\treturn nil\n\t\t\tif err := s.store.BumpEmailCodeAttempts(ctx, tx, c.ID); err != nil {',
        "./internal/accounts/",
        "TestResetPasswordConfirmCodeAttemptsAndExpiry",
    ),
    (
        "F 确认重置密码成功后未清理该用户现有会话（5.7 会话安全）",
        SERVER / "internal/accounts/service.go",
        '_, err = tx.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = ?`, u.ID)\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}',
        '// sessions not deleted\n\t\tif false {\n\t\t\t_, err = tx.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = ?`, u.ID)\n\t\t}',
        "./internal/accounts/",
        "TestResetPasswordConfirmSuccess",
    ),
    (
        "G reset-password-confirm 偷发会话 Cookie（违反 5.7 唯一入口规则）",
        SERVER / "internal/accounts/api.go",
        'func (m *Module) resetPasswordConfirm(ctx *app.Ctx, in ResetPasswordConfirmIn) (ResetPasswordConfirmOut, error) {\n\tres, err := m.svc.ResetPasswordConfirm(ctx.Context, ResetPasswordConfirmInput(in))\n\tif err != nil {\n\t\treturn ResetPasswordConfirmOut{}, err\n\t}\n\treturn ResetPasswordConfirmOut{',
        'func (m *Module) resetPasswordConfirm(ctx *app.Ctx, in ResetPasswordConfirmIn) (ResetPasswordConfirmOut, error) {\n\tres, err := m.svc.ResetPasswordConfirm(ctx.Context, ResetPasswordConfirmInput(in))\n\tif err != nil {\n\t\treturn ResetPasswordConfirmOut{}, err\n\t}\n\tctx.SetSessionCookie("leaked-token")\n\treturn ResetPasswordConfirmOut{',
        "./internal/accounts/",
        "TestResetPasswordConfirmApi",
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
