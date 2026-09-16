"""Font library business logic (design 13.12.1, 13.12.2)."""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from core.fonts import download, processing
from core.fonts.css import regenerate_font_css

logger = logging.getLogger(__name__)

SAMPLE_TEXT = "上海交通大学守望先锋社区 SJTU Overwatch 2026 钻石 3 · Genji#51234"
MAX_ENABLED_VARIANTS = 6
STALE_PROCESSING_AFTER = timedelta(minutes=30)
REQUEUE_DELAY_SECONDS = 30


class FontInUse(Exception):
    """The font is referenced by a typography region and cannot be deleted."""


def next_css_name() -> str:
    """Allocate ``sjtu-font-<n>``; n is one past the highest used number."""
    from core.models import FontFamily

    used = []
    for name in FontFamily.objects.values_list("css_name", flat=True):
        match = re.fullmatch(r"sjtu-font-(\d+)", name or "")
        if match:
            used.append(int(match.group(1)))
    return f"sjtu-font-{max(used, default=0) + 1}"


def create_family(
    *,
    name,
    source,
    license_type,
    license_note="",
    license_confirmed=True,
    source_ref="",
    created_by=None,
):
    """Create a font. Retries the css_name if another admin grabbed it first."""
    from django.db import IntegrityError

    last_error = None
    for _attempt in range(5):
        try:
            with transaction.atomic():
                return _create_family(
                    name=name,
                    source=source,
                    license_type=license_type,
                    license_note=license_note,
                    license_confirmed=license_confirmed,
                    source_ref=source_ref,
                    created_by=created_by,
                )
        except IntegrityError as exc:
            last_error = exc
    raise last_error


def _create_family(
    *,
    name,
    source,
    license_type,
    license_note,
    license_confirmed,
    source_ref,
    created_by,
):
    from core.models import FontFamily

    return FontFamily.objects.create(
        name=name,
        css_name=next_css_name(),
        source=source,
        source_ref=source_ref,
        license_type=license_type,
        license_note=license_note,
        license_confirmed=license_confirmed,
        created_by=created_by if getattr(created_by, "pk", None) else None,
    )


def add_face_from_bytes(family, data: bytes, filename: str, weight=None, style=None):
    """Validate the font file, store it and queue processing."""
    from core.models import FontFace

    info = processing.inspect_font(data)
    resolved_weight = int(weight) if weight else info.weight
    if style:
        resolved_style = style
    else:
        resolved_style = (
            FontFace.Style.ITALIC if info.is_italic else FontFace.Style.NORMAL
        )

    face, _created = FontFace.objects.update_or_create(
        family=family,
        weight=resolved_weight,
        style=resolved_style,
        defaults={
            "status": FontFace.Status.PENDING,
            "progress": 0,
            "error": "",
            "glyph_count": info.glyph_count,
        },
    )
    if face.original_file:
        # Replacing a weight: the previous upload would otherwise stay on disk.
        face.original_file.delete(save=False)
    face.original_file.save(filename, ContentFile(data), save=True)
    queue_face(face)
    return face


def add_face_from_url(family, url: str, weight=None, style=None):
    data = download.fetch_bytes(url)
    return add_face_from_bytes(
        family,
        data,
        download.filename_from_url(url),
        weight=weight,
        style=style,
    )


def add_google_faces(family, weights):
    """Download Google's own slices; nothing is re-sliced (design 13.12.2)."""
    from core.models import FontFace

    css = download.fetch_google_css(family.source_ref or family.name, weights)
    faces = download.parse_google_css(css)
    grouped = download.download_google_slices(family.pk, faces)
    created = []
    for (weight, style), slices in sorted(grouped.items()):
        existing = FontFace.objects.filter(
            family=family, weight=weight, style=style
        ).first()
        if existing is not None:
            stale = [item for item in existing.slices or [] if item not in slices]
            processing.delete_slice_files(stale)
        face, _ = FontFace.objects.update_or_create(
            family=family,
            weight=weight,
            style=style,
            defaults={
                "status": FontFace.Status.READY,
                "progress": 100,
                "error": "",
                "slices": slices,
                "slice_count": len(slices),
                "total_bytes": sum(item["bytes"] for item in slices),
                "glyph_count": 0,
            },
        )
        created.append(face)
    return created


def queue_face(face) -> None:
    from core.models import FontFace
    from core.tasks import process_font_face

    FontFace.objects.filter(pk=face.pk).update(
        status=FontFace.Status.PENDING,
        progress=0,
        error="",
    )
    transaction.on_commit(lambda: process_font_face.enqueue(face.pk))


def another_face_is_processing(face_id: int) -> bool:
    """One font at a time (design 13.12.2); ignore runs that died mid-way."""
    from core.models import FontFace

    cutoff = timezone.now() - STALE_PROCESSING_AFTER
    return (
        FontFace.objects.filter(
            status=FontFace.Status.PROCESSING,
            updated_at__gte=cutoff,
        )
        .exclude(pk=face_id)
        .exists()
    )


