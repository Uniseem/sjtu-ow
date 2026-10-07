# ruff: noqa: E501
"""Round 218 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run on the test machine:
  bash scripts/remote-check.sh run uv run python handoff/rounds/218-pre-rewrite-fixes/mutate.py
Only some mutations: pass words from their names as arguments.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

DOOR = "accounts/tests/test_single_login_door.py"
GATE = "comments/tests/test_comment_page_gate.py"
CRON = "core/tests/test_cron_schedule.py"

# (name, file, old, new, tests that must go red, replace all occurrences?)
MUTATIONS = [
    (
        "04-1 拿掉 /wagtail/login/ 的跳转",
        "sjtu_ow/urls.py",
        '    path("wagtail/login/", login_door),\n',
        "",
        [DOOR],
        False,
    ),
    (
        "04-1 拿掉 /_util/login/ 的跳转",
        "sjtu_ow/urls.py",
        '    path("_util/login/", login_door),\n',
        "",
        [DOOR],
        False,
    ),
    (
        "04-1 next 不查是不是本站",
        "accounts/views.py",
        "    if after and url_has_allowed_host_and_scheme(\n        after, allowed_hosts={request.get_host()}, require_https=request.is_secure()\n    ):",
        "    if after:",
        [DOOR],
        False,
    ),
    (
        "04-1 受限页面又跳回 Wagtail 登录页",
        "sjtu_ow/settings/base.py",
        'WAGTAIL_FRONTEND_LOGIN_URL = "account_login"\n',
        "",
        [DOOR],
        False,
    ),
    (
        "03-1 总闸：不查文章",
        "comments/views.py",
        "    return comment, _page_or_404(comment.page_id)",
        "    return comment, comment.page",
        [GATE],
        False,
    ),
    (
        "03-1 点赞超限分支不查文章",
        "comments/views.py",
        '        _, page = _comment_and_page(pk)\n        return _section_response(request, page, ["点赞太频繁了，稍后再试"])',
        '        page = get_object_or_404(Comment.objects.select_related("page"), pk=pk).page\n        return _section_response(request, page, ["点赞太频繁了，稍后再试"])',
        [GATE],
        False,
    ),
    (
        "03-1 编辑超限分支不查文章",
        "comments/views.py",
        '        _, page = _comment_and_page(pk)\n        return _section_response(request, page, ["编辑太频繁了，稍后再试"])',
        '        page = get_object_or_404(Comment.objects.select_related("page"), pk=pk).page\n        return _section_response(request, page, ["编辑太频繁了，稍后再试"])',
        [GATE],
        False,
    ),
    (
        "03-1 版主接口不查文章",
        "comments/views.py",
        "    comment, page = _comment_and_page(pk)\n    try:\n        action(comment=comment, actor=request.user)",
        '    comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)\n    page = comment.page\n    try:\n        action(comment=comment, actor=request.user)',
        [GATE],
        False,
    ),
    (
        "03-1 点赞编辑删除置顶接口不查文章",
        "comments/views.py",
        "    comment, page = _comment_and_page(pk)\n    try:\n        action(comment=comment, **kwargs)",
        '    comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)\n    page = comment.page\n    try:\n        action(comment=comment, **kwargs)',
        [GATE],
        False,
    ),
    (
        "03-1 回复接口不查文章",
        "comments/views.py",
        "    parent, page = _comment_and_page(pk)\n    return _post(request, page, parent=parent)",
        '    parent = get_object_or_404(Comment.objects.select_related("page"), pk=pk)\n    page = parent.page\n    return _post(request, page, parent=parent)',
        [GATE],
        False,
    ),
    (
        "09-9 不看小时",
        "deploy/at-shanghai.sh",
        '[ "$now_hour" -eq "$hour" ] || exit 0',
        "true",
        [CRON],
        False,
    ),
    (
        "09-9 不看星期",
        "deploy/at-shanghai.sh",
        '[ "$now_weekday" != "$weekday" ]',
        "false",
        [CRON],
        False,
    ),
    (
        "09-9 按柏林时间算",
        "deploy/at-shanghai.sh",
        "TZ=CST-8",
        "TZ=Europe/Berlin",
        [CRON],
        True,
    ),
    (
        "09-9 不保留命令的退出码",
        "deploy/at-shanghai.sh",
        'exec "$@"',
        '"$@" || exit 0',
        [CRON],
        False,
    ),
    (
        "09-9 crontab 的每周任务丢了星期",
        "deploy/crontab.example",
        "$AT 4 0 -- ",
        "$AT 4 -- ",
        [CRON],
        False,
    ),
    (
        "09-9 crontab 备份时间错一小时",
        "deploy/crontab.example",
        "$AT 3 -- ",
        "$AT 2 -- ",
        [CRON],
        False,
    ),
    (
        "09-9 crontab 又写回 CRON_TZ",
        "deploy/crontab.example",
        "AT=sh /srv/sjtu-ow/deploy/at-shanghai.sh\n",
        "AT=sh /srv/sjtu-ow/deploy/at-shanghai.sh\nCRON_TZ=Asia/Shanghai\n",
        [CRON],
        False,
    ),
]

if len(sys.argv) > 1:
    MUTATIONS = [m for m in MUTATIONS if any(word in m[0] for word in sys.argv[1:])]

BASELINE = sorted({test for m in MUTATIONS for test in m[4]})


def run(tests):
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "-p", "no:cacheprovider", *tests],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-6:])
        print(f"    ---- 输出尾巴 ----\n{tail}")
    return result.returncode


def main():
    print("基线：", flush=True)
    if run(BASELINE) != 0:
        print("基线就是红的，停下（083 的教训）。")
        return 1
    print("基线全绿，开始变异。\n", flush=True)
    bad = 0
    for name, filename, old, new, tests, everywhere in MUTATIONS:
        path = ROOT / filename
        original = path.read_text(encoding="utf-8")
        found = original.count(old)
        if found == 0 or (found > 1 and not everywhere):
            # 216 的坑：改坏的那行出现不止一次时，replace(.., 1) 会改到别处
            print(f"!! {name}：要改坏的代码在 {filename} 里出现 {found} 次，跳过")
            bad += 1
            continue
        backup = path.with_suffix(path.suffix + ".bak218")
        shutil.copy2(path, backup)
        try:
            path.write_text(original.replace(old, new), encoding="utf-8")
            code = run(tests)
            if code == 0:
                print(f"!! {name}：改坏后测试仍然全绿 —— 没抓到", flush=True)
                bad += 1
            else:
                print(f"ok {name}：改坏后红了", flush=True)
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
