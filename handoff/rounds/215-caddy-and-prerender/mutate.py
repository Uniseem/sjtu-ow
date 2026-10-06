"""Round 215 mutation check: every guard this round adds must turn red when
broken. Baseline first (083's lesson): if the baseline is red, stop.

Run: uv run python handoff/rounds/215-caddy-and-prerender/mutate.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# (name, file, old, new, tests that must go red)
MUTATIONS = [
    (
        "C4: 字体原文件又交给 file_server",
        "deploy/Caddyfile",
        "\thandle /media/fonts/* {\n\t\trespond 404\n\t}\n",
        "",
        ["core/tests/test_latency.py::test_uploaded_font_originals_are_not_served"],
    ),
    (
        "C4: 分片的正则放宽，original/ 下的 woff2 也算公开",
        "deploy/Caddyfile",
        "|[0-9]+/[^/]+\\.woff2)$",
        "|[0-9]+/.+\\.woff2)$",
        ["core/tests/test_latency.py::test_uploaded_font_originals_are_not_served"],
    ),
    (
        "C6: HSTS 值和 Django 不一样（少了 preload）",
        "deploy/Caddyfile",
        '"max-age=31536000; includeSubDomains; preload"',
        '"max-age=31536000; includeSubDomains"',
        [
            "core/tests/test_latency.py::test_what_caddy_serves_itself_carries_django_s_hsts"
        ],
    ),
    (
        "C6: 预渲染页不带 HSTS",
        "deploy/Caddyfile",
        "(page_security) {\n\timport transport_security\n",
        "(page_security) {\n",
        [
            "core/tests/test_latency.py::test_what_caddy_serves_itself_carries_django_s_hsts"
        ],
    ),
    (
        "C6: 不带哈希的静态文件不带 HSTS",
        "deploy/Caddyfile",
        "\thandle /static/* {\n\t\troot * /srv\n\t\timport transport_security\n",
        "\thandle /static/* {\n\t\troot * /srv\n",
        [
            "core/tests/test_latency.py::test_what_caddy_serves_itself_carries_django_s_hsts"
        ],
    ),
    (
        "C6: Django 那条路也加 HSTS（叠两份）",
        "deploy/Caddyfile",
        "(django) {\n",
        "(django) {\n\timport transport_security\n",
        [
            "core/tests/test_latency.py::test_what_caddy_serves_itself_carries_django_s_hsts"
        ],
    ),
    (
        "C5: 下线又排给 worker",
        "core/prerender.py",
        "    transaction.on_commit(lambda: _remove_now(path))\n",
        "    from core.tasks import remove_prerendered\n\n"
        "    transaction.on_commit(lambda: remove_prerendered.enqueue(path))\n",
        [
            "core/tests/test_prerender.py::test_unpublishing_deletes_the_file_without_waiting_for_the_worker"
        ],
    ),
    (
        "C5: 删除失败不标记",
        "core/prerender.py",
        '                "status": PrerenderedPage.Status.FAILED,\n',
        '                "status": PrerenderedPage.Status.READY,\n',
        [
            "core/tests/test_prerender.py::test_a_failed_removal_is_flagged_and_handed_to_the_worker"
        ],
    ),
    (
        "C5: 删除失败不交给 worker",
        "core/prerender.py",
        "        remove_prerendered.enqueue(path)\n",
        "        pass\n",
        [
            "core/tests/test_prerender.py::test_a_failed_removal_is_flagged_and_handed_to_the_worker"
        ],
    ),
    (
        "C9: 对外照旧给细节",
        "core/views.py",
        "    if not _sees_health_details(request):\n",
        "    if False:\n",
        [
            "core/tests/test_pages.py::test_the_public_sees_which_check_failed_but_no_details",
            "core/tests/test_pages.py::test_back_office_staff_who_are_not_superusers_see_no_details",
        ],
    ),
    (
        "C9: 能进后台的都看细节",
        "core/views.py",
        "        return request.user.is_superuser\n",
        "        return request.user.is_staff\n",
        [
            "core/tests/test_pages.py::test_back_office_staff_who_are_not_superusers_see_no_details"
        ],
    ),
    (
        "C9: 超管也看不到细节",
        "core/views.py",
        "        return request.user.is_superuser\n",
        "        return False\n",
        ["core/tests/test_pages.py::test_a_superuser_sees_the_details"],
    ),
    (
        "F1: 网络错误时不去骨架",
        "static/js/state.js",
        ".then(done, done);",
        ".then(done);",
        [
            "core/tests/test_prerender.py::test_the_skeleton_goes_even_when_the_state_request_fails"
        ],
    ),
    (
        "F1: 没有 8 秒兜底",
        "static/js/state.js",
        "      window.setTimeout(done, GIVE_UP_MS);\n",
        "",
        [
            "core/tests/test_prerender.py::test_the_skeleton_goes_even_when_the_state_request_fails"
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
        backup = path.with_suffix(path.suffix + ".bak215")
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
