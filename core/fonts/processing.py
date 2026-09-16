"""Parse, validate and slice font files with fontTools (design 13.12.2)."""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass, field

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from fontTools import subset
from fontTools.ttLib import TTFont, TTLibError

from core.fonts.slicing import build_slices, format_unicode_range

logger = logging.getLogger(__name__)

# OS/2 fsType: bit 1 = restricted license, bit 9 = bitmap embedding only.
FSTYPE_RESTRICTED = 0x0002
FSTYPE_BITMAP_ONLY = 0x0200

MAX_FONT_BYTES = 30 * 1024 * 1024


class FontError(Exception):
    """A font file cannot be used."""


class EmbeddingNotAllowed(FontError):
    """The font's fsType flag forbids web embedding."""


@dataclass
class FontInfo:
    family_name: str = ""
    weight: int = 400
    is_italic: bool = False
    fs_type: int = 0
    flavor: str = ""
    codepoints: set = field(default_factory=set)

    @property
    def glyph_count(self) -> int:
        return len(self.codepoints)


def _name_string(font: TTFont, name_id: int) -> str:
    table = font.get("name")
    if table is None:
        return ""
    record = table.getDebugName(name_id)
    return record or ""


def inspect_font(data: bytes) -> FontInfo:
    """Read metadata and the character set; raise FontError if unusable."""
    if not data:
        raise FontError("字体文件是空的。")
    if len(data) > MAX_FONT_BYTES:
        raise FontError(
            f"字体文件 {len(data) / 1024 / 1024:.1f}MB，超过 "
            f"{MAX_FONT_BYTES // 1024 // 1024}MB 上限。"
        )
    try:
        font = TTFont(io.BytesIO(data), fontNumber=0, lazy=True)
    except TTLibError as exc:
        raise FontError(f"无法解析字体文件：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 — fontTools raises many types
        raise FontError(f"无法解析字体文件：{exc}") from exc

    with font:
        os2 = font.get("OS/2")
        fs_type = int(getattr(os2, "fsType", 0) or 0)
        if fs_type & FSTYPE_RESTRICTED:
            raise EmbeddingNotAllowed(
                "字体的嵌入权限标记（OS/2 fsType）为「禁止嵌入」，不能用于网页。"
            )
        if fs_type & FSTYPE_BITMAP_ONLY:
            raise EmbeddingNotAllowed(
                "字体的嵌入权限标记只允许点阵嵌入，不能用于网页。"
            )
        weight = int(getattr(os2, "usWeightClass", 400) or 400)
        weight = min(900, max(100, round(weight / 100) * 100))
        is_italic = bool(int(getattr(os2, "fsSelection", 0) or 0) & 0x0001)
        head = font.get("head")
        if head is not None:
            is_italic = is_italic or bool(int(getattr(head, "macStyle", 0) or 0) & 0x02)
        try:
            codepoints = set(font.getBestCmap())
        except Exception as exc:  # noqa: BLE001
            raise FontError(f"字体没有可用的字符映射表：{exc}") from exc
        if not codepoints:
            raise FontError("字体里没有任何字符。")
        info = FontInfo(
            family_name=_name_string(font, 16) or _name_string(font, 1),
            weight=weight,
            is_italic=is_italic,
            fs_type=fs_type,
            flavor=font.flavor or "",
            codepoints=codepoints,
        )
    return info


def _subset_options() -> subset.Options:
    options = subset.Options()
    options.flavor = "woff2"
    options.notdef_outline = True
    options.ignore_missing_unicodes = True
    # Hinting costs ~12% of every CJK slice and modern browsers ignore it on
    # macOS/Android; Google's own web fonts drop it too.
    options.hinting = False
    options.drop_tables += ["FFTM"]
    return options


def subset_to_woff2(data: bytes, codepoints) -> bytes:
    """Return a WOFF2 file containing only the given code points."""
    font = TTFont(io.BytesIO(data), fontNumber=0)
    with font:
        subsetter = subset.Subsetter(options=_subset_options())
        subsetter.populate(unicodes=sorted(codepoints))
        subsetter.subset(font)
        font.flavor = "woff2"
        buffer = io.BytesIO()
        font.save(buffer)
    return buffer.getvalue()


def slice_storage_dir(family_id: int) -> str:
    return f"fonts/{family_id}"


def _slice_name(family_id: int, weight: int, italic: bool, index: int, digest: str):
    suffix = "i" if italic else ""
    return f"{slice_storage_dir(family_id)}/{weight}{suffix}-{index:03d}.{digest}.woff2"


def delete_slice_files(slices) -> None:
    for item in slices or []:
        path = item.get("path")
        if not path:
            continue
        try:
            if default_storage.exists(path):
                default_storage.delete(path)
        except Exception:  # noqa: BLE001 — deleting stale files must not fail a run
            logger.warning("无法删除字体分片 %s", path, exc_info=True)


def build_face_slices(
    data: bytes,
    family_id: int,
    weight: int,
    italic: bool,
    codepoints,
    on_progress=None,
) -> list[dict]:
    """Slice ``data`` and write every slice to storage; return slice records."""
    groups = build_slices(codepoints)
    total = len(groups)
    results: list[dict] = []
    for index, group in enumerate(groups):
        payload = subset_to_woff2(data, group)
        digest = hashlib.sha256(payload).hexdigest()[:8]
        name = _slice_name(family_id, weight, italic, index, digest)
        if not default_storage.exists(name):
            default_storage.save(name, ContentFile(payload))
        results.append(
            {
                "path": name,
                "unicode_range": format_unicode_range(group),
                "bytes": len(payload),
                "chars": len(group),
            }
        )
        if on_progress is not None:
            on_progress(index + 1, total)
    return results
