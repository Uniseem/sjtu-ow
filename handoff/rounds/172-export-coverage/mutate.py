"""Round 172: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/172-export-coverage/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_export_coverage.py"


def t(name):
    return f"{T}::{name}"


LIST = t("test_every_column_pointing_at_a_person_is_accounted_for")
OUT = t("test_comments_likes_and_rules_go_out")
S = "accounts/services.py"

MUTATIONS = [
    ("comments forgotten again", S, '    "comments.Comment.author": "comments",\n', "", [LIST]),
    ("listed but not exported", S, '        "comment_likes": [\n', '        "liked_comments": [\n', [LIST, OUT]),
    ("listed twice", S, '    "comments.Comment.reply_to_user": "别人回复这个人的评论，是别人写的内容",\n', '    "comments.Comment.reply_to_user": "别人回复这个人的评论，是别人写的内容",\n    "comments.Comment.author": "x",\n', [LIST]),
    ("others' comments too", S, "            for comment in Comment.objects.filter(author=user)\n", "            for comment in Comment.objects.all()\n", [OUT]),
    ("hidden shown as public", S, '                else ("已隐藏" if comment.is_hidden else "公开"),\n', '                else "公开",\n', [OUT]),
    ("reason left out", S, '                "reason": rule.note,\n', "", [OUT]),
]


def run(tests):
    return subprocess.run(
        [PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
        cwd=ROOT, env=ENV, capture_output=True, text=True,
    ).returncode


def main():
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
            text = raw.replace("\r\n", "\n")
            assert text.count(old) == 1, (label, text.count(old))
            text = text.replace(old, new)
            path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
            for test in tests:
                red = run([test]) != 0
                print(("caught " if red else "MISSED ") + label + " -> " + test.split("::")[1])
                if not red:
                    failed.append((label, test))
        finally:
            shutil.copy2(backup, path)
            backup.unlink()
            folder = rel.rsplit("/", 1)[0]
            for cache in ROOT.glob(folder + "/__pycache__/*.pyc"):
                cache.unlink()
    assert run(every) == 0, "not green after restoring"
    print("restored and green;", "missed:", failed or "none")
    return 1 if failed else 0


sys.exit(main())
