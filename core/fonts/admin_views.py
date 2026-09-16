"""Wagtail admin views for the font library and typography (design 13.12)."""

from __future__ import annotations

import io
import zipfile
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.fonts import services
from core.fonts.css import (
    REGION_VARS,
    effective_family_id,
    font_face_rules,
    regenerate_font_css,
)
from core.fonts.download import DownloadError
from core.fonts.forms import (
    FontFaceAddForm,
    FontUploadForm,
    FontUrlForm,
    GoogleFontForm,
    TypographyFormSet,
    synthetic_weight_warnings,
    variant_warning,
)
from core.fonts.processing import FontError
from core.models import FontFace, FontFamily, SiteSettings, TypographyRule


def superuser_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("字体设置仅限超级管理员。")
        return view(request, *args, **kwargs)

    return wrapper


def _breadcrumbs(*items):
    crumbs = [{"url": reverse("wagtailadmin_home"), "label": "首页"}]
    crumbs.extend(items)
    return crumbs


@superuser_required
def font_index(request):
    families = FontFamily.objects.prefetch_related("faces").all()
    return render(
        request,
        "core/fonts/index.html",
        {
            "page_title": "字体库",
            "header_icon": "doc-full",
            "families": families,
            "sample_text": services.SAMPLE_TEXT,
            "breadcrumbs_items": _breadcrumbs({"url": "", "label": "字体库"}),
        },
    )


@superuser_required
def font_add(request):
    upload_form = FontUploadForm(prefix="upload")
    url_form = FontUrlForm(prefix="url")
    google_form = GoogleFontForm(prefix="google")
    if request.method == "POST":
        if "submit_upload" in request.POST:
            upload_form = FontUploadForm(request.POST, request.FILES, prefix="upload")
            if upload_form.is_valid():
                return _create_from_upload(request, upload_form)
        elif "submit_url" in request.POST:
            url_form = FontUrlForm(request.POST, prefix="url")
            if url_form.is_valid():
                return _create_from_url(request, url_form)
        elif "submit_google" in request.POST:
            google_form = GoogleFontForm(request.POST, prefix="google")
            if google_form.is_valid():
                return _create_from_google(request, google_form)
    return render(
        request,
        "core/fonts/add.html",
        {
            "page_title": "添加字体",
            "header_icon": "plus",
            "upload_form": upload_form,
            "url_form": url_form,
            "google_form": google_form,
            "breadcrumbs_items": _breadcrumbs(
                {"url": reverse("core_font_index"), "label": "字体库"},
                {"url": "", "label": "添加字体"},
            ),
        },
    )


def _create_from_upload(request, form):
    data = form.cleaned_data
    family = services.create_family(
        name=data["name"],
        source=FontFamily.Source.UPLOAD,
        license_type=data["license_type"],
        license_note=data["license_note"],
        license_confirmed=data["license_confirmed"],
        created_by=request.user,
    )
    uploaded = data["file"]
    services.add_face_from_bytes(
        family,
        form.font_data,
        uploaded.name,
        weight=data.get("weight") or None,
        style=data.get("style") or None,
    )
    messages.success(request, f"已添加字体「{family.name}」，正在后台处理。")
    return redirect("core_font_detail", pk=family.pk)


def _create_from_url(request, form):
    data = form.cleaned_data
    family = services.create_family(
        name=data["name"],
        source=FontFamily.Source.URL,
        source_ref=data["url"],
        license_type=data["license_type"],
        license_note=data["license_note"],
        license_confirmed=data["license_confirmed"],
        created_by=request.user,
    )
    try:
        services.add_face_from_url(
            family,
            data["url"],
            weight=data.get("weight") or None,
            style=data.get("style") or None,
        )
    except (DownloadError, FontError) as exc:
        family.delete()
        form.add_error("url", str(exc))
        return render(
            request,
            "core/fonts/add.html",
            {
                "page_title": "添加字体",
                "header_icon": "plus",
                "upload_form": FontUploadForm(prefix="upload"),
                "url_form": form,
                "google_form": GoogleFontForm(prefix="google"),
                "breadcrumbs_items": _breadcrumbs(
                    {"url": reverse("core_font_index"), "label": "字体库"},
                    {"url": "", "label": "添加字体"},
                ),
            },
        )
    messages.success(request, f"已下载字体「{family.name}」，正在后台处理。")
    return redirect("core_font_detail", pk=family.pk)


