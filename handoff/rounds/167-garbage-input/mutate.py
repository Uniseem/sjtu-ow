"""Round 167: put each unchecked id back and check the sweep goes red
(AGENTS.md rule 7). Runs the tests first and stops if they are not green (083).

bash scripts/remote-check.sh run uv run python handoff/rounds/167-garbage-input/mutate.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1"}

T = "core/tests/test_garbage_input.py"


def t(name):
    return f"{T}::{name}"


POSTS = t("test_garbage_posts_never_crash")
QUERIES = t("test_garbage_queries_never_crash")
AS_ID = t("test_what_counts_as_an_id")

MUTATIONS = [
    ("anything is an id", "core/converters.py", "    if not re.fullmatch(IdConverter.regex, text):\n        return None\n", "", [AS_ID, POSTS]),
    ("member removed raw", "teams/views.py", 'def member_remove(request, pk):\n    team = get_object_or_404(Team, pk=pk)\n    member = get_object_or_404(User, pk=as_id(request.POST.get("user")))', 'def member_remove(request, pk):\n    team = get_object_or_404(Team, pk=pk)\n    member = get_object_or_404(User, pk=request.POST.get("user"))', [POSTS]),
    ("captain passed on raw", "teams/views.py", 'def captain_transfer(request, pk):\n    team = get_object_or_404(Team, pk=pk)\n    member = get_object_or_404(User, pk=as_id(request.POST.get("user")))', 'def captain_transfer(request, pk):\n    team = get_object_or_404(Team, pk=pk)\n    member = get_object_or_404(User, pk=request.POST.get("user"))', [POSTS]),
    ("scrim game ID raw", "scrims/services.py", "    account = user.game_accounts.filter(pk=as_id(account_id)).first()\n", "    account = user.game_accounts.filter(pk=account_id).first()\n", [POSTS]),
    ("players picked raw", "scrims/services.py", "    wanted = {as_id(value) for value in signup_ids} - {None}\n", "    wanted = {int(value) for value in signup_ids}\n", [POSTS]),
    ("new captain raw", "teams/wagtail_hooks.py", 'user = get_object_or_404(User, pk=as_id(request.POST.get("user")))', 'user = get_object_or_404(User, pk=request.POST.get("user"))', [POSTS]),
    ("feature rules filtered raw", "accounts/wagtail_hooks.py", '        user_id = as_id(self.request.GET.get("user"))\n        if user_id is not None:\n            qs = qs.filter(user_id=user_id)', '        user_id = self.request.GET.get("user")\n        if user_id:\n            qs = qs.filter(user_id=user_id)', [QUERIES]),
    ("team dissolved raw", "tournaments/teams_admin.py", '                    pk=as_id(request.POST.get("registration")),\n', '                    pk=request.POST.get("registration"),\n', [POSTS]),
    ("reviews filtered raw", "tournaments/review_admin.py", "    if as_id(tournament_id) is not None:\n        queryset = queryset.filter(tournament_id=as_id(tournament_id))\n", "    if tournament_id:\n        queryset = queryset.filter(tournament_id=tournament_id)\n", [QUERIES]),
    ("export logged raw", "tournaments/review_admin.py", "    asked = as_id(tournament_id)\n    if asked is not None and asked not in tournament_ids:\n        tournament_ids.append(asked)\n", "    if tournament_id and int(tournament_id) not in tournament_ids:\n        tournament_ids.append(int(tournament_id))\n", [QUERIES]),
    ("bulk approve raw", "tournaments/review_admin.py", "        registration = Registration.objects.filter(pk=as_id(pk)).first()\n", "        registration = Registration.objects.filter(pk=pk).first()\n", [POSTS]),
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
