"""Round 111: break each new rule once and check its test goes red (AGENTS.md
rule 7). Runs the tests first and stops if they are not green (083).

uv run python handoff/rounds/111-default-avatars/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "accounts/tests/test_default_avatar.py"
AVATARS = "core/avatars.py"

MUTATIONS = [
    ("everyone gets the first face", AVATARS,
     "    return images[person.pk % len(images)]\n",
     "    return images[0]\n",
     [f"{T}::test_each_person_keeps_their_own_face"]),
    ("the pool overrides people's own pictures", AVATARS,
     '    if person is None or getattr(person, "avatar_id", None):\n',
     "    if person is None:\n",
     [f"{T}::test_their_own_picture_wins"]),
    ("closed accounts get a face", AVATARS,
     '    if not getattr(person, "is_active", False) or not person.pk:\n',
     "    if not person.pk:\n",
     [f"{T}::test_closed_accounts_keep_the_initial"]),
    ("an empty pool breaks the page", AVATARS,
     "    if not images:\n        return None\n    return images[person.pk % len(images)]\n",
     "    return images[person.pk % len(images)]\n",
     [f"{T}::test_an_empty_pool_keeps_the_initial"]),
    ("faces come from the cover pool", AVATARS,
     "    return covers.load_pool(DEFAULT_AVATAR_COLLECTION)\n",
     "    return covers.load_pool()\n",
     [f"{T}::test_the_folders_under_the_pool_count_and_others_do_not"]),
    ("every face looks the pool up", "sjtu_ow/settings/base.py",
     '                "core.context_processors.avatar_pool",\n', "",
     [f"{T}::test_a_long_list_looks_at_the_pool_once"]),
    ("pool faces load at once", "core/templatetags/ow.py",
     '    return image.get_rendition(spec).img_tag({"alt": "", "loading": "lazy"})\n',
     '    return image.get_rendition(spec).img_tag({"alt": ""})\n',
     [f"{T}::test_someone_without_a_picture_gets_a_pool_face"]),
    ("big faces use the small thumbnail", "templates/components/avatar.html",
     '{% default_avatar person "fill-176x176" as face %}',
     '{% default_avatar person "fill-88x88" as face %}',
     [f"{T}::test_someone_without_a_picture_gets_a_pool_face"]),
    ("the member card skips the pool", "members/templates/members/index.html",
     '{% else %}{% default_avatar member.user "fill-400x400" as face %}{% if face %}{{ face }}{% else %}{{ member.user.nickname|initial }}{% endif %}{% endif %}',
     "{% else %}{{ member.user.nickname|initial }}{% endif %}",
     [f"{T}::test_the_member_card_uses_the_pool_too",
      f"{T}::test_no_template_prints_the_initial_without_trying_the_pool"]),
    ("changes to the avatar pool are missed", "content/signals.py",
     "    return covers.in_pool(collection_id) or avatars.in_pool(collection_id)\n",
     "    return covers.in_pool(collection_id)\n",
     [f"{T}::test_changes_to_the_pool_regenerate_the_site"]),
    ("closing an account leaves stale faces", "accounts/signals.py",
     '    "avatar_id",\n    "is_active",\n)',
     '    "avatar_id",\n)',
     [f"{T}::test_closing_or_reopening_an_account_regenerates_its_pages"]),
    ("init_site makes no avatar pool", "core/management/commands/init_site.py",
     "        collection = ensure_default_avatar_collection()\n",
     "        collection = ensure_default_cover_collection()\n",
     [f"{T}::test_init_site_makes_the_pool"]),
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
