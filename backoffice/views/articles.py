"""文章 (docs/admin.md 4.2): the list, writing, editing, publishing.

Saving and publishing go through Wagtail's revisions and page actions, so
the permission checks (``OwnArticlesPermissionTester``), the action log and
the signals behind them (prerendering, the AI patrol, 「上线时通知」) are the
ones the Wagtail editor used.
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
from wagtail.log_actions import log

from backoffice.forms import ArticleForm
from backoffice.nav import placed
from backoffice.views.common import paginate, safe_next, search_text
from content.models import ArticleCategory, ArticlePage
from content.permissions import plain_writer, user_can_edit_author
from content.services import first_article_index
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


def _announced(pages) -> set[int]:
    from core.models import Broadcast

    ids = [page.pk for page in pages]
    return set(
        Broadcast.objects.filter(
            kind=Broadcast.Kind.ARTICLE, object_id__in=ids
        ).values_list("object_id", flat=True)
    )


def can_announce(page, user, announced: set[int]) -> bool:
    """「通知全体成员」 (design 10.4): editors, once, live or planned."""
    if not user_can_edit_author(user) or page.pk in announced:
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
    announced = _announced(page_obj) if user_can_edit_author(user) else set()
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
            "categories": ArticleCategory.objects.all(),
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
    if request.method == "POST" and form.is_valid():
        page = form.save(commit=False)
        page.live = False
        parent.add_child(instance=page)
        revision = page.save_revision(user=user, log_action=False, clean=False)
        log(
            instance=page,
            action="wagtail.create",
            user=user,
            revision=revision,
            content_changed=True,
        )
        if "publish" in request.POST:
            if page.permissions_for_user(user).can_publish():
                _publish(request, revision)
            else:
                messages.warning(request, "草稿已保存；你不能发布这篇文章。")
        else:
            messages.success(request, f"「{page.title}」的草稿已保存。")
        return redirect("backoffice:article_edit", page.pk)
    return render(
        request,
        "backoffice/content/article_edit.html",
        {
            "page_title": "写文章",
            "form": form,
            "article": None,
            "can_publish": True,
            "guide": plain_writer(user),
            "back_url": reverse("backoffice:articles"),
            "back_label": "文章",
        },
    )


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
    draft = page.get_latest_revision_as_object()
    form = ArticleForm(
        request.POST or None, instance=draft, user=user, parent=page.get_parent()
    )
    if request.method == "POST" and form.is_valid():
        publishing = "publish" in request.POST
        if publishing and not perms.can_publish():
            raise PermissionDenied("你不能发布这篇文章。")
        draft = form.save(commit=False)
        revision = draft.save_revision(
            user=user, log_action=True, previous_revision=page.latest_revision
        )
        if publishing:
            _publish(request, revision)
        else:
            messages.success(request, "草稿已保存。")
        return redirect("backoffice:article_edit", page.pk)
    page = ArticlePage.objects.annotate_approved_schedule().get(pk=page.pk)
    verdict = None
    from backoffice.access import reviews_content

    if reviews_content(user):
        from moderation.services import latest_verdict

        verdict = latest_verdict(page)
    announced = _announced([page]) if user_can_edit_author(user) else set()
    return render(
        request,
        "backoffice/content/article_edit.html",
        {
            "page_title": page.draft_title or page.title,
            "form": form,
            "article": page,
            "status": article_status(page),
            "url": page.get_url(request) if page.live else "",
            "can_publish": perms.can_publish(),
            "can_unpublish": perms.can_unpublish(),
            "can_delete": perms.can_delete(),
            "can_announce": can_announce(page, user, announced),
            "verdict": verdict,
            "guide": plain_writer(user),
            "back_url": reverse("backoffice:articles"),
            "back_label": "文章",
        },
    )


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
