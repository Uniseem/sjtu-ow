"""244 的七处变异：改密码不删其他会话、改密码不更新 password_changed_at、
改密码不校验旧密码、改密码允许新旧密码相同、改密码限流数字偏差、
退出登录不删库中会话、退出登录不清除会话 Cookie。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 改密码未作废该用户的其他会话（12 号文档 5.7 会话安全）",
        SERVER / "internal/accounts/service.go",
        "return s.sessions.DeleteOthersTx(txCtx, tx, u.ID, ctx.SessionToken)",
        "return nil // DeleteOthersTx bypassed",
        "./internal/accounts/",
        "TestChangePasswordSuccess",
    ),
    (
        "B 改密码未记录 password_changed_at 更新时间",
        SERVER / "internal/accounts/service.go",
        """\t\t_, err := tx.ExecContext(txCtx, `UPDATE users SET
\t\t\tpassword_hash = ?,
\t\t\tpassword_changed_at = ?,
\t\t\tupdated_at = ?
\t\t\tWHERE id = ?`,
\t\t\tpwdHash, db.FormatUTC(now), db.FormatUTC(now), u.ID)""",
        """\t\t_, err := tx.ExecContext(txCtx, `UPDATE users SET
\t\t\tpassword_hash = ?,
\t\t\tupdated_at = ?
\t\t\tWHERE id = ?`,
\t\t\tpwdHash, db.FormatUTC(now), u.ID)""",
        "./internal/accounts/",
        "TestChangePasswordSuccess",
    ),
    (
        "C 改密码绕过旧密码核验（安全防线失效）",
        SERVER / "internal/accounts/service.go",
        '\tif !ok {\n\t\treturn nil, api.InvalidFields(map[string][]string{"old_password": {"当前密码不正确。"}})\n\t}',
        '\tif false && !ok {\n\t\treturn nil, api.InvalidFields(map[string][]string{"old_password": {"当前密码不正确。"}})\n\t}',
        "./internal/accounts/",
        "TestChangePasswordWrongOldPassword",
    ),
    (
        "D 改密码允许新密码与旧密码相同",
        SERVER / "internal/accounts/service.go",
        '\tif in.OldPassword != "" && in.Password != "" && in.OldPassword == in.Password {\n\t\tfields["password"] = []string{"新密码不能与当前密码相同。"}\n\t}',
        '\tif false && in.OldPassword != "" && in.Password != "" && in.OldPassword == in.Password {\n\t\tfields["password"] = []string{"新密码不能与当前密码相同。"}\n\t}',
        "./internal/accounts/",
        "TestChangePasswordValidation",
    ),
    (
        "E 改密码限流数字偏差（R006 5次/分/人）",
        SERVER / "internal/platform/ratelimit/limits.go",
        'AuthChangePassword = Decl{Name: "auth_change_password", Kind: PerUser, N: 5, Window: time.Minute}',
        'AuthChangePassword = Decl{Name: "auth_change_password", Kind: PerUser, N: 50, Window: time.Minute}',
        "./internal/platform/ratelimit/",
        "TestTableMatchesDesign",
    ),
    (
        "F 退出登录未从数据库物理删除当前会话（5.7 会话安全）",
        SERVER / "internal/accounts/service.go",
        "if err := s.sessions.Delete(ctx.Context, ctx.SessionToken); err != nil {",
        "if false && s.sessions.Delete(ctx.Context, ctx.SessionToken) != nil {",
        "./internal/accounts/",
        "TestLogout",
    ),
    (
        "G 退出登录未通知管道清除会话 Cookie（浏览器仍残留有效凭证）",
        SERVER / "internal/accounts/service.go",
        "ctx.ClearSessionCookie()",
        "// ctx.ClearSessionCookie()",
        "./internal/accounts/",
        "TestLogout",
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
                print(f"  变异漏抓（变异后仍然绿）：{label}")
                failed.append(label)
            else:
                print(f"  抓到变异（红）：{label}")
        finally:
            path.write_text(original, encoding="utf-8")

    if failed:
        print(f"\n有 {len(failed)} 处变异没抓到：")
        for f in failed:
            print(f"  - {f}")
        return 1

    print(f"\n全部 {len(MUTATIONS)} 处变异抓到并已恢复代码。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
