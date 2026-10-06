"""文章 (docs/admin.md 4.2): the list, writing, editing, publishing.

Saving and publishing go through Wagtail's revisions and page actions, so
the permission checks (``OwnArticlesPermissionTester``), the action log and
the signals behind them (prerendering, the AI patrol, 「上线时通知」) are the
ones the Wagtail editor used. Since v7.9 (design 13.17) changes save
themselves as a draft (``content.drafts``); 「发布」 is still a button.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from wagtail.actions.delete_page import DeletePageAction
from wagtail.actions.publish_page_revision import PublishPageRevisionAction
from wagtail.actions.unpublish_page import UnpublishPageAction

from backoffice.forms import ArticleForm
from backoffice.nav import placed
from backoffice.views.common import paginate, safe_next, search_text
from content.drafts import STALE_MESSAGE, save_draft, stale_base, start_article
from content.models import ArticleCategory, ArticlePage
from content.permissions import plain_writer, user_can_edit_author
from content.services import first_article_index
from core import autosave
from core.converters import as_id

PER_PAGE = 30
STATUS_CHOICES = (
    ("draft", "草稿"),
    ("live", "已发布"),
    ("changed", "已发布·有改动"),
    ("scheduled", "定时上线"),
)


def article_status(page) -> tuple[str, str]:
    """(word, c-status kind); the page should carry annotate_approved_schedule."""
    if page.live:
        if page.has_unpublished_changes:
            return "已发布·有改动", "warn"
        return "已发布", "ok"
    if page.expired:
        return "已下线", "off"
    if page.approved_schedule:
        return "定时上线", "info"
    return "草稿", "done"


def sees_every_article(user) -> bool:
    """Content editors and superusers; everyone else has their own (14.3)."""
    return user_can_edit_author(user)


def _announced(pages) -> dict[int, tuple[int, bool]]:
    """Per article: how often it was announced, and whether one waits for it
    to go live (design 10.4, v7.5), in one query."""
    from core.models import Broadcast

    found: dict[int, tuple[int, bool]] = {}
    for object_id, waits in Broadcast.objects.filter(
        kind=Broadcast.Kind.ARTICLE, object_id__in=[page.pk for page in pages]
    ).values_list("object_id", "waits_for_publish"):
        sent, waiting = found.get(object_id, (0, False))
        found[object_id] = (sent + (not waits), waiting or waits)
    return found


def times_announced(page, announced: dict) -> int:
    return announced.get(page.pk, (0, False))[0]


def can_announce(page, user, announced: dict) -> bool:
    """「通知全体成员」 (design 10.4): editors, live or planned. v7.5: again
    after it went out; only a second plan for going live is not offered."""
    if not user_can_edit_author(user) or announced.get(page.pk, (0, False))[1]:
        return False
    if page.live:
        return True
    return bool(
        page.go_live_at and page.go_live_at > timezone.now() and page.approved_schedule
    )


@placed("content", "articles")
def article_list(request):
    user = request.user
    articles = ArticlePage.objects.annotate_approved_schedule().select_related(
        "category", "author", "owner"
    )
    every = sees_every_article(user)
    mine = not every or request.GET.get("mine") == "1"
    if mine:
        articles = articles.filter(owner=user)
    query = search_text(request)
    if query:
        articles = articles.filter(title__icontains=query)
    category = as_id(request.GET.get("category"))
    if category is not None:
        articles = articles.filter(category_id=category)
    status = request.GET.get("status") or ""
    if status == "draft":
        articles = articles.filter(live=False, expired=False, _approved_schedule=False)
    elif status == "live":
        articles = articles.filter(live=True)
    elif status == "changed":
        articles = articles.filter(live=True, has_unpublished_changes=True)
    elif status == "scheduled":
        articles = articles.filter(live=False, _approved_schedule=True)
    articles = articles.order_by("-latest_revision_created_at", "-pk")
    page_obj, extra_query = paginate(request, articles, PER_PAGE)
    announced = _announced(page_obj) if user_can_edit_author(user) else {}
    rows = []
    for page in page_obj:
        perms = page.permissions_for_user(user)
        rows.append(
            {
                "page": page,
                "status": article_status(page),
                "url": page.get_url(request) if page.live else "",
                "can_unpublish": perms.can_unpublish(),
                "can_announce": can_announce(page, user, announced),
                "announced": times_announced(page, announced),
            }
        )
    index = first_article_index()
    can_write = bool(index and index.permissions_for_user(user).can_add_subpage())
    return render(
        request,
        "backoffice/content/articles.html",
        {
            "page_title": "文章",
            "rows": rows,
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "categories": ArticleCategory.objects.named(),
            "category": category,
            "status": status,
            "status_choices": STATUS_CHOICES,
            "every": every,
            "mine": mine,
            "can_write": can_write,
        },
    )


def _publish(request, revision) -> None:
    PublishPageRevisionAction(revision, user=request.user).execute()
    page = revision.as_object()
    if page.go_live_at and page.go_live_at > timezone.now():
        messages.success(
            request,
            f"「{page.title}」会在 "
            f"{timezone.localtime(page.go_live_at):%m月%d日 %H:%M} 上线。",
        )
    else:
        messages.success(request, f"「{page.title}」已发布。")


def _autosave(request, form, page, parent):
    """Save what may be saved as a draft (design 13.17, v7.9): the fields
    that are fine, the rest keep what was stored. A new article is created
    by its first change, empty title and category included. A page someone
    else saved since this editor opened it refuses the save (212, D3)."""
    user = request.user
    if page is not None and stale_base(page, request):
        return autosave.respond(autosave.Outcome(errors={"__all__": [STALE_MESSAGE]}))
    valid = form.is_valid()
    draft = form.finish(form.instance)  # the valid fields are applied to it
    saved = autosave.valid_changes(form)
    errors = {} if valid else autosave.errors_of(form)
    outcome = autosave.Outcome(saved=saved, errors=errors)
    if page is None:
        page = start_article(parent, draft, user)
        outcome.values["latest_revision"] = page.latest_revision_id
        outcome.location = reverse("backoffice:article_edit", args=[page.pk])
        outcome.replace["[data-article-preview]"] = (
            f'<a class="c-btn c-btn--quiet" data-article-preview href="'
            f'{reverse("backoffice:article_preview", args=[page.pk])}" '
            'target="_blank" rel="noopener">预览草稿</a>'
        )
    elif saved:
        revision = save_draft(page, draft, user)
        outcome.values["latest_revision"] = revision.pk
    if "slug" in form.fields and draft.slug != form.initial.get("slug"):
        outcome.values["slug"] = draft.slug
    return autosave.respond(outcome)


def _form_page(request, form, article):
    """The page for writing or editing; ``article`` is None for a new one."""
    user = request.user
    context = {
        "page_title": "写文章",
        "form": form,
        "article": None,
        # A new article is the writer's own, so publishing it comes down to
        # 发布 on the section (216, B10); it was shown to everyone and a
        # writer without it got 「你不能发布」 only after pressing it.
        "can_publish": form.parent is not None
        and form.parent.permissions_for_user(user).can_publish_subpage(),
        "guide": plain_writer(user),
        "back_url": reverse("backoffice:articles"),
        "back_label": "文章",
    }
    if article is None:
        return render(request, "backoffice/content/article_edit.html", context)
    perms = article.permissions_for_user(user)
    page = ArticlePage.objects.annotate_approved_schedule().get(pk=article.pk)
    verdict = None
    from backoffice.access import reviews_content

    if reviews_content(user):
        from moderation.services import latest_verdict

        verdict = latest_verdict(page)
    announced = _announced([page]) if user_can_edit_author(user) else {}
    context.update(
        {
            "page_title": page.draft_title or "（无标题）",
            "article": page,
            "status": article_status(page),
            "url": page.get_url(request) if page.live else "",
            "can_publish": perms.can_publish(),
            "can_unpublish": perms.can_unpublish(),
            "can_delete": perms.can_delete(),
            "can_announce": can_announce(page, user, announced),
            "announced": times_announced(page, announced),
            "verdict": verdict,
        }
    )
    return render(request, "backoffice/content/article_edit.html", context)


def _submit(request, form, page, parent):
    """The whole form, without the script or by 「发布」: checked whole,
    saved as a draft, published if asked and allowed. A page someone else
    saved since this editor opened it refuses the save (212, D3)."""
    user = request.user
    if not form.is_valid():
        return _form_page(request, form, page)
    if page is not None and stale_base(page, request):
        messages.error(request, STALE_MESSAGE)
        return _form_page(request, form, page)
    draft = form.finish(form.instance)
    if page is None:
        page = start_article(parent, draft, user)
        revision = page.latest_revision
    else:
        revision = save_draft(page, draft, user)
    if "publish" in request.POST:
        if page.permissions_for_user(user).can_publish():
            _publish(request, revision)
        else:
            messages.warning(request, "草稿已保存；你不能发布这篇文章。")
    else:
        messages.success(request, "草稿已保存。")
    return redirect("backoffice:article_edit", page.pk)


@placed("content", "articles")
def article_new(request):
    user = request.user
    parent = first_article_index()
    if parent is None:
        raise Http404("还没有资讯栏目，先运行 init_site。")
    if not parent.permissions_for_user(user).can_add_subpage():
        raise PermissionDenied("你不能在资讯栏目里写文章。")
    form = ArticleForm(
        request.POST or None,
        instance=ArticlePage(owner=user),
        user=user,
        parent=parent,
    )
    if request.method != "POST":
        return _form_page(request, form, None)
    if autosave.wants(request):
        return _autosave(request, form, None, parent)
    return _submit(request, form, None, parent)


def _editable(request, pk):
    page = get_object_or_404(ArticlePage, pk=pk)
    perms = page.permissions_for_user(request.user)
    if not perms.can_edit():
        raise PermissionDenied("你不能编辑这篇文章。")
    return page, perms


@placed("content", "articles")
def article_edit(request, pk):
    user = request.user
    page, perms = _editable(request, pk)
    parent = page.get_parent()
    draft = page.get_latest_revision_as_object()
    form = ArticleForm(request.POST or None, instance=draft, user=user, parent=parent)
    if request.method != "POST":
        return _form_page(request, form, page)
    if "publish" in request.POST and not perms.can_publish():
        raise PermissionDenied("你不能发布这篇文章。")
    if autosave.wants(request):
        return _autosave(request, form, page, parent)
    return _submit(request, form, page, parent)


@placed("content", "articles")
def article_preview(request, pk):
    """The latest draft through the public template, for whoever may edit it."""
    page, _perms = _editable(request, pk)
    draft = page.get_latest_revision_as_object()
    return draft.serve_preview(request, draft.default_preview_mode)


@placed("content", "articles")
@require_POST
def article_unpublish(request, pk):
    page = get_object_or_404(ArticlePage, pk=pk)
    if not page.permissions_for_user(request.user).can_unpublish():
        raise PermissionDenied("你不能撤下这篇文章。")
    UnpublishPageAction(page, user=request.user).execute()
    messages.success(request, f"「{page.title}」已撤下，变回草稿。")
    return redirect(safe_next(request, reverse("backoffice:articles")))


@placed("content", "articles")
@require_POST
def article_delete(request, pk):
    page = get_object_or_404(ArticlePage, pk=pk)
    if not page.permissions_for_user(request.user).can_delete():
        raise PermissionDenied("你不能删除这篇文章。")
    title = page.title
    DeletePageAction(page, user=request.user).execute()
    messages.success(request, f"「{title}」已删除。")
    return redirect("backoffice:articles")
