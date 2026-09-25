# -*- coding: utf-8 -*-
"""Round 067 mutation checks: break each new guard, expect its test to go red.

Prints one line per mutation. Files are restored byte for byte afterwards and
tournaments' __pycache__ is cleared so Python cannot reuse a stale module
(AGENTS.md pitfall from round 027).
"""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}

MUTATIONS = [
    (
        "auto_approve 分支被拆掉",
        "tournaments/registration.py",
        "    if tournament.auto_approve:\n",
        "    if False and tournament.auto_approve:\n",
        ["tournaments/tests/test_state_table.py", "-k", "auto_approve"],
    ),
    (
        "系统通过不再跳过状态变化邮件",
        "tournaments/registration.py",
        "    if actor_type == ActorType.SYSTEM:\n        return\n",
        "    if actor_type == ActorType.SYSTEM:\n        pass\n",
        ["tournaments/tests/test_state_table.py", "-k", "one_mail"],
    ),
    (
        "后台表单不再检查是否已有报名",
        "tournaments/wagtail_hooks.py",
        "            and services.has_registrations(self.instance)\n",
        "            and False\n",
        ["tournaments/tests/test_state_table.py", "-k", "locked"],
    ),
    (
        "base_form_class 没接上",
        "tournaments/wagtail_hooks.py",
        "Tournament.base_form_class = TournamentAdminForm\n",
        "\n",
        ["tournaments/tests/test_state_table.py", "-k", "auto_approve_is_locked or nobody_has_registered"],
    ),
    (
        "approve 不再检查当前状态",
        "tournaments/registration.py",
        "    if registration.status != RegistrationStatus.PENDING:\n        raise RegistrationError(\"当前状态不能通过\")\n",
        "    if False:\n        raise RegistrationError(\"当前状态不能通过\")\n",
        ["tournaments/tests/test_state_table.py", "-k", "only_a_pending"],
    ),
    (
        "撤销通过按钮对任何状态都显示",
        "tournaments/review_admin.py",
        '        "revoke": status == RegistrationStatus.APPROVED,\n',
        '        "revoke": True,\n',
        ["tournaments/tests/test_review_admin.py", "-k", "follow_the_status"],
    ),
    (
        "rejected 状态的名单不再释放名额（原有守卫，回归）",
        "tournaments/registration.py",
        "    registration.members.update(is_active=to_status in ACTIVE_STATUSES)\n",
        "    registration.members.update(is_active=True)\n",
        ["tournaments/tests/test_state_table.py", "-k", "withdraws_from_every"],
    ),
]


def clear_caches():
    for root, dirs, _files in os.walk(R + "tournaments"):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)


results = []
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
    summary = [line for line in run.stdout.splitlines() if "passed" in line or "failed" in line]
    caught = run.returncode != 0
    results.append((label, caught, summary[-1] if summary else run.stdout[-200:]))
    print(("✓ 被抓到" if caught else "✗ 幸存"), label, "|", summary[-1] if summary else "?")

print("---")
print(f"{sum(1 for _, c, _ in results if c)}/{len(results)} mutations caught")
