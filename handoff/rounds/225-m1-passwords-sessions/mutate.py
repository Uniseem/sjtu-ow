"""225 的五处变异：每处改坏一条，确认对应测试变红，然后改回来。

基线先跑一遍；基线就是红的话每处都会显得「被抓到」（083 的坑）。
改的原文都长到文件里只出现一次。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"
AUTH = SERVER / "internal/platform/auth"

MUTATIONS = [
    (
        "A 不可用密码也能登录",
        AUTH / "password.go",
        'return encoded != "" && !strings.HasPrefix(encoded, "!")',
        'return encoded != ""',
        "TestUnusablePasswordNeverMatches",
    ),
    (
        "B PBKDF2 验过不升级",
        AUTH / "password.go",
        "return ok, ok, nil",
        "return ok, false, nil",
        "TestPBKDF2MatchesHashlib",
    ),
    (
        "C 库里存令牌原文",
        AUTH / "session.go",
        "hashToken(raw), userID, db.FormatUTC(now), db.FormatUTC(now.Add(SessionTTL)), db.FormatUTC(now))",
        "hex.EncodeToString(raw), userID, db.FormatUTC(now), db.FormatUTC(now.Add(SessionTTL)), db.FormatUTC(now))",
        "TestSessionCreateLookupAndExpiry",
    ),
    (
        "D 改密码把当前会话也删了",
        AUTH / "session.go",
        "DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?",
        "DELETE FROM sessions WHERE user_id = ? AND token_hash = ?",
        "TestDeleteOthersKeepsCurrent",
    ),
    (
        "E 不再查和邮箱昵称像不像",
        AUTH / "validate.go",
        "if quickRatio(pwd, []rune(part)) >= maxSimilarity {",
        "if false && quickRatio(pwd, []rune(part)) >= maxSimilarity {",
        "TestValidatePassword",
    ),
]


def go_test(run: str | None) -> int:
    cmd = ["go", "test", "./internal/platform/auth/"]
    if run:
        cmd += ["-count=1", "-run", run]
    return subprocess.run(cmd, cwd=SERVER).returncode


def main() -> int:
    print("== 基线 ==")
    if go_test(None) != 0:
        print("基线是红的，变异没有意义，停")
        return 1
    print("基线绿")

    failed = []
    for name, path, old, new, test in MUTATIONS:
        text = path.read_text(encoding="utf-8")
        n = text.count(old)
        if n != 1:
            print(f"{name}：原文出现 {n} 次，应正好 1 次，停")
            return 1
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"== {name}（应红）==")
        try:
            code = go_test(test)
        finally:
            path.write_text(text, encoding="utf-8")
        if code == 0:
            print(f"{name}：改坏了测试还是绿的")
            failed.append(name)
        else:
            print(f"{name}：变红，已恢复")

    if failed:
        print("没抓到：", "、".join(failed))
        return 1
    print("五处变异全部变红后恢复")
    return 0


if __name__ == "__main__":
    sys.exit(main())
