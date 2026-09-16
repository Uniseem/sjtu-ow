"""Generate the site font stylesheet from the typography rules (design 13.12.4)."""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

logger = logging.getLogger(__name__)

CSS_DIR = "fonts/css"
SANS_FALLBACK = "var(--font-fallback)"
MONO_FALLBACK = "var(--font-mono-fallback)"

# Region -> the CSS variable suffix used by assets/css/input.css.
REGION_VARS = {
    "body": "body",
    "h1": "h1",
    "h2": "h2",
    "h3": "h3",
    "h4": "h4",
    "nav": "nav",
    "button": "button",
    "numeric": "numeric",
    "mono": "code",
}

# Regions whose rules live in input.css as element selectors: input.css already
# reads the weight/size variables, so only family/weight/size go to :root.
ELEMENT_REGIONS = {"body", "h1", "h2", "h3", "h4"}

REGION_SELECTORS = {
    "body": "body",
    "h1": "h1",
    "h2": "h2",
    "h3": "h3",
    "h4": "h4, h5, h6",
    "nav": ".font-nav",
    "button": ".font-button",
    "numeric": ".font-numeric",
    "mono": ".font-code",
}


def _decimal(value) -> str:
    text = f"{value:f}".rstrip("0").rstrip(".")
    return text or "0"


def _family_value(rule) -> str:
    fallback = MONO_FALLBACK if rule.region == "mono" else SANS_FALLBACK
    if rule.mode == "custom" and rule.family_id:
        return f'"{rule.family.css_name}", {fallback}'
    if rule.mode == "inherit":
        return "var(--font-body)"
    return fallback


def effective_family_id(rule, rules):
    """The font a region actually uses; "跟随正文" resolves to the body font."""
    if rule.mode == "custom":
        return rule.family_id
    if rule.mode == "inherit":
        body = next((item for item in rules if item.region == "body"), None)
        if body is not None and body.mode == "custom":
            return body.family_id
    return None


def used_pairs(rules) -> list[tuple]:
    """Every (font, weight) the site actually needs, in region order."""
    pairs = []
    for rule in rules:
        family_id = effective_family_id(rule, rules)
        if family_id and (family_id, rule.weight) not in pairs:
            pairs.append((family_id, rule.weight))
    return pairs


def used_faces(rules) -> list:
    """The processed faces behind :func:`used_pairs`, in use order."""
    from core.models import FontFace

    wanted = used_pairs(rules)
    if not wanted:
        return []
    faces = FontFace.objects.filter(
        family_id__in={item[0] for item in wanted},
        style=FontFace.Style.NORMAL,
        status=FontFace.Status.READY,
    ).select_related("family")
    by_key = {(face.family_id, face.weight): face for face in faces}
    return [by_key[key] for key in wanted if key in by_key]


def font_face_rules(face) -> list[str]:
    blocks = []
    for item in face.slices or []:
        path = item.get("path")
        if not path:
            continue
        url = default_storage.url(path)
        unicode_range = item.get("unicode_range") or ""
        lines = [
            "@font-face {",
            f'  font-family: "{face.family.css_name}";',
            f"  font-weight: {face.weight};",
            f"  font-style: {face.style};",
            "  font-display: swap;",
            f'  src: url("{url}") format("woff2");',
        ]
        if unicode_range:
            lines.append(f"  unicode-range: {unicode_range};")
        lines.append("}")
        blocks.append("\n".join(lines))
    return blocks


def build_css(rules) -> str:
    """Render the full stylesheet text for the given typography rules."""
    rules = list(rules)
    parts = [
        "/* 由「设置 → 排版设置」生成，请勿手工编辑。 */",
        "",
    ]
    for face in used_faces(rules):
        parts.extend(font_face_rules(face))
        parts.append("")

    variables = []
    extra_rules = []
    for rule in rules:
        var = REGION_VARS.get(rule.region)
        if var is None:
            continue
        variables.append(f"  --font-{var}: {_family_value(rule)};")
        declarations = []
        if rule.region in ELEMENT_REGIONS:
            variables.append(f"  --font-{var}-weight: {rule.weight};")
            if rule.size_rem is not None:
                variables.append(f"  --font-{var}-size: {_decimal(rule.size_rem)}rem;")
        else:
            # Only a custom font pins the weight: that is the file we sliced.
            # In system/inherit mode the template's own classes stay in charge.
            if rule.mode == "custom" and rule.family_id:
                declarations.append(f"  font-weight: {rule.weight};")
            if rule.size_rem is not None:
                declarations.append(f"  font-size: {_decimal(rule.size_rem)}rem;")
        if rule.line_height is not None:
            declarations.append(f"  line-height: {_decimal(rule.line_height)};")
        if rule.letter_spacing_em is not None:
            declarations.append(
                f"  letter-spacing: {_decimal(rule.letter_spacing_em)}em;"
            )
        if declarations:
            selector = REGION_SELECTORS[rule.region]
            extra_rules.append(selector + " {\n" + "\n".join(declarations) + "\n}")

    parts.append(":root {\n" + "\n".join(variables) + "\n}")
    if extra_rules:
        parts.append("")
        parts.extend(extra_rules)
    return "\n".join(parts).rstrip() + "\n"


def ordered_rules():
    from core.models import TypographyRule

    order = list(REGION_VARS)
    rules = list(TypographyRule.objects.select_related("family").all())
    rules.sort(key=lambda rule: order.index(rule.region))
    return rules


def regenerate_font_css(rules=None) -> str:
    """Write ``fonts.<hash>.css`` and point the site settings at it."""
    from core.models import SiteSettings

    rules = ordered_rules() if rules is None else list(rules)
    text = build_css(rules)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    name = f"{CSS_DIR}/fonts.{digest}.css"
    if not default_storage.exists(name):
        default_storage.save(name, ContentFile(text.encode("utf-8")))
    url = default_storage.url(name)

    settings_obj = SiteSettings.load()
    if settings_obj.font_css_path != url:
        settings_obj.font_css_path = url
        settings_obj.font_css_generated_at = timezone.now()
        settings_obj.save(update_fields=["font_css_path", "font_css_generated_at"])
        # Every prerendered page links this stylesheet (design 13.13.4).
        from core import prerender

        prerender.request_all()
    _clean_old_stylesheets(keep=name)
    return url


def _clean_old_stylesheets(keep: str, max_age=timedelta(days=1)) -> None:
    """Drop stylesheets older than a day; recent ones may still be referenced."""
    try:
        _, files = default_storage.listdir(CSS_DIR)
    except (FileNotFoundError, NotImplementedError, OSError):
        return
    cutoff = timezone.now() - max_age
    for filename in files:
        path = f"{CSS_DIR}/{filename}"
        if path == keep:
            continue
        try:
            if default_storage.get_modified_time(path) > cutoff:
                continue
            default_storage.delete(path)
        except Exception:  # noqa: BLE001 — cleanup must never break saving
            logger.warning("无法删除旧字体样式表 %s", path, exc_info=True)
