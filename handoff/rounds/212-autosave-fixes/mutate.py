"""Round 212 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run: uv run python handoff/rounds/212-autosave-fixes/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# (name, file, old, new, tests that must go red)
MUTATIONS = [
    (
        "T1/A3: autosave_together 组扩展（错误落在组内一个字段时整组不存）",
        "core/autosave.py",
        """    else:
        for group in groups:
            if bad & group:
                # A rule across fields reported on one field of the group
                # (212): saving another field of the group alone would break
                # the pair, so the whole group sits this save out too.
                bad |= group
""",
        "",
        [
            "core/tests/test_autosave.py::test_a_rule_on_one_field_holds_back_its_whole_group",
            "core/tests/test_autosave.py::test_a_contact_type_does_not_save_without_a_matching_value",
            "core/tests/test_autosave_events.py::test_changing_the_other_half_of_a_rule_saves_nothing_of_the_pair",
            "core/tests/test_autosave_events.py::test_a_copy_with_the_window_backwards_is_no_500_and_keeps_the_times",
            "core/tests/test_autosave_events.py::test_the_roster_pair_also_saves_together_or_not_at_all",
        ],
    ),
    (
        "A1: ContactMethodForm 的同类型冲突检查",
        "accounts/forms.py",
        """            if clash:
                self.add_error("type", "每种联系方式只能填写一次。")
""",
        "",
        ["core/tests/test_autosave.py::test_a_contact_type_clash_is_an_error_not_a_500"],
    ),
    (
        "A1 连带：类型自身有错时不再给内容加「未知类型」",
        "accounts/models.py",
        """        if self.type not in ContactType.values:
            return
""",
        "",
        [
            "core/tests/test_client_ip.py::test_a_whole_form_error_shows_once",
            "core/tests/test_autosave.py::test_a_contact_type_clash_is_an_error_not_a_500",
        ],
    ),
    (
        "F2: 退避封顶（子串守卫）",
        "static/js/autosave.js",
        "var RETRY_MAX = 60000;",
        "",
        ["core/tests/test_autosave_js.py::test_retriable_failures_back_off_instead_of_hammering"],
    ),
    (
        "F2: 永久失败不再拦住离开（子串守卫）",
        "static/js/autosave.js",
        "return this.dirty || this.busy !== null || (this.failed && !this.gaveUp);",
        "return this.dirty || this.busy !== null || this.failed;",
        ["core/tests/test_autosave_js.py::test_a_permanent_failure_does_not_block_leaving_the_page"],
    ),
    (
        "F4: 保存后清空密钥框",
        "backoffice/views/settings.py",
        """        for name in saved:
            if name in SECRET_FIELDS:
                outcome.values[name] = ""
""",
        "",
        ["core/tests/test_autosave.py::test_a_saved_secret_is_emptied_in_the_response"],
    ),
    (
        "B6: 新建分类有错也建行",
        "backoffice/views/categories.py",
        """        category, saved = autosave.new_from_valid_fields(form, ArticleCategory())
        category.save()
""",
        """        category, saved = form.instance, autosave.save_valid_fields(form)
""",
        ["core/tests/test_autosave.py::test_a_new_category_is_created_even_when_the_first_change_is_wrong"],
    ),
    (
        "B6: 新建成员分组有错也建行",
        "backoffice/views/members.py",
        """        group, saved = autosave.new_from_valid_fields(form, MemberGroup())
        group.save()
""",
        """        group, saved = form.instance, autosave.save_valid_fields(form)
""",
        ["core/tests/test_autosave.py::test_a_new_member_group_is_created_even_when_the_first_change_is_wrong"],
    ),
    (
        "D3: 修订号不一致就不存",
        "content/drafts.py",
        "    return page.latest_revision_id != base",
        "    return False",
        [
            "content/tests/test_drafts.py::test_two_editors_do_not_overwrite_each_other",
            "content/tests/test_drafts.py::test_a_stale_whole_form_submit_is_refused",
            "content/tests/test_drafts.py::test_plain_pages_and_pins_refuse_a_stale_base",
        ],
    ),
    (
        "D2: 删分类计数算上修订",
        "content/services.py",
        """    for object_id, category_id in rows:
        if category_id is not None:
            by_page[int(object_id)] = category_id
""",
        "",
        [
            "content/tests/test_category_delete.py::test_a_category_used_only_by_a_draft_still_cannot_go",
            "content/tests/test_category_delete.py::test_a_scheduled_revision_also_counts",
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
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-15:])
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
        backup = path.with_suffix(path.suffix + ".bak212")
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
