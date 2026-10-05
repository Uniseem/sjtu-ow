"""网站页面 (docs/admin.md 4.2): the homepage's pinned articles, the news
section's introduction and the plain pages (关于我们, the two legal texts).

All four save themselves as drafts and go live on 「发布」 (design 13.17,
v7.9); the pins and the intro went live on every save until then."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from wagtail.actions.publish_page_revision import PublishPageRevisionAction

from backoffice.forms import IndexIntroForm, PinnedArticlesForm, StandardPageForm
from backoffice.nav import placed
from backoffice.views.articles import article_status
from content.drafts import save_draft
from content.models import (
    MAX_PINNED_ARTICLES,
    ArticleIndexPage,
    HomePage,
    HomePagePinnedArticle,
    StandardPage,
)
from core import autosave

# The fixed ones first, in this order; other plain pages after them.
FIXED_SLUGS = ("about", "terms", "privacy")


def _save(request, page, draft, *, published: str) -> None:
    """The whole form (without the script, or 「发布」): a draft, then live
    if asked."""
    revision = save_draft(page, draft, request.user)
    if "publish" in request.POST:
        PublishPageRevisionAction(revision, user=request.user).execute()
        messages.success(request, published)
    else:
        messages.success(request, "草稿已保存。")


def _draft_page(request, page, form, *, title, intro="", back=True):
    """The pins and the intro: the form, 「发布」, and how the page stands."""
    page = type(page).objects.annotate_approved_schedule().get(pk=page.pk)
    return render(
        request,
        "backoffice/content/draft_form.html",
        {
            "page_title": title,
            "form": form,
            "intro": intro,
            "item": page,
            "status": article_status(page),
            "back_url": reverse("backoffice:pages") if back else "",
            "back_label": "网站页面",
        },
    )


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
    if autosave.wants(request):
        valid = form.is_valid()
        saved = autosave.valid_changes(form)
        if saved:
            save_draft(page, form.instance, request.user)  # the fine fields applied
        errors = {} if valid else autosave.errors_of(form)
        return autosave.respond(autosave.Outcome(saved=saved, errors=errors))
    if request.method == "POST" and form.is_valid():
        _save(
            request, page, form.instance, published=f"「{form.instance.title}」已发布。"
        )
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
    """At most three, from the published articles; a draft of the homepage
    until 「发布」 (docs/admin.md 4.2, v7.9)."""
    home = get_object_or_404(HomePage)
    draft = home.get_latest_revision_as_object()
    current = [rel.article for rel in draft.pinned_articles.all()]
    initial = {f"article_{n}": a.pk for n, a in enumerate(current, start=1)}
    form = PinnedArticlesForm(request.POST or None, initial=initial)
    if request.method == "POST":
        valid = form.is_valid()
        if valid:
            draft.pinned_articles = [
                HomePagePinnedArticle(article=article, sort_order=number)
                for number, article in enumerate(
                    form.cleaned_data["articles"][:MAX_PINNED_ARTICLES]
                )
            ]
        if autosave.wants(request):
            saved = autosave.valid_changes(form)
            if valid and saved:
                save_draft(home, draft, request.user)
            errors = {} if valid else autosave.errors_of(form)
            return autosave.respond(autosave.Outcome(saved=saved, errors=errors))
        if valid:
            _save(request, home, draft, published="首页的置顶文章已更新。")
            return redirect("backoffice:home_pins")
    return _draft_page(
        request,
        home,
        form,
        title="首页的置顶文章",
        intro=(
            "最多 3 篇，按这里的顺序排在首页最上面。只能选已经发布的文章。"
            "改了自动存成草稿，点「发布」首页才更新。"
        ),
    )


@placed("content", "pages")
def index_intro(request):
    index = ArticleIndexPage.objects.order_by("path").first()
    if index is None:
        return redirect("backoffice:pages")
    draft = index.get_latest_revision_as_object()
    form = IndexIntroForm(request.POST or None, initial={"intro": draft.intro})
    if request.method == "POST":
        valid = form.is_valid()
        if valid:
            draft.intro = form.cleaned_data["intro"]
        if autosave.wants(request):
            saved = autosave.valid_changes(form)
            if valid and saved:
                save_draft(index, draft, request.user)
            errors = {} if valid else autosave.errors_of(form)
            return autosave.respond(autosave.Outcome(saved=saved, errors=errors))
        if valid:
            _save(request, index, draft, published="资讯栏目的介绍已更新。")
            return redirect("backoffice:index_intro")
    return _draft_page(request, index, form, title="资讯栏目的介绍")
