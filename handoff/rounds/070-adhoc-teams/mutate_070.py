# -*- coding: utf-8 -*-
"""Round 070 mutation checks: break each guard, expect the new tests to go red.

The first seven ran in an earlier invocation (all caught, output in the
report); START skips them so the rerun only covers the rest.
"""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}
T = ["tournaments/tests/test_adhoc_teams.py"]
REG = "tournaments/registration.py"
START = int(os.environ.get("MUTATE_START", "0"))

MUTATIONS = [
    ("超员不再拒绝", REG,
     "            if len(ids) > tournament.roster_max:\n", "            if False:\n", T),
    ("队名为空也收", REG,
     '    if not name:\n        return ["队伍要有名字"]\n', '    if False:\n        return ["队伍要有名字"]\n', T),
    ("队名超长也收", REG,
     "    if len(name) > TEAM_NAME_MAX:\n", "    if False:\n", T),
    ("队名重复也收", REG,
     '    if taken.exists():\n        return [f"队名「{name}」在这项赛事里已经有了"]\n',
     '    if False:\n        return [f"队名「{name}」在这项赛事里已经有了"]\n', T),
    ("同一版面里同名不查", REG,
     "    if len(names) != len(set(names)):\n", "    if False:\n", T),
    ("一人两队不查", REG,
     "            if signup_id in seen:\n", "            if False:\n", T),
    ("别的赛事的散人也收", REG,
     "            if entry is None:\n                problems.append(\"名单里有不属于这项赛事的人，请刷新页面再试\")\n                continue\n",
     "            if entry is None:\n                continue\n", T),
    ("编队时不再跑队员校验", REG,
     "            member_issues.extend(\n                member_problems(tournament=tournament, user=entry.user)\n            )\n", "", T),
    ("编队时不再查名单冲突", REG,
     "            if conflict:\n                member_issues.append(conflict)\n", "            if False:\n                member_issues.append(conflict)\n", T),
    ("解散不再限于临时队伍", REG,
     '    if registration.team_id is not None:\n        raise RegistrationError("只有临时队伍能解散，战队报名请驳回")\n',
     '    if False:\n        raise RegistrationError("只有临时队伍能解散，战队报名请驳回")\n', T),
    ("退出不再限于临时队伍", REG,
     '    if registration.team_id is not None:\n        raise RegistrationError("战队报名由队长撤回，不能单独退出")\n',
     '    if False:\n        raise RegistrationError("战队报名由队长撤回，不能单独退出")\n', T),
    ("不在名单里也能退出", REG,
     '    if row is None:\n        raise RegistrationError("你不在这支队伍的名单里")\n',
     '    if row is None:\n        row = registration.members.first()\n', T),
    ("截止后还能退出", REG,
     "    if enforce_deadline and not captain_can_change(registration):\n", "    if False:\n", T),
    ("最后一人退出不再解散", REG,
     "    dissolved = not registration.members.exists()\n", "    dissolved = False\n", T),
    ("临时队伍也能撤回", REG,
     '    if registration.team_id is None:\n        raise RegistrationError("临时队伍由管理员解散，队员可以退出队伍")\n',
     '    if False:\n        raise RegistrationError("临时队伍由管理员解散，队员可以退出队伍")\n', T),
    ("审核页对临时队伍也显示按钮", "tournaments/review_admin.py",
     '    if registration.team_id is None:\n        return {"approve": False, "reject": False, "revoke": False}\n',
     '    if False:\n        return {"approve": False, "reject": False, "revoke": False}\n', T),
    ("取消赛事不再通知临时队伍成员", "tournaments/services.py",
     "        if registration.team_id is None:\n            users.extend(\n", "        if False:\n            users.extend(\n", T),
    ("注销时不再退出临时队伍", "accounts/services.py",
     "        _leave_adhoc_teams(user)  # design 8.8.2: free the places first\n", "", T),
]


def clear_caches():
    for app in ("tournaments", "accounts"):
        for root, dirs, _files in os.walk(R + app):
            for d in list(dirs):
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d), ignore_errors=True)


caught = 0
for label, rel, old, new, target in MUTATIONS[START:]:
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
            cwd=R, env=ENV, capture_output=True, text=True, timeout=900,
        )
    finally:
        io.open(path, "wb").write(original)
        clear_caches()
    summary = [line for line in run.stdout.splitlines() if "passed" in line or "failed" in line or "error" in line]
    hit = run.returncode != 0
    caught += hit
    print(("✓ 被抓到" if hit else "✗ 幸存"), label, "|", summary[-1] if summary else run.stdout[-160:])
print("---")
print(f"{caught}/{len(MUTATIONS) - START} mutations caught (from #{START + 1})")
