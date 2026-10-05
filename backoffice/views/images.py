"""图片 (docs/admin.md 4.2): the library, uploads, the collections and the
picture dialog. Uploads go through Wagtail's image form (format, size,
WebP), permissions through its collection policy."""

from __future__ import annotations

from pathlib import Path

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from wagtail.images import get_image_model
from wagtail.images.forms import get_image_form
from wagtail.log_actions import log
from wagtail.models import Collection

from backoffice import access
from backoffice.access import image_policy
from backoffice.forms import (
    CollectionForm,
    ImageEditForm,
    ImageUploadForm,
    collections_for,
)
from backoffice.nav import placed
from backoffice.views.common import paginate, search_text
from backoffice.widgets import thumbnail
from core.converters import as_id

PER_PAGE = 48
CHOOSER_PER_PAGE = 24
GRID_SPEC = "max-320x240"


def _visible(user, actions=("choose", "change")):
    Image = get_image_model()
    if user.is_superuser:
        return Image.objects.all()
    return image_policy().instances_user_has_any_permission_for(user, list(actions))


def _filtered(request, images):
    query = search_text(request)
    if query:
        images = images.filter(title__icontains=query)
    collection = as_id(request.GET.get("collection"))
    if collection is not None:
        images = images.filter(collection_id=collection)
    return (
        images.select_related("collection").order_by("-created_at", "-pk"),
        query,
        collection,
    )


def _cells(page_obj):
    return [(image, thumbnail(image, GRID_SPEC)) for image in page_obj]


def _collections(user):
    """The collections this person sees pictures in, for the filter."""
    ids = _visible(user).values("collection_id")
    return Collection.objects.filter(pk__in=ids).order_by("path")


@placed("content", "images")
def image_list(request):
    user = request.user
    images, query, collection = _filtered(request, _visible(user))
    page_obj, extra_query = paginate(
        request, images.prefetch_renditions(GRID_SPEC), PER_PAGE
    )
    return render(
        request,
        "backoffice/content/images.html",
        {
            "page_title": "图片",
            "cells": _cells(page_obj),
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "collection": collection,
            "collections": _collections(user),
            "can_upload": collections_for(user, "add").exists(),
        },
    )


def _upload_one(request, upload, collection):
    """One file through Wagtail's form; (image, None) or (None, error)."""
    Image = get_image_model()
    form = get_image_form(Image)(
        data={
            "title": Path(upload.name).stem[:255] or "图片",
            "collection": collection.pk,
        },
        files={"file": upload},
        user=request.user,
        instance=Image(uploaded_by_user=request.user, collection=collection),
    )
    if not form.is_valid():
        errors = [error for field in form.errors.values() for error in field]
        return None, errors[0] if errors else "图片无效。"
    image = form.save()
    log(image, "wagtail.create", user=request.user)
    return image, None


@placed("content", "images")
def image_upload(request):
    form = ImageUploadForm(request.POST or None, user=request.user)
    if not form.fields["collection"].queryset.exists():
        raise PermissionDenied("你没有往任何集合里加图片的权限。")
    if request.method == "POST" and form.is_valid():
        uploads = request.FILES.getlist("files")
        done, failed = 0, []
        for upload in uploads[:50]:
            image, error = _upload_one(request, upload, form.cleaned_data["collection"])
            if image:
                done += 1
            else:
                failed.append(f"{upload.name}：{error}")
        if done:
            messages.success(request, f"上传了 {done} 张图片。")
        for line in failed:
            messages.error(request, line)
        if not uploads:
            messages.error(request, "没有选文件。")
        return redirect(
            "backoffice:images" if done and not failed else "backoffice:image_upload"
        )
    return render(
        request,
        "backoffice/content/image_upload.html",
        {
            "page_title": "上传图片",
            "form": form,
            "back_url": reverse("backoffice:images"),
            "back_label": "图片",
        },
    )


