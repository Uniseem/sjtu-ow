# ruff: noqa: E501
"""Round 216 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run: uv run python handoff/rounds/216-review-lows/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# (name, file, old, new, tests that must go red)
MUTATIONS = [
    (
        "A4 EXIF 放回 try 外",
        "accounts/images.py",
        "        picture = ImageOps.exif_transpose(picture)\n    except AvatarError:",
        "    except AvatarError:",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "A5 改邮箱不再要密码",
        "sjtu_ow/settings/base.py",
        "ACCOUNT_REAUTHENTICATION_REQUIRED = True",
        "ACCOUNT_REAUTHENTICATION_REQUIRED = False",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "A6 注销不限次",
        "accounts/views.py",
        '    if request.method == "POST" and over_limit(\n        f"me-delete:',
        '    if False and over_limit(\n        f"me-delete:',
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "A7 部分保存不带段位时间",
        "accounts/models.py",
        '            kwargs["update_fields"] = {*update_fields, "ranks_updated_at"}',
        "            pass",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "A10 限流不在事务里",
        "core/ratelimit.py",
        "    with transaction.atomic():\n        try:",
        "    if True:\n        try:",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "C7 密钥校验漏 AI 密钥",
        "core/management/commands/restore.py",
        '    ("core_sitesettings", "moderation_api_key"),\n',
        "",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "C8 共享网段放行",
        "core/net.py",
        "        not address.is_global\n        or ",
        "        ",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "C8 连接不固定地址",
        "core/fonts/download.py",
        "_opener = urllib.request.build_opener(_SafeRedirectHandler, _PinnedHTTPSHandler)",
        "_opener = urllib.request.build_opener(_SafeRedirectHandler)",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "C10 镜像回到 root",
        "Dockerfile",
        "USER app\n",
        "",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "C10 backups 进镜像",
        ".dockerignore",
        "backups\n",
        "",
        ["accounts/tests/test_216_account_and_core.py"],
    ),
    (
        "C10 不核对 sha256",
        "deploy/fetch_tailwind_cli.py",
        "    if got != expected:",
        "    if False:",
        ["core/tests/test_tailwind_cli_fetch.py"],
    ),
    (
        "T3 编号不过 as_id",
        "tournaments/registration.py",
        "pk=as_id(chosen_id), user=user",
        "pk=chosen_id, user=user",
        ["teams/tests/test_216_team_and_registration.py"],
    ),
    (
        "T4 指定队长不原子",
        "teams/services.py",
        "@transaction.atomic\ndef assign_captain(",
        "def assign_captain(",
        ["teams/tests/test_216_team_and_registration.py"],
    ),
    (
        "T5 申请入队撞约束不接",
        "teams/services.py",
        '        raise TeamError("你对这支战队还有一条待审批的申请。") from exc',
        "        raise",
        ["teams/tests/test_216_team_and_registration.py"],
    ),
    (
        "T6 建队按尝试计数",
        "teams/views.py",
        "        if not form.is_valid():\n            pass\n        elif over_limit(",
        "        if over_limit(",
        ["teams/tests/test_216_team_and_registration.py"],
    ),
    (
        "T8 临时队伍不判空",
        "tournaments/registration.py",
        '                battletag=account.battletag if account else "",\n                is_sjtu=user.is_sjtu,\n                rank_tank=account.rank_tank if account else None,\n                rank_damage=account.rank_damage if account else None,\n                rank_support=account.rank_support if account else None,\n                is_captain=False,',
        "                battletag=account.battletag,\n                is_sjtu=user.is_sjtu,\n                rank_tank=account.rank_tank,\n                rank_damage=account.rank_damage,\n                rank_support=account.rank_support,\n                is_captain=False,",
        ["teams/tests/test_216_team_and_registration.py"],
    ),
    (
        "移除队长",
        "teams/services.py",
        "    if membership.is_captain:\n        # A superuser could remove the captain",
        "    if False:\n        # A superuser could remove the captain",
        ["teams/tests/test_216_team_and_registration.py"],
    ),
    (
        "T7 取消后照样审核",
        "tournaments/registration.py",
        "    if tournament.status == TournamentStatus.CANCELLED:\n        raise",
        "    if False:\n        raise",
        ["tournaments/tests/test_216_closed_tournaments.py"],
    ),
    (
        "T7 结束后照样审核",
        "tournaments/registration.py",
        "    if tournament.status == TournamentStatus.FINISHED:\n        raise",
        "    if False:\n        raise",
        ["tournaments/tests/test_216_closed_tournaments.py"],
    ),
    (
        "S4 游戏 ID 删了不判空",
        "scrims/teaming.py",
        '                    signup.game_account.battletag if signup.game_account else ""',
        "                    signup.game_account.battletag",
        ["scrims/tests/test_216_split_edges.py"],
    ),
    (
        "S5 没段位存别的分",
        "scrims/split_admin.py",
        "            rating = signup.rating_for(role) or 0",
        "            rating = signup.rating_for(role) or signup.best_rating",
        ["scrims/tests/test_216_split_edges.py"],
    ),
    (
        "S6 不提示 0 分",
        "scrims/split_admin.py",
        "                if unrated:\n",
        "                if False:\n",
        ["scrims/tests/test_216_split_edges.py"],
    ),
    (
        "S8 分队页不排队",
        "scrims/templates/scrims/admin/split.html",
        ' data-autosave-queue="split"',
        "",
        ["scrims/tests/test_216_split_edges.py"],
    ),
    (
        "S10 每个草稿多查一次",
        "scrims/services.py",
        "    if counted is not None:\n        return counted == 0\n",
        "",
        ["scrims/tests/test_216_split_edges.py"],
    ),
    (
        "B4 编号不过关",
        "backoffice/forms.py",
        "        if value not in self.empty_values and as_id(value) is None:",
        "        if False:",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "B7 非法路径照样排队",
        "core/prerender_admin.py",
        "        if not _usable(path):",
        "        if False:",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "B8 不记新建",
        "core/middleware.py",
        "            if made and made != request.path:",
        "            if False:",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "B8 不清空草稿",
        "core/management/commands/cleanup_old_data.py",
        '        counts[f"空着的草稿（{EMPTY_DRAFT_DAYS} 天没动）"] = self.empty_drafts(\n            dry_run, now\n        )\n',
        "",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "B9 撞网址又 500",
        "backoffice/forms.py",
        "                key = name if name in self.fields else NON_FIELD_ERRORS",
        "                key = name",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "B10 发布按钮无条件",
        "backoffice/views/articles.py",
        '        "can_publish": form.parent is not None\n        and form.parent.permissions_for_user(user).can_publish_subpage(),',
        '        "can_publish": True,',
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "F5 对话框认登录页",
        "static/js/backoffice.js",
        "        if (!response.ok || response.redirected) {",
        "        if (false) {",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "F6 回跳不要 https",
        "moderation/avatar_admin.py",
        "        back, allowed_hosts={request.get_host()}, require_https=request.is_secure()",
        "        back, allowed_hosts={request.get_host()}",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "F7 选图按钮没名字",
        "backoffice/templates/backoffice/widgets/image_picker.html",
        '{% if widget.label %} aria-label="选择{{ widget.label }}"{% endif %}',
        "",
        ["backoffice/tests/test_216_backoffice_edges.py"],
    ),
    (
        "D5 结论落到新文字",
        "moderation/services.py",
        "    written = ModerationItem.objects.filter(\n        pk=item.pk, text_hash=item.text_hash\n    ).update(**{",
        "    written = ModerationItem.objects.filter(\n        pk=item.pk\n    ).update(**{",
        ["moderation/tests/test_216_patrol_edges.py"],
    ),
    (
        "D5 失败记到新文字",
        "moderation/services.py",
        "        written = ModerationItem.objects.filter(\n            pk=item.pk, text_hash=item.text_hash\n        ).update(attempts=",
        "        written = ModerationItem.objects.filter(\n            pk=item.pk\n        ).update(attempts=",
        ["moderation/tests/test_216_patrol_edges.py"],
    ),
    (
        "D6 外站地址做成链接",
        "core/letters.py",
        '    if url != site and not url.startswith(site + "/"):\n        return url\n',
        "",
        ["moderation/tests/test_216_patrol_edges.py"],
    ),
    (
        "D7 不禁 stream",
        "moderation/services.py",
        '    "stream",\n    "model",\n)',
        '    "model",\n)',
        ["moderation/tests/test_216_patrol_edges.py"],
    ),
    (
        "D8 截断流逃出",
        "moderation/providers.py",
        "                http.client.HTTPException,\n",
        "",
        ["moderation/tests/test_216_patrol_edges.py"],
    ),
    (
        "A2 内容编辑能搜邮箱",
        "backoffice/views/members.py",
        '            group, query, by_email=sees_emails(request.user)\n        ),\n        "sees_emails"',
        '            group, query, by_email=True\n        ),\n        "sees_emails"',
        ["core/tests/test_216_decisions.py"],
    ),
    (
        "A2 标签给所有人看邮箱",
        "backoffice/forms.py",
        '    if sees_emails(viewer):\n        return f"{user.nickname}（{user.email}）"',
        '    if True:\n        return f"{user.nickname}（{user.email}）"',
        ["core/tests/test_216_decisions.py"],
    ),
    (
        "A12 停用照样显示头像",
        "templates/components/avatar.html",
        "{% if person.avatar_id and person.is_active %}",
        "{% if person.avatar_id %}",
        ["core/tests/test_216_decisions.py"],
    ),
    (
        "B11 群发不冷却",
        "core/services.py",
        "        if recent is not None:\n            return (",
        "        if False:\n            return (",
        ["core/tests/test_216_decisions.py"],
    ),
    (
        "日历换地址不失效",
        "core/calendar_feed.py",
        "pk=pk, is_active=True, calendar_version=version",
        "pk=pk, is_active=True",
        ["core/tests/test_216_decisions.py"],
    ),
]

# `mutate.py 移除队长 F5` runs only the mutations whose names contain one of
# the words (to re-check a fixed test without the whole list).
if len(sys.argv) > 1:
    MUTATIONS = [m for m in MUTATIONS if any(word in m[0] for word in sys.argv[1:])]

BASELINE = sorted({test for _m in MUTATIONS for test in _m[4]})


def run(tests):
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", *tests],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-12:])
        print(f"    ---- 输出尾巴 ----\n{tail}")
    return result.returncode


def main():
    print("基线：", flush=True)
    if run(BASELINE) != 0:
        print("基线就是红的，停下（083 的教训）。")
        return 1
    print("基线全绿，开始变异。\n", flush=True)
    bad = 0
    for name, filename, old, new, tests in MUTATIONS:
        path = ROOT / filename
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"!! {name}：找不到要改坏的代码（{filename}），跳过")
            bad += 1
            continue
        backup = path.with_suffix(path.suffix + ".bak216")
        shutil.copy2(path, backup)
        try:
            path.write_text(original.replace(old, new, 1), encoding="utf-8")
            code = run(tests)
            if code == 0:
                print(f"!! {name}：改坏后测试仍然全绿 —— 没抓到")
                bad += 1
            else:
                print(f"ok {name}：改坏后红了（{len(tests)} 条）")
        finally:
            shutil.move(backup, path)
            # 027 的坑：mtime/size 没变时清掉缓存再跑
            for cache in path.parent.glob(f"__pycache__/{path.stem}.*"):
                cache.unlink()
    print()
    if run(BASELINE) != 0:
        print("!! 改回之后基线红了，有文件没恢复好")
        return 1
    print("改回后基线全绿。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
