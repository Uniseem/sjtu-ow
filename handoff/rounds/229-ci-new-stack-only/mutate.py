"""229 的两处变异：CI 又跑现行站、脚本默认打开现行站，对应测试都应红。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A CI 又跑 pytest",
        ROOT / ".github/workflows/ci.yml",
        "        run: go test ./...",
        "        run: go test ./...\n      - name: legacy\n        run: uv run pytest",
        "TestCIOnlyRunsTheNewStack",
    ),
    (
        "B 测试机整组又跑 pytest",
        ROOT / "scripts/check.sh",
        "    go test ./...",
        "    go test ./...\n    uv run pytest -q",
        "TestCIOnlyRunsTheNewStack",
    ),
]


def go_test(run: str | None) -> int:
    cmd = ["go", "test", "./internal/platform/config/"]
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
    print("两处变异全部变红后恢复")
    return 0


if __name__ == "__main__":
    sys.exit(main())
