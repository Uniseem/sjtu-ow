# -*- coding: utf-8 -*-
"""Round 072 mutation checks: break each comment rule, expect its test to go red."""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}
T = ["comments/tests/test_comments.py"]
SVC = "comments/services.py"
VIEWS = "comments/views.py"

MUTATIONS = [
    ("功能权限不再检查", SVC,
     "    if not can_use(user, FEATURE):\n", "    if False:\n"),
    ("关闭评论的文章也收", SVC,
     "    if not page.comments_enabled:\n", "    if False:\n"),
    ("空评论也收", SVC,
     '    if not body:\n        problems.append("评论不能为空")\n', '    if False:\n        problems.append("评论不能为空")\n'),
    ("超长评论也收", SVC,
     "    if len(body) > MAX_BODY:\n", "    if False:\n"),
    ("跨文章回复也收", SVC,
     "        if parent.page_id != page.pk:\n", "        if False:\n"),
    ("隐藏的评论还能回复", SVC,
     "        elif not parent.visible:\n", "        elif False:\n"),
    ("回复的回复变成多层嵌套", SVC,
     "            if parent.parent_id is not None:\n                # A reply to a reply lands in the same thread (design 5.6).\n                parent = parent.parent\n",
     "            if False:\n                parent = parent.parent\n"),
    ("读者也能隐藏", SVC,
     '    if not can_moderate(actor):\n        raise CommentError("需要内容编辑权限")\n    comment.is_hidden = True\n',
     '    if False:\n        raise CommentError("需要内容编辑权限")\n    comment.is_hidden = True\n'),
    ("读者看得到隐藏的评论", SVC,
     "    if not moderator:\n        top = top.filter(\n", "    if False:\n        top = top.filter(\n"),
    ("置顶不再排最前", SVC,
     '    top = top.order_by("-is_pinned", "-created_at", "-id")\n', '    top = top.order_by("-created_at", "-id")\n'),
    ("评论不再送审", SVC,
     "    _submit_moderation(comment)\n    refresh_page(comment.page)\n", "    refresh_page(comment.page)\n"),
    ("评论不再刷新文章页", SVC,
     "    if page.live and url:\n        prerender.request_page(url, kind=\"article\")\n", "    return\n"),
    ("限流被拆掉", VIEWS,
     "    if _too_many(request.user):\n", "    if False:\n"),
    ("未登录的 HTMX 请求不再跳登录", VIEWS,
     "    if not request.user.is_authenticated:\n        return _login_response(request)\n    if _too_many(request.user):\n",
     "    if _too_many(request.user):\n"),
]


def clear_caches():
    for root, dirs, _files in os.walk(R + "comments"):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)


caught = 0
for label, rel, old, new in MUTATIONS:
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
             "-p", "no:cacheprovider", *T],
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
print(f"{caught}/{len(MUTATIONS)} mutations caught")
