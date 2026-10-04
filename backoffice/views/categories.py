"""文章分类 (docs/admin.md 4.2). A category articles still use cannot be
deleted (design 5.3, v6.59): the button is left out and a typed request is
refused with the reason."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from wagtail.log_actions import log

from backoffice import access
from backoffice.forms import CategoryForm
from backoffice.nav import placed
from content.models import ArticleCategory


def _allowed(request, action: str = "change") -> None:
    if not access.edits_categories(request.user):
        raise PermissionDenied("文章分类只有内容编辑能改。")
    if not request.user.has_perm(f"content.{action}_articlecategory"):
        raise PermissionDenied("没有这项分类权限。")


@placed("content", "categories")
def category_list(request):
    _allowed(request)
    categories = ArticleCategory.objects.annotate(article_count=Count("articles"))
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
    _allowed(request, "change" if pk else "add")
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        log(category, "wagtail.edit" if pk else "wagtail.create", user=request.user)
        messages.success(request, f"分类「{category.name}」已保存。")
        return redirect("backoffice:categories")
    in_use = category.articles.count() if pk else 0
    return render(
        request,
        "backoffice/content/category_edit.html",
        {
            "page_title": category.name if pk else "新建分类",
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
    _allowed(request, "delete")
    category = get_object_or_404(ArticleCategory, pk=pk)
    count = category.articles.count()
    if count:
        messages.error(
            request,
            f"还有 {count} 篇文章在「{category.name}」里，先把它们改到别的分类再删。",
        )
        return redirect("backoffice:category_edit", category.pk)
    log(category, "wagtail.delete", user=request.user)
    name = category.name
    category.delete()
    messages.success(request, f"分类「{name}」已删除。")
    return redirect("backoffice:categories")