def _create_from_google(request, form):
    data = form.cleaned_data
    family = services.create_family(
        name=data["name"] or data["family_name"],
        source=FontFamily.Source.GOOGLE_FONTS,
        source_ref=data["family_name"],
        license_type=FontFamily.License.OPEN_SOURCE,
        license_note="Google Fonts 开源字体",
        license_confirmed=data["license_confirmed"],
        created_by=request.user,
    )
    try:
        faces = services.add_google_faces(family, data["weights"])
    except (DownloadError, FontError) as exc:
        family.delete()
        form.add_error("family_name", str(exc))
        return render(
            request,
            "core/fonts/add.html",
            {
                "page_title": "添加字体",
                "header_icon": "plus",
                "upload_form": FontUploadForm(prefix="upload"),
                "url_form": FontUrlForm(prefix="url"),
                "google_form": form,
                "breadcrumbs_items": _breadcrumbs(
                    {"url": reverse("core_font_index"), "label": "字体库"},
                    {"url": "", "label": "添加字体"},
                ),
            },
        )
    messages.success(
        request,
        f"已从 Google Fonts 下载「{family.name}」的 {len(faces)} 个字重。",
    )
    return redirect("core_font_detail", pk=family.pk)


@superuser_required
def font_detail(request, pk):
    family = get_object_or_404(FontFamily, pk=pk)
    face_form = FontFaceAddForm(prefix="face")
    if request.method == "POST":
        face_form = FontFaceAddForm(request.POST, request.FILES, prefix="face")
        if face_form.is_valid():
            data = face_form.cleaned_data
            try:
                if data.get("file"):
                    services.add_face_from_bytes(
                        family,
                        face_form.font_data,
                        data["file"].name,
                        weight=data.get("weight") or None,
                        style=data.get("style") or None,
                    )
                else:
                    services.add_face_from_url(
                        family,
                        data["url"],
                        weight=data.get("weight") or None,
                        style=data.get("style") or None,
                    )
            except (DownloadError, FontError) as exc:
                face_form.add_error(None, str(exc))
            else:
                messages.success(request, "已添加字重，正在后台处理。")
                return redirect("core_font_detail", pk=family.pk)
    return render(
        request,
        "core/fonts/detail.html",
        {
            "page_title": family.name,
            "header_icon": "doc-full",
            "family": family,
            "faces": family.faces.all(),
            "face_form": face_form,
            "sample_text": services.SAMPLE_TEXT,
            "used_by": [
                dict(TypographyRule.Region.choices)[region]
                for region in family.used_by_regions()
            ],
            "breadcrumbs_items": _breadcrumbs(
                {"url": reverse("core_font_index"), "label": "字体库"},
                {"url": "", "label": family.name},
            ),
        },
    )


@superuser_required
@require_POST
def font_reprocess(request, pk):
    family = get_object_or_404(FontFamily, pk=pk)
    count = services.reprocess_family(family)
    if count:
        messages.success(request, f"已重新排入处理队列：{count} 个字重。")
    else:
        messages.warning(
            request,
            "没有可以重新处理的字重（Google Fonts 字体使用下载好的分片，不重新切片）。",
        )
    return redirect("core_font_detail", pk=family.pk)


@superuser_required
def font_delete(request, pk):
    family = get_object_or_404(FontFamily, pk=pk)
    used_by = family.used_by_regions()
    labels = dict(TypographyRule.Region.choices)
    if request.method == "POST":
        try:
            services.delete_family(family)
        except services.FontInUse as exc:
            messages.error(request, str(exc))
            return redirect("core_font_detail", pk=family.pk)
        messages.success(request, f"已删除字体「{family.name}」。")
        return redirect("core_font_index")
    return render(
        request,
        "core/fonts/delete.html",
        {
            "page_title": f"删除「{family.name}」",
            "header_icon": "bin",
            "family": family,
            "blocked_regions": [labels[region] for region in used_by],
            "breadcrumbs_items": _breadcrumbs(
                {"url": reverse("core_font_index"), "label": "字体库"},
                {
                    "url": reverse("core_font_detail", args=[family.pk]),
                    "label": family.name,
                },
                {"url": "", "label": "删除"},
            ),
        },
    )


@superuser_required
def font_face_download(request, pk):
    face = get_object_or_404(FontFace.objects.select_related("family"), pk=pk)
    if face.original_file:
        return FileResponse(
            face.original_file.open("rb"),
            as_attachment=True,
            filename=face.original_file.name.rsplit("/", 1)[-1],
        )
    if not face.slices:
        messages.error(request, "这个字重还没有可下载的文件。")
        return redirect("core_font_detail", pk=face.family_id)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for item in face.slices:
            path = item.get("path")
            if not path or not default_storage.exists(path):
                continue
            with default_storage.open(path, "rb") as handle:
                archive.writestr(path.rsplit("/", 1)[-1], handle.read())
    buffer.seek(0)
    filename = f"{face.family.css_name}-{face.weight}-{face.style}.zip"
    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@superuser_required
