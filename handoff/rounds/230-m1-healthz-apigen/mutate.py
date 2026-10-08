"""230 的四处变异：磁盘阈值、积压按到期时间、对外藏详情、生成器用 json 标签。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "server"

MUTATIONS = [
    (
        "A 剩余 20% 也算健康",
        SERVER / "internal/platform/health/health.go",
        "if total == 0 || free*5 <= total {",
        "if total == 0 || free*5 < total {",
        "TestDiskAtTwentyPercentIsDown",
    ),
    (
        "B 积压不看到期时间",
        SERVER / "internal/platform/health/health.go",
        "cutoff := db.FormatUTC(now.Add(-BacklogAfter))",
        "cutoff := db.FormatUTC(now.Add(-time.Minute))",
        "TestBacklogUsesRunAfter",
    ),
    (
        "C 对外也给详情",
        SERVER / "internal/platform/health/health.go",
        "	if !detail {",
        "	if false && !detail {",
        "TestProbeRollsBackAndHidesDetail",
    ),
    (
        "D 生成器不用 json 标签",
        SERVER / "internal/platform/apigen/apigen.go",
        """		tag := f.Tag.Get("json")
		if tag == "-" {""",
        """		tag := f.Tag.Get("xml")
		if tag == "-" {""",
        "TestRenderEmitsTypesAndNav",
    ),
]


def go_test(pkg: str, run: str | None) -> int:
    cmd = ["go", "test", pkg]
    if run:
        cmd += ["-count=1", "-run", run]
    return subprocess.run(cmd, cwd=SERVER).returncode


def main() -> int:
    print("== 基线 ==")
    if go_test("./internal/platform/health/", None) != 0 or go_test("./internal/platform/apigen/", None) != 0:
        print("基线是红的，变异没有意义，停")
        return 1
    print("基线绿")

    failed = []
    pkgs = {
        "TestDiskAtTwentyPercentIsDown": "./internal/platform/health/",
        "TestBacklogUsesRunAfter": "./internal/platform/health/",
        "TestProbeRollsBackAndHidesDetail": "./internal/platform/health/",
        "TestRenderEmitsTypesAndNav": "./internal/platform/apigen/",
    }
    for name, path, old, new, test in MUTATIONS:
        text = path.read_text(encoding="utf-8")
        n = text.count(old)
        if n != 1:
            print(f"{name}：原文出现 {n} 次，应正好 1 次，停")
            return 1
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"== {name}（应红）==")
        try:
            code = go_test(pkgs[test], test)
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
