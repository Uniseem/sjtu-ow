# ruff: noqa: E501
"""217 复核 16（测试质量）：手挑的变异点。

不在 212–216 各自 mutate.py 里、守卫普查（只认「if 条件: 拒绝」）也看不到的东西：
隐私过滤（查询里的 filter、模板里的条件）、CSP 落到哪些地址、预渲染的秘密标记、
限流配置、211 的缓存和保存时算好的字段、几处只在一条调用路径上测过的守卫。

每个变异在 git archive 出来的独立副本里改（借 210 mutate_guards.py 的 make_copy /
pytest），不碰仓库工作区。先跑相关应用的测试；仍然全绿的再跑全量，全量也绿才算
survived。基线先跑（083 的教训）。

    bash scripts/remote-check.sh run .venv/bin/python handoff/rounds/217-second-review/findings/16-mutate.py
"""

import importlib.util
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "mg", ROOT / "handoff/rounds/210-full-review/mutate_guards.py"
)
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)

# (编号, 名字, 文件, 原文, 改成, 先跑的测试)
MUTATIONS = [
    # --- 隐私过滤 ------------------------------------------------------------
    ("P1", "后台用户页：谁都看得到联系方式", "accounts/services.py",
     "        if can_see_contacts\n        else None,",
     "        if True\n        else None,",
     ["backoffice/tests", "accounts/tests"]),
    ("P2", "审核页 can_see_contacts 恒真", "tournaments/review_admin.py",
     '        getattr(user, "is_superuser", False)\n        or user.has_perm("accounts.view_contactmethod")',
     "        True",
     ["tournaments/tests", "scrims/tests"]),
    ("P3", "分队页不看 can_see_contacts", "scrims/split_admin.py",
     "    if not can_see_contacts(request.user):\n        return None",
     "    if False:\n        return None",
     ["scrims/tests"]),
    ("P4", "报名详情谁登录都能看", "tournaments/registration.py",
     "    return registration.members.filter(user=user).exists()",
     "    return True",
     ["tournaments/tests"]),
    ("P5", "成员页列出隐藏的分组", "members/services.py",
     "        MemberGroup.objects.filter(is_visible=True)",
     "        MemberGroup.objects.filter()",
     ["members/tests"]),
    ("P6", "个人页列出隐藏分组的头衔", "members/services.py",
     "            user=user, group__is_visible=True",
     "            user=user",
     ["members/tests"]),
    ("P7", "成员不要求邮箱已验证", "members/services.py",
     "User.objects.filter(is_active=True, emailaddress__verified=True)",
     "User.objects.filter(is_active=True)",
     ["members/tests", "search/tests"]),
    ("P8", "成员不要求账号启用", "members/services.py",
     "User.objects.filter(is_active=True, emailaddress__verified=True)",
     "User.objects.filter(emailaddress__verified=True)",
     ["members/tests", "search/tests"]),
    ("P9", "内战草稿能打开", "scrims/services.py",
     "    return Scrim.objects.filter(pk=pk).exclude(status=ScrimStatus.DRAFT).first()",
     "    return Scrim.objects.filter(pk=pk).first()",
     ["scrims/tests"]),
    ("P10", "搜索搜到未发布的文章", "search/services.py",
     "        ArticlePage.objects.live()\n        .public()",
     "        ArticlePage.objects.all()\n        .public()",
     ["search/tests"]),
    ("P11", "搜索搜到赛事草稿", "search/services.py",
     "        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED]",
     "        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED, TournamentStatus.DRAFT]",
     ["search/tests"]),
    ("P12", "搜索搜到内战草稿", "search/services.py",
     "        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED]",
     "        status__in=[ScrimStatus.PUBLISHED, ScrimStatus.FINISHED, ScrimStatus.DRAFT]",
     ["search/tests"]),
    ("P13", "搜索搜到解散的战队", "search/services.py",
     "    teams = Team.objects.filter(disbanded_at__isnull=True).order_by(",
     "    teams = Team.objects.filter().order_by(",
     ["search/tests"]),
    ("P14", "队内联系方式给能申请的人看", "teams/templates/teams/slots/join.html",
     "  {% elif can_apply %}\n",
     '  {% elif can_apply %}\n    {% include "teams/_member_contact.html" %}\n',
     ["teams/tests"]),
    ("P15", "隐藏的评论给所有人看正文（模板）", "comments/templates/comments/_item.html",
     "  {% elif comment.is_hidden and not can_moderate %}",
     "  {% elif False %}",
     ["comments/tests"]),
    ("P16", "隐藏的回复非管理员也查出来（查询）", "comments/services.py",
     "    if not moderator:\n        replies = replies.filter(is_hidden=False)",
     "    if False:\n        replies = replies.filter(is_hidden=False)",
     ["comments/tests"]),
    ("P17", "隐藏的回复给所有人看正文（模板）", "comments/templates/comments/_reply.html",
     "  {% elif reply.is_hidden and not can_moderate %}",
     "  {% elif False %}",
     ["comments/tests"]),
    # --- CSP / 预渲染 -------------------------------------------------------
    ("C1", "前台也拿后台的宽松 CSP", "core/middleware.py",
     "        if request.path.startswith((prefix, wagtail)):",
     "        if True:",
     ["core/tests", "backoffice/tests"]),
    ("C2", "非超管也能进 /wagtail/", "core/middleware.py",
     "            if user is not None and user.is_authenticated and not user.is_superuser:",
     "            if False:",
     ["core/tests", "backoffice/tests"]),
    ("C3", "预渲染不拦 csrfmiddlewaretoken", "core/prerender.py",
     '    "csrfmiddlewaretoken",\n', "",
     ["core/tests"]),
    ("C4", "预渲染不拦 sessionid", "core/prerender.py",
     '    "sessionid",\n', "",
     ["core/tests"]),
    ("C5", "healthz 查用户出错就 500", "core/views.py",
     "    try:\n        return request.user.is_superuser\n    except Exception:  # noqa: BLE001\n        return False",
     "    return request.user.is_superuser",
     ["core/tests"]),
    # --- 限流 ---------------------------------------------------------------
    ("R1", "注册不限流", "sjtu_ow/settings/base.py",
     '    "signup": "20/m/ip",', '    "signup": "20000/m/ip",',
     ["accounts/tests", "core/tests"]),
    ("R2", "找回密码不限流", "sjtu_ow/settings/base.py",
     '    "reset_password": "20/m/ip,5/m/key",', '    "reset_password": "20000/m/ip,5000/m/key",',
     ["accounts/tests", "core/tests"]),
    ("R3", "重发验证码不限流", "sjtu_ow/settings/base.py",
     '    "confirm_email": "1/10s/key",\n', "",
     ["accounts/tests", "core/tests"]),
    ("R4", "登录失败只按 IP 不按账号", "sjtu_ow/settings/base.py",
     '    "login_failed": "10/m/ip,5/300s/key",', '    "login_failed": "10/m/ip",',
     ["accounts/tests", "core/tests"]),
    ("R5", "头像上传不限次", "accounts/services.py",
     '    if over_limit(f"avatar-upload:{user.pk}", AVATAR_UPLOADS_PER_DAY, DAY_SECONDS):',
     "    if False:",
     ["accounts/tests"]),
    # --- 投稿者自动入组掩盖的权限 ------------------------------------------------
    ("G1", "赛事/内战管理员没有传图权限", "content/services.py",
     '    for name in (GROUP_TOURNAMENT, GROUP_SCRIM):\n        _grant_collection_perms(groups[name], collection, ("add_image", "choose_image"))\n',
     "",
     ["content/tests", "backoffice/tests", "tournaments/tests", "scrims/tests"]),
    ("G2", "认证作者没有栏目权限", "content/services.py",
     '        _grant_page_perms(\n            groups[GROUP_AUTHOR],\n            index,\n            ("add_page", "publish_page"),\n        )\n',
     "",
     ["content/tests", "backoffice/tests"]),
    # --- 211：失效短链缓存、保存时算好的字段 -----------------------------------------
    ("D1a", "查不到的短链不记缓存", "content/markdown.py",
     "            embeds.remember_failed_lookup(url)\n", "",
     ["content/tests"]),
    ("D1b", "查到后不清掉失败行的到期时间", "content/embeds.py",
     '            "cache_until": None,\n', "",
     ["content/tests"]),
    ("F10", "?bvid= 不过 BV 校验", "content/embeds.py",
     "    if bvid and not BV_RE.fullmatch(bvid):\n        bvid = None\n", "",
     ["content/tests"]),
    ("D10a", "只存正文时不重算字数", "content/models.py",
     'if update_fields is None or "body" in update_fields:',
     "if update_fields is None:",
     ["content/tests", "search/tests", "backoffice/tests"]),
    ("D10b", "只存正文时算了不落库", "content/models.py",
     '            if update_fields is not None:\n                kwargs["update_fields"] = list(\n                    dict.fromkeys(\n                        [*update_fields, "body_plain", "body_words", "body_minutes"]\n                    )\n                )\n',
     "",
     ["content/tests", "search/tests", "backoffice/tests"]),
    ("D10c", "内战只存说明时不重算纯文本", "scrims/models.py",
     'if update_fields is None or "description" in update_fields:',
     "if update_fields is None:",
     ["scrims/tests", "search/tests", "core/tests/test_autosave_events.py"]),
    ("D10d", "赛事只存说明时不重算纯文本", "tournaments/models.py",
     'if update_fields is None or "description" in update_fields:',
     "if update_fields is None:",
     ["tournaments/tests", "search/tests", "core/tests/test_autosave_events.py"]),
    ("D10e", "内战纯文本算了不落库", "scrims/models.py",
     '            if update_fields is not None:\n                kwargs["update_fields"] = list(\n                    dict.fromkeys([*update_fields, "description_plain"])\n                )\n',
     "",
     ["scrims/tests", "search/tests", "core/tests/test_autosave_events.py"]),
    # --- 212 D3 只在部分入口测过 --------------------------------------------------
    ("D3a", "资讯栏目介绍自动保存不查修订号", "backoffice/views/pages.py",
     "        stale = stale_base(index, request)  # someone else saved meanwhile (212, D3)\n        if autosave.wants(request) and stale:",
     "        stale = stale_base(index, request)  # someone else saved meanwhile (212, D3)\n        if False:",
     ["content/tests", "backoffice/tests"]),
    ("D3b", "编辑页不带修订号", "backoffice/templates/backoffice/content/page_edit.html",
     '      <input type="hidden" name="latest_revision" value="{{ item.latest_revision_id }}">\n', "",
     ["content/tests", "backoffice/tests"]),
    ("D3c", "首页置顶/栏目介绍不带修订号", "backoffice/templates/backoffice/content/draft_form.html",
     '      <input type="hidden" name="latest_revision" value="{{ item.latest_revision_id }}">\n', "",
     ["content/tests", "backoffice/tests"]),
]

