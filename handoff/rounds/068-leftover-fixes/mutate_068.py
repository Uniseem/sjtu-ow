# -*- coding: utf-8 -*-
"""Round 068 mutation checks: undo each fix, expect its new test to go red."""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}

MUTATIONS = [
    (
        "1 内容编辑的文章分类权限没给",
        "content/services.py",
        "            codename__in=CATEGORY_PERMISSIONS,\n",
        "            codename__in=(),\n",
        ["content/tests/test_category_permissions.py"],
    ),
    (
        "2 恢复命令不再检查对象存储密钥",
        "core/management/commands/restore.py",
        '    ("core_sitesettings", "backup_s3_secret_access_key"),\n',
        "",
        ["core/tests/test_ops_commands.py", "-k", "object_storage_secret"],
    ),
    (
        "3 导航里没有「我的内战」",
        "accounts/views.py",
        '    ("me_scrims", "我的内战", True),\n',
        "",
        ["accounts/tests/test_me_nav.py"],
    ),
    (
        "4 prod 又漏掉 PrerenderMissMiddleware",
        "sjtu_ow/settings/prod.py",
        '    "core.middleware.PrerenderMissMiddleware",\n',
        "",
        ["core/tests/test_security_guards.py", "-k", "production_middleware"],
    ),
    (
        "5a 角色限定内战又把 0 当没填",
        "scrims/services.py",
        "            if getattr(account, RANK_FIELDS[role], None) is None\n",
        "            if not getattr(account, RANK_FIELDS[role], None)\n",
        ["scrims/tests/test_bronze_five.py"],
    ),
    (
        "5b best_rating 又丢掉 0",
        "scrims/models.py",
        "            if self.rating_for(role) is not None\n",
        "            if self.rating_for(role)\n",
        ["scrims/tests/test_bronze_five.py"],
    ),
    (
        "5c 分队页又把 0 换成最高段位",
        "scrims/split_admin.py",
        "        rating = signup.rating_for(role) if scrim.role_queue and role else None\n        if rating is None:\n",
        "        rating = signup.rating_for(role) if scrim.role_queue and role else None\n        if not rating:\n",
        ["scrims/tests/test_bronze_five.py"],
    ),
    (
        "5d 算法又丢掉 0",
        "scrims/teaming.py",
        "            if signup.rating_for(role) is not None\n",
        "            if signup.rating_for(role)\n",
        ["scrims/tests/test_bronze_five.py"],
    ),
    (
        "6 删掉的游戏 ID 不再显示占位",
        "scrims/models.py",
        "        if self.game_account_id is None:\n            return self.DELETED_ID_LABEL\n",
        "        if False:\n            return self.DELETED_ID_LABEL\n",
        ["scrims/tests/test_scrims.py", "-k", "really_be_deleted"],
    ),
]


def clear_caches():
    for app in ("scrims", "content", "core", "accounts", "sjtu_ow"):
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
