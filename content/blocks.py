"""StreamField blocks for article and standard-page bodies (design 5.2)."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from wagtail import blocks
from wagtail.embeds.blocks import EmbedBlock
from wagtail.embeds.embeds import get_embed
from wagtail.embeds.exceptions import EmbedException
from wagtail.images.blocks import ImageChooserBlock

UNSUPPORTED_VIDEO_MESSAGE = (
    "只支持哔哩哔哩（B 站）视频链接，请粘贴 bilibili.com/video/ 或 b23.tv 地址。"
)

_IFRAME_SRC = re.compile(r"""\bsrc=["']([^"']+)["']""", re.IGNORECASE)


class CaptionedImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="图片")
    caption = blocks.CharBlock(required=False, max_length=200, label="图注")

    class Meta:
        icon = "image"
        label = "图片"
        template = "content/blocks/image.html"


class QuoteBlock(blocks.StructBlock):
    text = blocks.TextBlock(label="引用文字")
    attribution = blocks.CharBlock(required=False, max_length=100, label="出处")

    class Meta:
        icon = "openquote"
        label = "引用"
        template = "content/blocks/quote.html"


class VideoBlock(EmbedBlock):
    """Bilibili-only embed (design 5.2). Front-end uses iframe src, never vendor CSS."""

    def clean(self, value):
        if value is None:
            return value
        url = getattr(value, "url", value)
        if not url:
            return value
        try:
            get_embed(str(url))
        except EmbedException as exc:
            raise ValidationError(UNSUPPORTED_VIDEO_MESSAGE) from exc
        return value

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        html = ""
        if value is not None:
            try:
                html = value.html or ""
            except Exception:  # noqa: BLE001 — embed lookup can fail at render time
                html = ""
        match = _IFRAME_SRC.search(html)
        context["embed_src"] = match.group(1) if match else ""
        return context

    class Meta:
        icon = "media"
        label = "视频"
        template = "content/blocks/video.html"
        help_text = "粘贴哔哩哔哩视频链接（bilibili.com/video/ 或 b23.tv）。"


ARTICLE_BODY_BLOCKS = [
    (
        "paragraph",
        blocks.RichTextBlock(
            features=["h2", "h3", "bold", "italic", "ol", "ul", "link"],
            label="段落",
        ),
    ),
    ("image", CaptionedImageBlock()),
    ("quote", QuoteBlock()),
    ("video", VideoBlock()),
]