@require_POST
def font_face_delete(request, pk):
    face = get_object_or_404(FontFace.objects.select_related("family"), pk=pk)
    family_id = face.family_id
    if services.is_face_in_use(face):
        messages.error(
            request,
            "这个字重正在被排版设置使用，请先在排版设置里换成其他字重。",
        )
        return redirect("core_font_detail", pk=family_id)
    services.delete_face(face)
    messages.success(request, "已删除字重。")
    return redirect("core_font_detail", pk=family_id)


@superuser_required
def font_faces_css(request):
    """@font-face rules for every processed weight, used by admin previews."""
    blocks = []
    faces = (
        FontFace.objects.filter(status=FontFace.Status.READY)
        .select_related("family")
        .order_by("family__name", "weight")
    )
    seen_families = set()
    for face in faces:
        blocks.extend(font_face_rules(face))
        stack = f'"{face.family.css_name}", sans-serif'
        if face.family_id not in seen_families:
            seen_families.add(face.family_id)
            blocks.append(f".font-preview-{face.family_id} {{ font-family: {stack}; }}")
        blocks.append(
            f".font-preview-{face.family_id}-{face.weight}-{face.style} "
            f"{{ font-family: {stack}; font-weight: {face.weight}; "
            f"font-style: {face.style}; }}"
        )
    response = HttpResponse("\n".join(blocks), content_type="text/css")
    response["Cache-Control"] = "no-store"
    return response


@superuser_required
def typography(request):
    services.ensure_typography_rules()
    queryset = TypographyRule.objects.select_related("family").all()
    order = list(REGION_VARS)
    queryset = sorted(queryset, key=lambda rule: order.index(rule.region))
    ids = [rule.pk for rule in queryset]
    base_queryset = TypographyRule.objects.filter(pk__in=ids).select_related("family")

    if request.method == "POST":
        formset = TypographyFormSet(request.POST, queryset=base_queryset)
        if formset.is_valid():
            rules = formset.save()
            saved = TypographyRule.objects.select_related("family").all()
            url = regenerate_font_css()
            messages.success(request, f"排版设置已保存，字体样式表已更新：{url}")
            for warning in _warnings(saved):
                messages.warning(request, warning)
            if not rules:
                messages.info(request, "没有改动需要保存。")
            return redirect("core_typography")
        messages.error(request, "排版设置没有保存，请修正下面的错误。")
    else:
        formset = TypographyFormSet(queryset=base_queryset)

    forms_by_region = sorted(
        formset.forms,
        key=lambda form: order.index(form.instance.region),
    )
    stats = _face_stats()
    saved_rules = [form.instance for form in forms_by_region]
    region_rows = []
    for form in forms_by_region:
        rule = form.instance
        family_id = effective_family_id(rule, saved_rules)
        region_rows.append(
            {
                "form": form,
                "region": rule.region,
                "label": rule.get_region_display(),
                "var": REGION_VARS[rule.region],
                "stats": stats.get(f"{family_id}-{rule.weight}"),
            }
        )
    settings_obj = SiteSettings.load()
    return render(
        request,
        "core/fonts/typography.html",
        {
            "page_title": "排版设置",
            "header_icon": "doc-full",
            "formset": formset,
            "region_rows": region_rows,
            "sample_text": services.SAMPLE_TEXT,
            "font_weights": _family_weights(),
            "settings_obj": settings_obj,
            "warnings": _warnings(TypographyRule.objects.select_related("family")),
            "breadcrumbs_items": _breadcrumbs({"url": "", "label": "排版设置"}),
        },
    )


def _warnings(rules) -> list[str]:
    rules = list(rules)
    found = [variant_warning(rules)]
    found.extend(synthetic_weight_warnings(rules))
    return [message for message in found if message]


def _family_weights() -> dict:
    """{family id: {css_name, weights[]}} for the live preview script."""
    result = {}
    faces = FontFace.objects.filter(
        status=FontFace.Status.READY,
        style=FontFace.Style.NORMAL,
    ).select_related("family")
    for face in faces:
        entry = result.setdefault(
            str(face.family_id),
            {"css_name": face.family.css_name, "weights": []},
        )
        if face.weight not in entry["weights"]:
            entry["weights"].append(face.weight)
    for entry in result.values():
        entry["weights"].sort()
    return result


def _face_stats() -> dict:
    """{"<family id>-<weight>": {slices, bytes}} shown next to each region."""
    stats = {}
    for face in FontFace.objects.filter(status=FontFace.Status.READY):
        stats[f"{face.family_id}-{face.weight}"] = {
            "slices": face.slice_count,
            "bytes": face.total_bytes,
        }
    return stats
