"""Fixed old-template references for the comment section, on the test machine.

Renders comments/section.html, _item.html, _reply.html and _composer.html with
Django for fixed comment shapes, and writes web/apps/site/src/testdata/
legacy-comments.json. ui.test.ts compares its Vue SSR output against these
(the same scheme 266/267 used for the shared components).

The old templates carry HTMX plumbing the new stack replaces with client-side
events (design-next 15.2); those bits are stripped before storing, each with
its reason:

- ``hx-*`` attributes and the ``#comment-sort`` hidden input + ``hx-include``:
  HTMX's whole-section swap becomes Vue state; the actions go through the
  generated API client.
- ``csrfmiddlewaretoken``: there is no Django form CSRF in the new stack.
- ``action=``/``method=`` on composer forms: the new forms submit via fetch;
  without scripts the account banner shows instead.
- ``data-slot="article-comments:5"`` keeps the page pk in the old slot hook;
  the new stack has no consumer, so the id is dropped.

The login link is interpolated raw by the old template (no urlencode), so the
Vue page passes pageUrl unencoded as well.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sjtu_ow.settings.dev")
import django  # noqa: E402

django.setup()
from django.template.loader import render_to_string  # noqa: E402

OUT = ROOT / "web/apps/site/src/testdata/legacy-comments.json"

DATE = "2026-10-10T13:00:00+00:00"
DT = datetime.fromisoformat(DATE)
PAGE_URL = "/news/weekend/"
LOGIN = "/accounts/login/?next=/news/weekend/"


def person(nickname, pk=2, active=True):
    return NS(pk=pk, nickname=nickname, avatar_id=None, is_active=active)


def comment(pk, nickname, body, **more):
    base = dict(
        pk=pk, anchor=f"comment-{pk}", is_deleted=False, is_hidden=False, is_pinned=False,
        author=person(nickname), author_id=2, created_at=DT, edited_at=None, body=body,
        like_count=0, reply_to_user=None,
    )
    base.update(more)
    return NS(**base)


def view(c, **over):
    """The CommentView shape the Vue components take."""
    base = dict(
        id=c.pk, user_id=c.author_id, author_name=c.author.nickname,
        reply_to_user_name=c.reply_to_user.nickname if c.reply_to_user else None,
        content=c.body, is_pinned=c.is_pinned, is_hidden=c.is_hidden, is_deleted=c.is_deleted,
        is_tombstone=False, like_count=c.like_count, liked_by_me=False, replies=None,
        edited_at=c.edited_at, created_at=DATE, updated_at=DATE,
    )
    base.update(over)
    return base


def strip(html):
    html = re.sub(r'\s+hx-[a-z-]+="[^"]*"', "", html)
    html = re.sub(r'<input type="hidden" name="csrfmiddlewaretoken"[^>]*>', "", html)
    html = re.sub(r'<input type="hidden" id="comment-sort"[^>]*>', "", html)
    html = re.sub(r'\s+action="[^"]*"', "", html)
    html = re.sub(r'\s+method="post"', "", html)
    html = html.replace('data-slot="article-comments:5"', 'data-slot="article-comments"')
    return html


cases = []


def add(component, path, props, context):
    # Empty pools keep avatar.html/cover_fallback from touching the database.
    cases.append(dict(component=component, props=props,
                      html=strip(render_to_string(path, {**context, "avatar_pool": [], "cover_pool": []}))))


c1 = comment(3, "小满", "写得好", like_count=1)
c2 = comment(4, "阿白", "学习了", author_id=9)
c_top = comment(5, "置顶的", "给大家顶起来", is_pinned=True, edited_at=DT)
c_hidden = comment(6, "潜水的", "这条被隐藏", is_hidden=True)
c_deleted = comment(7, "消失的", "这条被删除", is_deleted=True)
reply1 = comment(9, "阿白", "同问", author_id=9, reply_to_user=person("小满"))

C1, C2, C_TOP, C_HIDDEN, C_DELETED, REPLY1 = (
    view(c1, liked_by_me=True), view(c2), view(c_top, edited_at=DATE),
    view(c_hidden), view(c_deleted), view(reply1, liked_by_me=True),
)

# --- section -----------------------------------------------------------------
def thread_ctx(items, total, has_next=False, next_number=None):
    return dict(items=items, number=1, has_next=has_next, next_number=next_number, total=total, sort="new")


MEMBER_REQ = dict(request=NS(user=NS(id=9, is_authenticated=True)))


page = NS(pk=5, url=PAGE_URL, comments_enabled=True)

add("CComments", "comments/section.html",
    dict(commentsEnabled=True, thread=dict(total=2, page=1, pageSize=20, comments=[C1, C2]),
         sort="new", interactive=False, canPost=False, postProblems=[], canModerate=False,
         viewerId=None, pageUrl=PAGE_URL, loginUrl=LOGIN),
    dict(page=page, thread=thread_ctx([dict(comment=c1, replies=[]), dict(comment=c2, replies=[])], 2),
         interactive=False, can_moderate=False, post_problems=[], can_post=False, liked=set(), sort="new", oob=False))

add("CComments", "comments/section.html",
    dict(commentsEnabled=True, thread=dict(total=0, page=1, pageSize=20, comments=[]),
         sort="new", interactive=True, canPost=True, postProblems=[], canModerate=False,
         viewerId=9, pageUrl=PAGE_URL, loginUrl=LOGIN),
    dict(page=page, thread=thread_ctx([], 0), interactive=True, can_moderate=False,
         post_problems=[], can_post=True, liked=set(), sort="new", oob=False, **MEMBER_REQ))

add("CComments", "comments/section.html",
    dict(commentsEnabled=False, thread=dict(total=1, page=1, pageSize=20, comments=[C1]),
         sort="new", interactive=True, canPost=False, postProblems=[], canModerate=False,
         viewerId=9, pageUrl=PAGE_URL, loginUrl=LOGIN),
    dict(page=NS(pk=5, url=PAGE_URL, comments_enabled=False), thread=thread_ctx([dict(comment=c1, replies=[])], 1),
         interactive=True, can_moderate=False, post_problems=[], can_post=False, liked={3}, sort="new", oob=False, **MEMBER_REQ))

add("CComments", "comments/section.html",
    dict(commentsEnabled=True, thread=dict(total=0, page=1, pageSize=20, comments=[]),
         sort="new", interactive=True, canPost=False,
         postProblems=["你暂时无法使用此功能，如有疑问请联系管理员"], canModerate=False,
         viewerId=10, pageUrl=PAGE_URL, loginUrl=LOGIN),
    dict(page=page, thread=thread_ctx([], 0), interactive=True, can_moderate=False,
         post_problems=["你暂时无法使用此功能，如有疑问请联系管理员"], can_post=False, liked=set(), sort="new", oob=False, **MEMBER_REQ))

add("CComments", "comments/section.html",
    dict(commentsEnabled=True, thread=dict(total=25, page=1, pageSize=20, comments=[C1]),
         sort="new", interactive=False, canPost=False, postProblems=[], canModerate=False,
         viewerId=None, pageUrl=PAGE_URL, loginUrl=LOGIN),
    dict(page=page, thread=thread_ctx([dict(comment=c1, replies=[])], 25, has_next=True, next_number=2),
         interactive=False, can_moderate=False, post_problems=[], can_post=False, liked=set(), sort="new", oob=False))

# --- item --------------------------------------------------------------------
def item_ctx(item, *, interactive, can_post, can_moderate, viewer_pk=9, liked=frozenset()):
    return dict(item=item, interactive=interactive, can_post=can_post, can_moderate=can_moderate,
                liked=set(liked), request=NS(user=NS(id=viewer_pk, is_authenticated=True)))

add("CCommentItem", "comments/_item.html",
    dict(item=C1, interactive=False, canPost=False, canModerate=False, viewerId=None),
    item_ctx(dict(comment=c1, replies=[]), interactive=False, can_post=False, can_moderate=False, liked={3}))

add("CCommentItem", "comments/_item.html",
    dict(item=C1, interactive=True, canPost=True, canModerate=False, viewerId=9),
    item_ctx(dict(comment=c1, replies=[]), interactive=True, can_post=True, can_moderate=False, liked={3}))

add("CCommentItem", "comments/_item.html",
    dict(item=C_TOP, interactive=True, canPost=True, canModerate=False, viewerId=9),
    item_ctx(dict(comment=c_top, replies=[]), interactive=True, can_post=True, can_moderate=False))

add("CCommentItem", "comments/_item.html",
    dict(item=view(comment(8, "楼主", "主楼", like_count=2), replies=[view(reply1)]),
         interactive=True, canPost=True, canModerate=False, viewerId=9),
    item_ctx(dict(comment=comment(8, "楼主", "主楼", like_count=2), replies=[reply1]),
             interactive=True, can_post=True, can_moderate=False))

add("CCommentItem", "comments/_item.html",
    dict(item=C_DELETED, interactive=True, canPost=True, canModerate=False, viewerId=9),
    item_ctx(dict(comment=c_deleted, replies=[]), interactive=True, can_post=True, can_moderate=False))

add("CCommentItem", "comments/_item.html",
    dict(item=C_HIDDEN, interactive=True, canPost=True, canModerate=False, viewerId=9),
    item_ctx(dict(comment=c_hidden, replies=[]), interactive=True, can_post=True, can_moderate=False))

add("CCommentItem", "comments/_item.html",
    dict(item=C_HIDDEN, interactive=True, canPost=True, canModerate=True, viewerId=9),
    item_ctx(dict(comment=c_hidden, replies=[]), interactive=True, can_post=True, can_moderate=True))

add("CCommentItem", "comments/_item.html",
    dict(item=C2, interactive=True, canPost=True, canModerate=True, viewerId=9),
    item_ctx(dict(comment=c2, replies=[]), interactive=True, can_post=True, can_moderate=True))

# --- reply -------------------------------------------------------------------
add("CCommentReply", "comments/_reply.html",
    dict(reply=REPLY1, interactive=True, canPost=True, canModerate=False, viewerId=9),
    dict(reply=reply1, interactive=True, can_post=True, can_moderate=False, liked={9},
         request=NS(user=NS(id=9, is_authenticated=True))))

add("CCommentReply", "comments/_reply.html",
    dict(reply=REPLY1, interactive=False, canPost=False, canModerate=False, viewerId=None),
    dict(reply=reply1, interactive=False, can_post=False, can_moderate=False, liked=set(),
         request=NS(user=NS(id=0, is_authenticated=False))))

# --- composer ----------------------------------------------------------------
add("CCommentComposer", "comments/_composer.html",
    dict(draft=""),
    dict(page=page, parent=None, draft_body=""))

add("CCommentComposer", "comments/_composer.html",
    dict(parentName="小满", draft=""),
    dict(page=page, parent=c1, draft_body=""))
# The edit form's own template is _own.html; its shape (prefilled textarea,
# 保存修改) is covered inside the own-comment item fixture above it.

OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {len(cases)} comment fixtures to {OUT}")