_keys = [a for a in sys.argv[1:] if not a.startswith("--")]
if _keys:
    MUTATIONS = [m for m in MUTATIONS if m[0] in _keys]

OUT = Path("/tmp/sjtu-ow-217-16")
WORKERS = 4


def apply(copy: Path, filename: str, old: str, new: str) -> str | None:
    path = copy / filename
    original = path.read_text(encoding="utf-8")
    if original.count(old) != 1:
        return None
    path.write_text(original.replace(old, new, 1), encoding="utf-8")
    return original


def run_one(copy: Path, mutation) -> dict:
    key, name, filename, old, new, tests = mutation
    started = time.monotonic()
    original = apply(copy, filename, old, new)
    if original is None:
        return {"key": key, "name": name, "result": "not-found", "stage": "", "failed": [], "tail": ""}
    try:
        code, failed, tail = mg.pytest(copy, *tests)
        stage = "app"
        if code == 0:
            code, failed, tail = mg.pytest(copy)
            stage = "full"
    finally:
        (copy / filename).write_text(original, encoding="utf-8")
        for cache in (copy / filename).parent.glob("__pycache__/*"):
            cache.unlink()
    result = "caught" if code == 1 else "survived" if code == 0 else f"error({code})"
    return {
        "key": key,
        "name": name,
        "file": filename,
        "result": result,
        "stage": stage,
        "failed": failed[:2],
        "tail": tail,
        "seconds": round(time.monotonic() - started, 1),
    }


