# -*- coding: utf-8 -*-
"""Round 073 mutation checks: break each like / pin / edit / delete rule, expect red."""
import io
import os
import shutil
import subprocess
import sys

R = "C:/Users/fyc12/Desktop/Claudee/sjtu-ow/"
ENV = {**os.environ, "PYTHONUTF8": "1"}
T = ["comments/tests/test_comment_extras.py"]
SVC = "comments/services.py"
VIEWS = "comments/views.py"
HOOKS = "comments/wagtail_hooks.py"
OWN = "comments/templates/comments/_own.html"

MUTATIONS = [
    ("未登录也能点赞", SVC,
     '    if not getattr(user, "is_authenticated", False):\n        raise CommentError(NOT_SIGNED_IN)\n    if not comment.visible:\n        raise CommentError("这条评论不能点赞")\n',
     '    if not comment.visible:\n        raise CommentError("这条评论不能点赞")\n'),
    ("隐藏或删除的也能点赞", SVC,
     '    if not comment.visible:\n        raise CommentError("这条评论不能点赞")\n', ''),
    ("点赞不加计数", SVC,
     '    if created:\n        Comment.objects.filter(pk=comment.pk).update(like_count=F("like_count") + 1)\n',
     '    if created:\n        pass\n'),
    ("再点一次不取消", SVC,
     '    else:\n        like.delete()\n        Comment.objects.filter(pk=comment.pk, like_count__gt=0).update(\n            like_count=F("like_count") - 1\n        )\n',
     '    else:\n        pass\n'),
    ("回复也能置顶", SVC,
     '    if not comment.is_top_level:\n        return "只能置顶顶层评论"\n', ''),
    ("隐藏或删除的也能置顶", SVC,
     '    if hidden or comment.is_deleted:\n        return "这条评论不能置顶"\n', ''),
    ("读者也能置顶", SVC,
     '    if not can_moderate(actor):\n        raise CommentError("需要内容编辑权限")\n    problem = pin_problem(comment)\n',
     '    problem = pin_problem(comment)\n'),
    ("置顶不检查 pin_problem", SVC,
     '    problem = pin_problem(comment)\n    if problem:\n        raise CommentError(problem)\n',
     '    problem = pin_problem(comment)\n'),
    ("置顶新的不取消旧的", SVC,
     '    release_pin(comment.page, keep=comment.pk)\n    comment.is_pinned = True\n',
     '    comment.is_pinned = True\n'),
    ("隐藏不取消置顶", SVC,
     '    comment.is_hidden = True\n    comment.is_pinned = False\n    comment.save(update_fields=["is_hidden", "is_pinned"])\n',
     '    comment.is_hidden = True\n    comment.save(update_fields=["is_hidden"])\n'),
    ("删除不取消置顶", SVC,
     '    comment.is_deleted = True\n    comment.is_pinned = False\n    comment.body = ""\n    comment.save(update_fields=["is_deleted", "is_pinned", "body"])\n',
     '    comment.is_deleted = True\n    comment.body = ""\n    comment.save(update_fields=["is_deleted", "body"])\n'),
    ("别人也能编辑和删除", SVC,
     '    if not getattr(actor, "is_authenticated", False) or comment.author_id != actor.pk:\n        raise CommentError("只能改自己的评论")\n',
     '    return None\n'),
    ("隐藏的评论还能编辑", SVC,
     '    _own(comment, actor)\n    if not comment.visible:\n        raise CommentError("这条评论已经不能编辑了")\n',
     '    _own(comment, actor)\n'),
    ("编辑成空也收", SVC,
     '    if not body:\n        raise CommentError("评论不能为空")\n    if len(body) > MAX_BODY:\n',
     '    if len(body) > MAX_BODY:\n'),
    ("编辑超长也收", SVC,
     '    if len(body) > MAX_BODY:\n        raise CommentError(f"评论最多 {MAX_BODY} 字")\n    if body == comment.body:\n',
     '    if body == comment.body:\n'),
    ("编辑不标记 edited_at", SVC,
     '    comment.edited_at = timezone.now()\n    comment.save(update_fields=["body", "edited_at"])\n',
     '    comment.save(update_fields=["body"])\n'),
    ("编辑不再送审", SVC,
     '    comment.save(update_fields=["body", "edited_at"])\n    transaction.on_commit(lambda: _after_write(comment))\n',
     '    comment.save(update_fields=["body", "edited_at"])\n    transaction.on_commit(lambda: refresh_page(comment.page))\n'),
    ("删除不清正文", SVC,
     '    comment.body = ""\n    comment.save(update_fields=["is_deleted", "is_pinned", "body"])\n',
     '    comment.save(update_fields=["is_deleted", "is_pinned"])\n'),
    ("最热不看赞数", SVC,
     '        ).order_by("-is_pinned", "-like_count", "-reply_count", "-created_at", "-id")\n',
     '        ).order_by("-is_pinned", "-reply_count", "-created_at", "-id")\n'),
    ("最热把隐藏的回复也算热度", SVC,
     '            reply_count=Count(\n                "replies", filter=Q(replies__is_hidden=False, replies__is_deleted=False)\n            )\n',
     '            reply_count=Count("replies")\n'),
    ("最热里置顶不再最前", SVC,
     '        ).order_by("-is_pinned", "-like_count", "-reply_count", "-created_at", "-id")\n',
     '        ).order_by("-like_count", "-reply_count", "-created_at", "-id")\n'),
    ("未知排序不归一", SVC,
     '    sort = sort if sort in SORTS else "new"\n', '    sort = sort\n'),
    ("已删除的顶层连回复一起消失", SVC,
     '        top = top.filter(Q(is_hidden=False, is_deleted=False) | Q(has_live_reply=True))\n',
     '        top = top.filter(Q(is_hidden=False, is_deleted=False))\n'),
    ("看不到自己点过的赞", SVC,
     '    if getattr(viewer, "is_authenticated", False):\n        liked = set(\n',
     '    if False:\n        liked = set(\n'),
    ("点赞限流被拆掉", VIEWS,
     '    if request.user.is_authenticated and over_limit(\n', '    if False and over_limit(\n'),
    ("HTMX 动作丢掉排序", VIEWS,
     '        sort = request.POST.get("sort") or request.GET.get("sort")\n', '        sort = None\n'),
    ("未登录的动作不再跳登录", VIEWS,
     '    if not request.user.is_authenticated:\n        return _login_response(request)\n    comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)\n    try:\n        action(comment=comment, **kwargs)\n',
     '    comment = get_object_or_404(Comment.objects.select_related("page"), pk=pk)\n    try:\n        action(comment=comment, **kwargs)\n'),
    ("加载更多丢掉排序", VIEWS,
     '        page_number=request.GET.get("page"),\n        sort=request.GET.get("sort"),\n',
     '        page_number=request.GET.get("page"),\n'),
    ("后台表单不查置顶规则", HOOKS,
     '                    if problem:\n                        self.add_error("is_pinned", problem)\n',
     '                    pass\n'),
    ("后台置顶不取消旧的", HOOKS,
     '        if self.form.cleaned_data.get("is_pinned"):\n            services.release_pin(self.form.instance.page_id, keep=self.form.instance.pk)\n',
     ''),
    ("别人的评论也显示编辑 / 删除", OWN,
     '{% if interactive and comment.author_id == request.user.id and not comment.is_hidden %}',
     '{% if interactive and not comment.is_hidden %}'),
]


def clear_caches():
    for root, dirs, _files in os.walk(R + "comments"):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)


START = int(sys.argv[1]) if len(sys.argv) > 1 else 0
caught = 0
for label, rel, old, new in MUTATIONS[START:]:
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
    mark = "✓ 被抓到" if hit else "✗ 没抓到"
    print(f"{mark} {label} | {summary[-1] if summary else run.stdout[-200:]}", flush=True)
print("---")
print(f"{caught}/{len(MUTATIONS) - START} mutations caught (from #{START + 1})")
