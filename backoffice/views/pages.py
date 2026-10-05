"""网站页面 (docs/admin.md 4.2): the homepage's pinned articles, the news
section's introduction and the plain pages (关于我们, the two legal texts)."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from wagtail.actions.publish_page_revision import PublishPageRevisionAction

from backoffice.forms import IndexIntroForm, PinnedArticlesForm, StandardPageForm
from backoffice.nav import placed
from backoffice.views.articles import article_status
from content.models import (
    MAX_PINNED_ARTICLES,
    ArticleIndexPage,
    HomePage,
    HomePagePinnedArticle,
    StandardPage,
)

# The fixed ones first, in this order; other plain pages after them.
FIXED_SLUGS = ("about", "terms", "privacy")


def _save_and_publish(request, draft, previous) -> None:
    revision = draft.save_revision(
        user=request.user, log_action=True, previous_revision=previous
    )
    PublishPageRevisionAction(revision, user=request.user).execute()


@placed("content", "pages")
def page_list(request):
    plain = list(StandardPage.objects.annotate_approved_schedule().order_by("path"))
    plain.sort(
        key=lambda page: (
            FIXED_SLUGS.index(page.slug) if page.slug in FIXED_SLUGS else 99,
            page.path,
        )
    )
    home = HomePage.objects.first()
    index = ArticleIndexPage.objects.order_by("path").first()
    return render(
        request,
        "backoffice/content/pages.html",
        {
            "page_title": "网站页面",
            "home": home,
            "pinned": (
                [rel.article for rel in home.pinned_articles.select_related("article")]
                if home
                else []
            ),
            "index": index,
            "plain": [(page, article_status(page)) for page in plain],
        },
    )


@placed("content", "pages")
def page_edit(request, pk):
    page = get_object_or_404(StandardPage, pk=pk)
    if not page.permissions_for_user(request.user).can_edit():
        raise PermissionDenied("你不能改这个页面。")
    draft = page.get_latest_revision_as_object()
    form = StandardPageForm(request.POST or None, instance=draft)
    if request.method == "POST" and form.is_valid():
        draft = form.save(commit=False)
        if "publish" in request.POST:
            _save_and_publish(request, draft, page.latest_revision)
            messages.success(request, f"「{draft.title}」已发布。")
        else:
            draft.save_revision(
                user=request.user,
                log_action=True,
                previous_revision=page.latest_revision,
            )
            messages.success(request, "草稿已保存。")
        return redirect("backoffice:page_edit", page.pk)
    page = StandardPage.objects.annotate_approved_schedule().get(pk=page.pk)
    return render(
        request,
        "backoffice/content/page_edit.html",
        {
            "page_title": page.draft_title or page.title,
            "form": form,
            "item": page,
            "status": article_status(page),
            "url": page.get_url(request) if page.live else "",
            "back_url": reverse("backoffice:pages"),
            "back_label": "网站页面",
        },
    )


@placed("content", "pages")
def page_preview(request, pk):
    page = get_object_or_404(StandardPage, pk=pk)
    draft = page.get_latest_revision_as_object()
    return draft.serve_preview(request, draft.default_preview_mode)


@placed("content", "pages")
def home_pins(request):
    """At most three, from the published articles, saved straight to the
    homepage (docs/admin.md 4.2)."""
    home = get_object_or_404(HomePage)
    current = [rel.article for rel in home.pinned_articles.select_related("article")]
    initial = {f"article_{n}": a.pk for n, a in enumerate(current, start=1)}
    form = PinnedArticlesForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        draft = home.get_latest_revision_as_object()
        draft.pinned_articles = [
            HomePagePinnedArticle(article=article, sort_order=number)
            for number, article in enumerate(
                form.cleaned_data["articles"][:MAX_PINNED_ARTICLES]
            )
        ]
        _save_and_publish(request, draft, home.latest_revision)
        messages.success(request, "首页的置顶文章已更新。")
        return redirect("backoffice:pages")
    return render(
        request,
        "backoffice/content/simple_form.html",
        {
            "page_title": "首页的置顶文章",
            "form": form,
            "intro": (
                "最多 3 篇，按这里的顺序排在首页最上面。只能选已经发布的文章。"
                "保存后首页马上更新。"
            ),
            "submit_label": "保存并更新首页",
            "back_url": reverse("backoffice:pages"),
            "back_label": "网站页面",
        },
    )


@placed("content", "pages")
def index_intro(request):
    index = ArticleIndexPage.objects.order_by("path").first()
    if index is None:
        return redirect("backoffice:pages")
    draft = index.get_latest_revision_as_object()
    form = IndexIntroForm(request.POST or None, initial={"intro": draft.intro})
    if request.method == "POST" and form.is_valid():
        draft.intro = form.cleaned_data["intro"]
        _save_and_publish(request, draft, index.latest_revision)
        messages.success(request, "资讯栏目的介绍已更新。")
        return redirect("backoffice:pages")
    return render(
        request,
        "backoffice/content/simple_form.html",
        {
            "page_title": "资讯栏目的介绍",
            "form": form,
            "submit_label": "保存并发布",
            "back_url": reverse("backoffice:pages"),
            "back_label": "网站页面",
        },
    )
