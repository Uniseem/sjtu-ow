"""StreamField blocks for article and standard-page bodies (design 5.2)."""

from __future__ import annotations

import re

from wagtail import blocks
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock

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
    """Embed via Wagtail's built-in oEmbed providers. Bilibili is not among them."""

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        html = ""
        if value is not None:
            try:
                html = value.html or ""
            except Exception:  # noqa: BLE001 — oEmbed lookup can fail at render time
                html = ""
        match = _IFRAME_SRC.search(html)
        context["embed_src"] = match.group(1) if match else ""
        return context

    class Meta:
        icon = "media"
        label = "视频"
        template = "content/blocks/video.html"
        help_text = (
            "粘贴 YouTube、Vimeo 等 Wagtail 自带提供方支持的链接。暂不支持 B 站。"
        )


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
