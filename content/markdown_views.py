"""What the Markdown editor asks the server for (design 5.2, v6.70): the
preview, rendered exactly as the public page will be, and image uploads into
the image library. Both live under /admin/, behind Wagtail's admin check."""

from __future__ import annotations

from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from content.markdown import render

PREVIEW_LIMIT = 200_000
UPLOAD_RENDITION = "max-1600x1600"


@require_POST
def preview(request):
    return HttpResponse(render(request.POST.get("text", "")[:PREVIEW_LIMIT]))


@require_POST
def upload_image(request):
    """Into 「投稿图片」 through Wagtail's own image form (format, size), for
    whoever may add images there; answers with the rendition to insert."""
    from wagtail.images import get_image_model
    from wagtail.images.forms import get_image_form
    from wagtail.permissions import policy_registry

    from content.services import ensure_submission_image_collection

    Image = get_image_model()
    collection = ensure_submission_image_collection()
    policy = policy_registry.get_by_type(Image)
    allowed = policy.collections_user_has_permission_for(request.user, "add")
    if not allowed.filter(pk=collection.pk).exists():
        return JsonResponse({"error": "你没有上传图片的权限。"}, status=403)
    upload = request.FILES.get("image")
    if upload is None:
        return JsonResponse({"error": "没有收到图片。"}, status=400)
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
        return JsonResponse(
            {"error": errors[0] if errors else "图片无效。"}, status=400
        )
    image = form.save()
    from wagtail.log_actions import log

    log(image, "wagtail.create", user=request.user)
    return JsonResponse({"url": image.get_rendition(UPLOAD_RENDITION).url})