@placed("content", "images")
def image_edit(request, pk):
    image = get_object_or_404(get_image_model(), pk=pk)
    user = request.user
    if not image_policy().user_has_permission_for_instance(user, "change", image):
        raise PermissionDenied("你不能改这张图片。")
    form = ImageEditForm(
        request.POST or None,
        user=user,
        initial={"title": image.title, "collection": image.collection_id},
    )
    if request.method == "POST" and form.is_valid():
        image.title = form.cleaned_data["title"]
        image.collection = form.cleaned_data["collection"]
        image.save()
        log(image, "wagtail.edit", user=user)
        messages.success(request, f"「{image.title}」已保存。")
        return redirect("backoffice:images")
    return render(
        request,
        "backoffice/content/image_edit.html",
        {
            "page_title": image.title,
            "form": form,
            "image": image,
            "preview": thumbnail(image, "max-800x600"),
            "can_delete": image_policy().user_has_permission_for_instance(
                user, "delete", image
            ),
            "back_url": reverse("backoffice:images"),
            "back_label": "图片",
        },
    )


@placed("content", "images")
@require_POST
def image_delete(request, pk):
    image = get_object_or_404(get_image_model(), pk=pk)
    if not image_policy().user_has_permission_for_instance(
        request.user, "delete", image
    ):
        raise PermissionDenied("你不能删除这张图片。")
    title = image.title
    log(image, "wagtail.delete", user=request.user)
    image.delete()
    messages.success(request, f"「{title}」已删除。")
    return redirect("backoffice:images")


# --- the picture dialog -------------------------------------------------------


@placed("content", "images")
def image_chooser(request):
    """The dialog's inside: the pictures this person may choose."""
    user = request.user
    images, query, collection = _filtered(request, _visible(user, ("choose",)))
    page_obj, extra_query = paginate(
        request, images.prefetch_renditions(GRID_SPEC), CHOOSER_PER_PAGE
    )
    upload_to = collections_for(user, "add").order_by("path")
    return render(
        request,
        "backoffice/content/image_chooser.html",
        {
            "cells": _cells(page_obj),
            "page_obj": page_obj,
            "extra_query": extra_query,
            "query": query,
            "collection": collection,
            "collections": _collections(user),
            "upload_to": upload_to,
        },
    )


@placed("content", "images")
@require_POST
def image_chooser_upload(request):
    collection = (
        collections_for(request.user, "add")
        .filter(pk=as_id(request.POST.get("collection")))
        .first()
    )
    if collection is None:
        return JsonResponse({"error": "不能往这个集合里加图片。"}, status=403)
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "没有选文件。"}, status=400)
    image, error = _upload_one(request, upload, collection)
    if error:
        return JsonResponse({"error": error}, status=400)
    return JsonResponse(
        {"id": image.pk, "title": image.title, "thumb": thumbnail(image)}
    )


# --- collections (superusers) -------------------------------------------------


@placed("content", "images", allowed=access.is_superuser)
def collection_list(request):
    counts = dict(
        get_image_model()
        .objects.values_list("collection_id")
        .annotate(n=Count("pk"))
        .values_list("collection_id", "n")
    )
    collections = list(Collection.objects.order_by("path"))
    for collection in collections:
        collection.image_count = counts.get(collection.pk, 0)
        collection.indent = "　" * max(collection.depth - 2, 0)
    form = CollectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        parent = form.cleaned_data["parent"]
        child = parent.add_child(instance=Collection(name=form.cleaned_data["name"]))
        log(child, "wagtail.create", user=request.user)
        messages.success(request, f"集合「{child.name}」已建好。")
        return redirect("backoffice:collections")
    return render(
        request,
        "backoffice/content/collections.html",
        {
            "page_title": "图片集合",
            "collections": collections,
            "form": form,
            "back_url": reverse("backoffice:images"),
            "back_label": "图片",
        },
    )


@placed("content", "images", allowed=access.is_superuser)
@require_POST
def collection_rename(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    name = (request.POST.get("name") or "").strip()[:255]
    if collection.is_root() or not name:
        messages.error(request, "根集合不能改名，名称也不能空着。")
    else:
        collection.name = name
        collection.save()
        log(collection, "wagtail.edit", user=request.user)
        messages.success(request, f"已改名为「{name}」。")
    return redirect("backoffice:collections")


@placed("content", "images", allowed=access.is_superuser)
@require_POST
def collection_delete(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    if collection.is_root():
        messages.error(request, "根集合不能删除。")
    elif (
        collection.get_children().exists()
        or get_image_model().objects.filter(collection=collection).exists()
    ):
        messages.error(
            request, f"「{collection.name}」里还有图片或子集合，先挪走再删。"
        )
    else:
        name = collection.name
        log(collection, "wagtail.delete", user=request.user)
        collection.delete()
        messages.success(request, f"集合「{name}」已删除。")
    return redirect("backoffice:collections")