def main() -> int:
    # 只检查原文都在（一处），不跑测试
    for key, name, filename, old, _new, _t in MUTATIONS:
        count = (ROOT / filename).read_text(encoding="utf-8").count(old)
        if count != 1:
            print(f"!! {key} {name}: 原文在 {filename} 出现 {count} 次")
    if "--check" in sys.argv:
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    mg.REPO = ROOT
    mg.PYTHON = ROOT / ".venv" / "bin" / "python"
    copies = [OUT / "mcopies" / f"w{i}" for i in range(WORKERS)]
    for copy in copies:
        mg.make_copy(copy)
    print("基线（并行，未变异）：", flush=True)
    with ThreadPoolExecutor(WORKERS) as pool:
        baselines = list(pool.map(lambda c: mg.pytest(c), copies))
    for copy, (code, failed, tail) in zip(copies, baselines, strict=True):
        print(f"  {copy.name}: exit={code} {tail} {failed}", flush=True)
    if any(code != 0 for code, _, _ in baselines):
        print("基线不绿，停下（083 的教训）。")
        return 1
    free = list(copies)
    lock = threading.Lock()

    def work(mutation):
        with lock:
            copy = free.pop()
        try:
            return run_one(copy, mutation)
        finally:
            with lock:
                free.append(copy)

    rows = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for row in pool.map(work, MUTATIONS):
            rows.append(row)
            mark = {"caught": "ok", "survived": "!!"}.get(row["result"], "??")
            print(
                f"{mark} {row['key']} {row['name']}：{row['result']}（{row['stage']}）"
                f" {row['failed'][:1]} {row['tail']}",
                flush=True,
            )
    (OUT / "manual.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    )
    survived = [r["key"] for r in rows if r["result"] != "caught"]
    print(f"\n{len(rows)} 个变异，没抓到 / 出错：{survived}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
