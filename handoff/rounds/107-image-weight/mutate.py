"""Round 107: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/107-image-weight/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_images.py"
SETTINGS = "sjtu_ow/settings/base.py"

MUTATIONS = [
    ("PNG thumbnails stay PNG", SETTINGS,
     'WAGTAILIMAGES_FORMAT_CONVERSIONS = {"png": "webp", "jpeg": "webp"}',
     'WAGTAILIMAGES_FORMAT_CONVERSIONS = {"jpeg": "webp"}',
     [f"{T}::test_thumbnails_are_webp_whatever_was_uploaded[PNG]"]),
    ("JPEG thumbnails stay JPEG", SETTINGS,
     'WAGTAILIMAGES_FORMAT_CONVERSIONS = {"png": "webp", "jpeg": "webp"}',
     'WAGTAILIMAGES_FORMAT_CONVERSIONS = {"png": "webp"}',
     [f"{T}::test_thumbnails_are_webp_whatever_was_uploaded[JPEG]"]),
    ("WebP quality drifts", SETTINGS,
     "WAGTAILIMAGES_WEBP_QUALITY = 80", "WAGTAILIMAGES_WEBP_QUALITY = 60",
     [f"{T}::test_thumbnails_are_webp_whatever_was_uploaded[PNG]"]),
    ("share images become WebP", "content/seo.py",
     'image.get_rendition("fill-1200x630|format-jpeg")',
     'image.get_rendition("fill-1200x630")',
     [f"{T}::test_share_images_stay_jpeg"]),
    ("article pictures load at once", "content/templates/content/blocks/image.html",
     ' loading="lazy" %}', " %}",
     [f"{T}::test_pictures_below_the_first_screen_load_lazily"]),
    ("a member card loads at once", "members/templates/members/index.html",
     'fill-400x400 alt="" loading="lazy"', 'fill-400x400 alt=""',
     [f"{T}::test_pictures_below_the_first_screen_load_lazily"]),
    ("the article cover loads lazily", "content/templates/content/article_page.html",
     'class="c-cover__img" alt=""', 'class="c-cover__img" alt="" loading="lazy"',
     [f"{T}::test_first_screen_pictures_are_not_lazy"]),
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
            assert text.count(old) >= 1, (label, text.count(old))
            text = text.replace(old, new, 1)
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
