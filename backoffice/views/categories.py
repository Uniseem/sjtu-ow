"""文章分类 (docs/admin.md 4.2). A category articles still use cannot be
deleted (design 5.3, v6.59): the button is left out and a typed request is
refused with the reason. 「在用」 counts drafts too (212, D2): an autosaved
draft's category lives only in its revisions.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from wagtail.log_actions import log

from backoffice.forms import CategoryForm
from backoffice.nav import placed
from content.models import ArticleCategory
from content.services import category_in_use, category_use_counts
from core import autosave


def _may(request, action: str) -> None:
    """New and delete need more than the tab (change): placed checked that."""
    if not request.user.has_perm(f"content.{action}_articlecategory"):
        raise PermissionDenied("没有这项分类权限。")


@placed("content", "categories")
def category_list(request):
    counts = category_use_counts()
    categories = list(ArticleCategory.objects.all())
    for category in categories:
        category.article_count = counts.get(category.pk, 0)
    return render(
        request,
        "backoffice/content/categories.html",
        {
            "page_title": "分类",
            "categories": categories,
            "can_add": request.user.has_perm("content.add_articlecategory"),
            "can_delete": request.user.has_perm("content.delete_articlecategory"),
        },
    )


@placed("content", "categories")
def category_edit(request, pk=None):
    category = get_object_or_404(ArticleCategory, pk=pk) if pk else ArticleCategory()
    if not pk:
        _may(request, "add")
    form = CategoryForm(request.POST or None, instance=category)
    if autosave.wants(request):
        # A new one exists from the first change (design 13.17, v7.6); it
        # stays off the site until it has a name and an address. The fields
        # with an error sit this save out, the rest still create it (212, B6).
        if pk:
            saved = autosave.save_valid_fields(form)
            category = form.instance
            if saved:
                autosave.log_edit(category, request.user)
            return autosave.respond(
                autosave.Outcome(saved=saved, errors=autosave.errors_of(form))
            )
        category, saved = autosave.new_from_valid_fields(form, ArticleCategory())
        category.save()
        log(category, "wagtail.create", user=request.user)
        return autosave.respond(
            autosave.Outcome(
                saved=saved,
                errors=autosave.errors_of(form),
                location=reverse("backoffice:category_edit", args=[category.pk]),
            )
        )
    if request.method == "POST" and form.is_valid():
        category = form.save()
        if pk:
            autosave.log_edit(category, request.user)
        else:
            log(category, "wagtail.create", user=request.user)
        messages.success(request, f"分类「{category.name}」已保存。")
        return redirect("backoffice:categories")
    in_use = category_in_use(category) if pk else 0
    return render(
        request,
        "backoffice/content/category_edit.html",
        {
            "page_title": (category.name or "未命名分类") if pk else "新建分类",
            "form": form,
            "category": category if pk else None,
            "in_use": in_use,
            "can_delete": bool(pk)
            and not in_use
            and request.user.has_perm("content.delete_articlecategory"),
            "back_url": reverse("backoffice:categories"),
            "back_label": "分类",
        },
    )


@placed("content", "categories")
@require_POST
def category_delete(request, pk):
    _may(request, "delete")
    category = get_object_or_404(ArticleCategory, pk=pk)
    count = category_in_use(category)
    if count:
        messages.error(
            request,
            f"还有 {count} 篇文章（含草稿）在「{category.name}」里，"
            "先把它们改到别的分类再删。",
        )
        return redirect("backoffice:category_edit", category.pk)
    log(category, "wagtail.delete", user=request.user)
    name = category.name
    category.delete()
    messages.success(request, f"分类「{name}」已删除。")
    return redirect("backoffice:categories")
