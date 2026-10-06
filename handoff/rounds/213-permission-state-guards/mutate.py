"""Round 213 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run: uv run python handoff/rounds/213-permission-state-guards/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# (name, file, old, new, tests that must go red)
MUTATIONS = [
    (
        "S1: edit 不查 can_comment",
        "comments/services.py",
        """    problems = can_comment(actor, comment.page)
    if problems:
        raise CommentError(problems)
""",
        "",
        [
            "comments/tests/test_comment_extras.py::test_a_silenced_author_cannot_edit_old_comments",
            "comments/tests/test_comment_extras.py::test_a_closed_article_takes_no_edits",
        ],
    ),
    (
        "S1: edit 视图不限流",
        "comments/views.py",
        """    if request.user.is_authenticated and _too_many(request.user):
        # Editing shares the posting limit (design 5.6, 213/S1).
        comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)
        return _section_response(request, comment.page, ["编辑太频繁了，稍后再试"])
""",
        "",
        [
            "comments/tests/test_comment_extras.py::test_editing_shares_the_posting_limit",
        ],
    ),
    (
        "S7: 作者能删被隐藏的评论",
        "comments/services.py",
        """    if comment.is_hidden:
        raise CommentError("这条评论已经不能删除了")
""",
        "",
        [
            "comments/tests/test_comment_extras.py::test_a_hidden_comment_cannot_be_deleted_by_its_author",
        ],
    ),
    (
        "S2: 改位置不清分队、不标记",
        "scrims/services.py",
        "    if changed_account or changed_roles:",
        "    if changed_account:",
        [
            "scrims/tests/test_scrims.py::test_changing_roles_clears_the_placement_and_marks_the_split_stale",
        ],
    ),
    (
        "S2: 缓冲区的人被清掉不标记",
        "scrims/services.py",
        "    was_placed = (signup.is_selected or bool(signup.team)) if not is_new else False",
        "    was_placed = bool(signup.team) if not is_new else False",
        [
            "scrims/tests/test_scrims.py::test_a_buffer_player_changing_ids_marks_the_split_stale",
        ],
    ),
    (
        "S3: publish 不拦已结束/已发布",
        "scrims/services.py",
        """    if scrim.status == ScrimStatus.FINISHED:
        raise ScrimError("已结束的内战不能再发布。")
    if scrim.status != ScrimStatus.DRAFT:
        raise ScrimError("这场内战已经发布了。")
""",
        "",
        [
            "scrims/tests/test_scrims.py::test_only_a_draft_can_be_published",
        ],
    ),
    (
        "S3: finish 不看状态",
        "scrims/services.py",
        """    if scrim.status != ScrimStatus.PUBLISHED:
        raise ScrimError("只有已发布的内战可以标记为已结束。")
""",
        "",
        [
            "scrims/tests/test_scrims.py::test_only_a_published_scrim_can_be_finished",
        ],
    ),
    (
        "T2: 转让队长不拦停用账号",
        "teams/services.py",
        """    if not new_captain.is_active:
        # Same guard as assign_captain (213, T2): a stopped account as
        # captain deadlocks the team (nobody can apply, a superuser must
        # step in).
        raise TeamError("这个账号已停用，不能当队长。")
""",
        "",
        [
            "teams/tests/test_teams.py::test_the_captaincy_cannot_go_to_a_stopped_account",
        ],
    ),
    (
        "T2: 管理页对停用成员仍显示「转让队长」",
        "teams/templates/teams/manage.html",
        "                      {% if membership.user.is_active %}",
        "                      {% if True %}",
        [
            "teams/tests/test_stopped_members.py::test_the_manage_page_offers_no_transfer_for_a_stopped_member",
        ],
    ),
    (
        "A8: 启用不看清没注销",
        "accounts/services.py",
        """    if is_deleted(user):
        raise AccountError("注销过的账号不能再启用。")
""",
        "",
        [
            "backoffice/tests/test_backoffice.py::test_a_deleted_account_cannot_be_reactivated",
        ],
    ),
    (
        "A8: 启用不清停用原因",
        "accounts/services.py",
        """    user.is_active = True
    user.deactivation_note = ""
    user.save(update_fields=["is_active", "deactivation_note"])""",
        """    user.is_active = True
    user.save(update_fields=["is_active"])""",
        [
            "backoffice/tests/test_backoffice.py::test_reactivation_goes_through_the_service_and_clears_the_note",
        ],
    ),
    (
        "A9: 注销不清 is_superuser",
        "accounts/services.py",
        "        user.is_superuser = False  # 213, A9: a deleted superuser must stay gone\n",
        "",
        [
            "accounts/tests/test_account_deletion.py::test_deleting_an_account_drops_the_superuser_flag",
        ],
    ),
    (
        "B3: 图片按张改守卫",
        "backoffice/views/images.py",
        """    if not image_policy().user_has_permission_for_instance(user, "change", image):
        raise PermissionDenied("你不能改这张图片。")
""",
        "",
        [
            "backoffice/tests/test_image_guards.py::test_a_submitter_cannot_edit_or_delete_anothers_image",
        ],
    ),
    (
        "B3: 图片按张删守卫",
        "backoffice/views/images.py",
        """    if not image_policy().user_has_permission_for_instance(
        request.user, "delete", image
    ):
        raise PermissionDenied("你不能删除这张图片。")
""",
        "",
        [
            "backoffice/tests/test_image_guards.py::test_a_submitter_cannot_edit_or_delete_anothers_image",
        ],
    ),
]

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
        backup = path.with_suffix(path.suffix + ".bak213")
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
