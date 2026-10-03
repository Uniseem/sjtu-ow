"""Round 109: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/109-cover-pool/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_cover_pool.py"
COVERS = "core/covers.py"
TAG = "core/templatetags/ow.py"
SIGNALS = "content/signals.py"

MUTATIONS = [
    ("articles and tournaments share pictures", COVERS,
     "    offset = placeholders.KIND_OFFSETS.get(obj._meta.label_lower, 0)\n",
     "    offset = 0\n",
     [f"{T}::test_each_object_keeps_its_own_pool_picture"]),
    ("any picture counts as a cover", COVERS,
     ".objects.filter(collection__name=DEFAULT_COVER_COLLECTION)",
     ".objects.all()",
     [f"{T}::test_pictures_elsewhere_are_not_in_the_pool"]),
    ("thumbnails come one by one", COVERS,
     '        .prefetch_related("renditions")\n', "",
     [f"{T}::test_a_long_list_looks_at_the_pool_once"]),
    ("every card looks the pool up", "sjtu_ow/settings/base.py",
     '                "core.context_processors.cover_pool",\n', "",
     [f"{T}::test_a_long_list_looks_at_the_pool_once"]),
    ("pool pictures stand still", TAG,
     '        classes += ["c-drift", f"c-drift--{(obj.pk or 0) % covers.DRIFTS + 1}"]\n', "",
     [f"{T}::test_pool_pictures_drift_and_keep_the_spots_class_and_size"]),
    ("cards load at once", TAG,
     "        mark_safe(' loading=\"lazy\"') if lazy else \"\",\n", '        "",\n',
     [f"{T}::test_pool_pictures_drift_and_keep_the_spots_class_and_size"]),
    ("an empty pool shows nothing", TAG,
     "        src = cover_placeholder(obj)\n", '        src = ""\n',
     [f"{T}::test_an_empty_pool_falls_back_to_the_drawn_placeholder"]),
    ("a card skips the pool", "templates/components/post_card.html",
     '{% else %}{% cover_fallback article "fill-960x540-c50" lazy=True %}',
     '{% else %}<img src="{{ article|cover_placeholder }}" width="960" height="540" alt="" loading="lazy">',
     [f"{T}::test_no_template_reaches_for_the_placeholder_directly"]),
    ("scrims skip the pool", "scrims/templates/scrims/detail.html",
     '{% cover_fallback scrim "fill-2400x900-c50" "c-stage__img" %}',
     '<img src="{{ scrim|cover_placeholder }}" width="2400" height="900" class="c-stage__img" alt="">',
     [f"{T}::test_scrim_banners_take_a_pool_picture"]),
    ("a picture leaving the pool is missed", SIGNALS,
     "    if left or _in_cover_pool(instance.collection_id):\n",
     "    if _in_cover_pool(instance.collection_id):\n",
     [f"{T}::test_changes_to_the_pool_regenerate_the_site"]),
    ("a deleted picture is missed", SIGNALS,
     "    if _in_cover_pool(instance.collection_id):\n        prerender.request_all_soon()\n",
     "    if False:\n        prerender.request_all_soon()\n",
     [f"{T}::test_changes_to_the_pool_regenerate_the_site"]),
    ("every upload regenerates everything", "core/prerender.py",
     "    if not cache.add(ALL_PENDING_KEY, 1, COALESCE_SECONDS):\n",
     "    if False:\n",
     [f"{T}::test_a_batch_of_uploads_regenerates_once"]),
    ("init_site makes no pool", "core/management/commands/init_site.py",
     "        collection = ensure_default_cover_collection()\n",
     "        collection = ensure_submission_image_collection()\n",
     [f"{T}::test_init_site_makes_the_pool"]),
    ("the drift fights the hover zoom", "assets/css/input.css",
     "      scale: 1.04;\n      translate: -1.2% -0.8%;\n",
     "      transform: scale(1.04) translate(-1.2%, -0.8%);\n",
     [f"{T}::test_the_drift_moves_only_scale_and_translate"]),
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
