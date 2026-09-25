# -*- coding: utf-8 -*-
"""Round 069 mutation checks: break each guard, expect the new tests to go red."""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}
T = ["tournaments/tests/test_individual_signup.py"]

MUTATIONS = [
    ("开关不再检查", "tournaments/registration.py",
     "    if not tournament.allow_individual_signup:\n", "    if False:\n", T),
    ("时间窗不再检查", "tournaments/registration.py",
     "    if not tournament.registration_open(now):\n        problems.append(\"当前不在报名时间内\")\n",
     "    if False:\n        problems.append(\"当前不在报名时间内\")\n", T),
    ("队员校验（权限、资料、仅限交大）不再复用", "tournaments/registration.py",
     "    problems.extend(member_problems(tournament=tournament, user=user))\n    conflict = existing_roster_conflict(tournament=tournament, user=user)\n",
     "    conflict = existing_roster_conflict(tournament=tournament, user=user)\n", T),
    ("名单冲突不再检查", "tournaments/registration.py",
     "    conflict = existing_roster_conflict(tournament=tournament, user=user)\n    if conflict:\n        problems.append(conflict)\n    return problems\n",
     "    return problems\n", T),
    ("别人的游戏 ID 也收", "tournaments/registration.py",
     "        return user.game_accounts.filter(pk=int(game_account_id)).first()\n",
     "        from accounts.models import GameAccount\n\n        return GameAccount.objects.filter(pk=int(game_account_id)).first()\n", T),
    ("零个位置也收", "tournaments/registration.py",
     "    if not roles:\n        problems.append(\"至少要勾选一个能打的位置\")\n",
     "    if False:\n        problems.append(\"至少要勾选一个能打的位置\")\n", T),
    ("已编入的还能改", "tournaments/registration.py",
     "    if signup is not None and signup.is_placed:\n        raise RegistrationError(\"你已经被编入队伍，要改动请联系赛事管理员\")\n",
     "    if False:\n        raise RegistrationError(\"你已经被编入队伍，要改动请联系赛事管理员\")\n", T),
    ("截止后还能取消", "tournaments/registration.py",
     "    if now > tournament.registration_closes_at:\n        raise RegistrationError(\"报名已截止，不能再取消\")\n",
     "    if False:\n        raise RegistrationError(\"报名已截止，不能再取消\")\n", T),
    ("报名不再刷新页面", "tournaments/registration.py",
     "        raise RegistrationError(\"你已经报名过这项赛事了\") from exc\n    _refresh_tournament_page(tournament)\n",
     "        raise RegistrationError(\"你已经报名过这项赛事了\") from exc\n", T),
    ("未公开的赛事也刷新", "tournaments/registration.py",
     "    if not tournament.is_listed:\n        return\n    from core import prerender\n",
     "    from core import prerender\n", T),
    ("删除游戏 ID 不再看个人报名", "accounts/services.py",
     "    if entry is not None:\n        return (\n            f\"这个游戏 ID 正用于赛事「{entry.tournament.title}」的个人报名，\"\n",
     "    if False:\n        return (\n            f\"这个游戏 ID 正用于赛事「{entry.tournament.title}」的个人报名，\"\n", T),
    ("改昵称不再刷新散人名单", "accounts/services.py",
     "        if entry.tournament.is_listed:  # the pool prints live nicknames (8.8.1)\n",
     "        if False:  # the pool prints live nicknames (8.8.1)\n", T),
    ("槽位对散人不再给入口", "tournaments/slots.py",
     "    if signed_in and not captain_teams and tournament.allow_individual_signup:\n",
     "    if False:\n", T),
]


def clear_caches():
    for app in ("tournaments", "accounts"):
        for root, dirs, _files in os.walk(R + app):
            for d in list(dirs):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)


caught = 0
for label, rel, old, new, target in MUTATIONS:
    path = R + rel
    original = io.open(path, "rb").read()
    text = original.decode("utf-8")
    norm = text.replace("\r\n", "\n")
    assert norm.count(old) == 1, (label, norm.count(old))
    mutated = norm.replace(old, new)
    if "\r\n" in text:
        mutated = mutated.replace("\n", "\r\n")
    io.open(path, "wb").write(mutated.encode("utf-8"))
    clear_caches()
    try:
        run = subprocess.run(
            [sys.executable, "-m", "uv", "run", "pytest", "-q", "--no-header",
             "-p", "no:cacheprovider", *target],
            cwd=R, env=ENV, capture_output=True, text=True, timeout=600,
        )
    finally:
        io.open(path, "wb").write(original)
        clear_caches()
    summary = [line for line in run.stdout.splitlines() if "passed" in line or "failed" in line or "error" in line]
    hit = run.returncode != 0
    caught += hit
    print(("✓ 被抓到" if hit else "✗ 幸存"), label, "|", summary[-1] if summary else run.stdout[-160:])
print("---")
print(f"{caught}/{len(MUTATIONS)} mutations caught")