def run_face_processing(face_id: int) -> str:
    """Slice one face.

    Returns ``done`` / ``requeue`` / ``skipped`` / ``failed``.
    """
    from core.models import FontFace

    face = FontFace.objects.select_related("family").filter(pk=face_id).first()
    if face is None:
        return "skipped"
    if face.family.source == "google_fonts" and not face.original_file:
        return "skipped"
    if another_face_is_processing(face_id):
        return "requeue"
    if not face.original_file:
        _fail(face, "没有原始字体文件，无法处理。")
        return "failed"

    FontFace.objects.filter(pk=face.pk).update(
        status=FontFace.Status.PROCESSING,
        progress=1,
        error="",
        updated_at=timezone.now(),
    )
    old_slices = list(face.slices or [])
    try:
        with face.original_file.open("rb") as handle:
            data = handle.read()
        info = processing.inspect_font(data)

        def on_progress(done, total):
            percent = max(1, min(99, int(done / max(total, 1) * 100)))
            FontFace.objects.filter(pk=face.pk).update(
                progress=percent,
                updated_at=timezone.now(),
            )

        slices = processing.build_face_slices(
            data,
            face.family_id,
            face.weight,
            face.style == FontFace.Style.ITALIC,
            info.codepoints,
            on_progress=on_progress,
        )
    except processing.FontError as exc:
        _fail(face, str(exc))
        return "failed"
    except Exception as exc:  # noqa: BLE001 — surface the reason in the admin
        logger.exception("字体处理失败 face=%s", face_id)
        _fail(face, f"处理失败：{exc}")
        return "failed"

    FontFace.objects.filter(pk=face.pk).update(
        status=FontFace.Status.READY,
        progress=100,
        error="",
        slices=slices,
        slice_count=len(slices),
        total_bytes=sum(item["bytes"] for item in slices),
        glyph_count=info.glyph_count,
        updated_at=timezone.now(),
    )
    retire_slice_files([item for item in old_slices if item not in slices])
    if is_face_in_use(face):
        regenerate_font_css()
    return "done"


SLICE_RETIRE_DELAY = timedelta(days=1)


def retire_slice_files(slices) -> None:
    """Delete replaced slices a day later; pages may still be loading them."""
    from core.tasks import delete_retired_font_slices

    paths = [item.get("path") for item in slices or [] if item.get("path")]
    if not paths:
        return
    run_after = timezone.now() + SLICE_RETIRE_DELAY
    transaction.on_commit(
        lambda: delete_retired_font_slices.using(run_after=run_after).enqueue(paths)
    )


def delete_unreferenced_slices(paths) -> int:
    """Delete the given slice files unless some weight still points at them."""
    from core.models import FontFace

    wanted = set(paths or [])
    if not wanted:
        return 0
    for face in FontFace.objects.exclude(slices=[]).only("slices"):
        for item in face.slices or []:
            wanted.discard(item.get("path"))
    processing.delete_slice_files([{"path": path} for path in sorted(wanted)])
    return len(wanted)


def _fail(face, message: str) -> None:
    from core.models import FontFace

    FontFace.objects.filter(pk=face.pk).update(
        status=FontFace.Status.FAILED,
        error=message,
        progress=0,
        updated_at=timezone.now(),
    )


def is_face_in_use(face) -> bool:
    """Is this (font, weight) used by any region?

    Uses the same rule as the generated stylesheet (design 12.4.5): a
    "跟随正文" region resolves to the body font, so a weight can be in use
    without any region naming that font directly.
    """
    from core.fonts.css import ordered_rules, used_pairs

    return (face.family_id, face.weight) in used_pairs(ordered_rules())


def delete_face(face) -> None:
    """Remove one weight and every file it owns, then refresh the stylesheet."""
    processing.delete_slice_files(face.slices)
    if face.original_file:
        face.original_file.delete(save=False)
    face.delete()
    regenerate_font_css()


def family_disk_bytes(family) -> int:
    """Original files plus every slice this font owns."""
    total = 0
    for face in family.faces.all():
        total += face.total_bytes or 0
        if face.original_file:
            try:
                total += face.original_file.size
            except (OSError, ValueError):
                pass
    return total


def reprocess_family(family) -> int:
    """Re-slice every uploaded face of a family (slicing rules may have changed)."""
    count = 0
    for face in family.faces.exclude(original_file=""):
        if not face.original_file:
            continue
        queue_face(face)
        count += 1
    return count


def delete_family(family) -> None:
    from core.models import TypographyRule

    regions = TypographyRule.objects.filter(
        mode=TypographyRule.Mode.CUSTOM, family=family
    )
    if regions.exists():
        labels = "、".join(rule.get_region_display() for rule in regions)
        raise FontInUse(f"「{family.name}」正在被排版区域使用（{labels}），不能删除。")
    for face in family.faces.all():
        processing.delete_slice_files(face.slices)
        if face.original_file:
            face.original_file.delete(save=False)
    family.delete()


def enabled_variants(rules=None) -> list[tuple]:
    """(font, weight) pairs the browser will actually download.

    Regions asking for a weight that has no processed file are left out: the
    browser fakes those instead of fetching anything.
    """
    from core.fonts.css import ordered_rules, used_faces

    rules = ordered_rules() if rules is None else list(rules)
    return [(face.family_id, face.weight) for face in used_faces(rules)]


def _default_weight(region: str) -> int:
    if region == "h1":
        return 700
    if region.startswith("h"):
        return 600
    return 400


def ensure_typography_rules() -> list:
    """Create the nine regions with their documented defaults (design 13.12.3)."""
    from core.models import TypographyRule

    defaults = {
        "body": TypographyRule.Mode.SYSTEM,
        "mono": TypographyRule.Mode.SYSTEM,
    }
    rules = []
    for region, _label in TypographyRule.Region.choices:
        rule, _created = TypographyRule.objects.get_or_create(
            region=region,
            defaults={
                "mode": defaults.get(region, TypographyRule.Mode.INHERIT),
                "weight": _default_weight(region),
            },
        )
        rules.append(rule)
    return rules
