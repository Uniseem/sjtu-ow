"""Round 176: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/176-category-delete/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "content/tests/test_category_delete.py"


def t(name):
    return f"{T}::{name}"


LISTED = t("test_only_empty_categories_offer_delete")
STAYS = t("test_a_used_category_says_why_and_stays")
BULK = t("test_bulk_delete_skips_it")
H = "content/wagtail_hooks.py"

MUTATIONS = [
    ("bulk delete asks nothing", H, '        if action == "delete" and instance.articles.exists():\n            return False\n', "", [BULK]),
    ("policy not registered", H, "register_permission_policy(\n    ArticleCategory, ArticleCategoryPermissionPolicy(ArticleCategory)\n)\n", "", [BULK]),
    ("the list offers it anyway", H, "        if instance.articles.exists():\n            return None\n        return super().get_delete_url(instance)\n", "        return super().get_delete_url(instance)\n", [LISTED]),
    ("the delete page goes ahead", H, "        count = self.object.articles.count()\n        if count:\n", "        count = self.object.articles.count()\n        if False:\n", [STAYS]),
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
