"""228 的四处变异：每处改坏一条，确认对应测试变红，然后改回来。

基线先跑一遍；基线就是红的话每处都会显得「被抓到」（083 的坑）。
改的原文都长到文件里只出现一次。
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 落款不再是祝好",
        SERVER / "internal/platform/mail/letter.go",
        "add(Closing)",
        'add("此致")',
        "TestTextReadsAsALetter",
    ),
    (
        "B 同一封信不合并收件人",
        SERVER / "internal/platform/outbox/outbox.go",
        "if found {",
        "if false && found {",
        "TestHoldMergesAndDecideClaimsOnce",
    ),
    (
        "C 确认可以认领第二次",
        SERVER / "internal/platform/outbox/outbox.go",
        "WHERE id = ? AND state = 'waiting'",
        "WHERE id = ?",
        "TestHoldMergesAndDecideClaimsOnce",
    ),
    (
        "D 不看发信名单",
        SERVER / "internal/platform/mail/smtp.go",
        "if !allowed(cfg.Allowlist, to.Address) {",
        "if false && !allowed(cfg.Allowlist, to.Address) {",
        "TestDeliverSkipsAllowlistAndUnconfigured",
    ),
]


def go_test(run: str | None) -> int:
    cmd = ["go", "test", "./internal/platform/mail/", "./internal/platform/outbox/"]
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
    print("四处变异全部变红后恢复")
    return 0


if __name__ == "__main__":
    sys.exit(main())
