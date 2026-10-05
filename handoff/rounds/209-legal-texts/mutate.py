"""Round 209: break each rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).
``--check`` only looks that every mutation still applies.

bash scripts/remote-check.sh run uv run python handoff/rounds/209-legal-texts/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

PROCESSORS = (
    "content/tests/test_legal_pages.py::"
    "test_the_privacy_draft_names_every_processor_the_site_uses"
)
SAYS = "core/tests/test_site_name.py::test_the_pages_letters_and_settings_say_sjtu_ow"
BLANKS = "core/tests/test_setup_checklist.py::test_the_agreements_need_their_blanks_filled"

MUTATIONS = [
    # Every mention goes: the policy names ZgoCloud in two places, and taking
    # out one of them still names it (the first run's miss).
    ("the forwarding server left out", "content/legal/privacy.md",
     "ZgoCloud", "某家服务商", [PROCESSORS]),
    ("a blank left in the policy", "content/legal/privacy.md",
     "生效日期：2026 年 10 月 5 日", "生效日期：【YYYY 年 M 月 D 日】", [PROCESSORS]),
    ("the hero back on one line", "content/templates/content/home_page.html",
     "<span>上海交通大学</span><span>守望先锋社区</span>",
     "<span>SJTU-</span><span>OW</span>", [SAYS]),
    ("blanks not counted", "core/admin_setup.py",
     '        blanks = text.count("【")', "        blanks = 0", [BLANKS]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
    ).returncode


def _text(rel):
    return (ROOT / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def check():
    """Each mutation must find its text; every occurrence is replaced."""
    bad = [
        (label, _text(rel).count(old))
        for label, rel, old, _new, _tests in MUTATIONS
        if _text(rel).count(old) < 1
    ]
    print("mutations:", len(MUTATIONS), "not applying:", bad or "none")
    return not bad


def main():
    if not check():
        sys.exit(1)
    if "--check" in sys.argv:
        return
    every = sorted({t for *_rest, tests in MUTATIONS for t in tests})
    assert run(every) == 0, "baseline is red"
    print("baseline green,", len(every), "tests")
    failed = []
    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        backup = path.with_suffix(path.suffix + ".mutbak")
        shutil.copy2(path, backup)
        try:
            raw = path.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            text = raw.replace("\r\n", "\n").replace(old, new)
            path.write_bytes(
                (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")
            )
            for test in tests:
                red = run([test]) != 0
                name = test.split("::")[-1]
                print(("caught " if red else "MISSED ") + label + " -> " + name)
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/**/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")


if __name__ == "__main__":
    main()
