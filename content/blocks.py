"""What is left of the StreamField bodies (design 5.2): since v6.70 bodies are
Markdown (content.markdown). Migration 0001 still names this block class, so
it stays, doing nothing more than Wagtail's own embed block.
"""

from wagtail.embeds.blocks import EmbedBlock


class VideoBlock(EmbedBlock):
    pass
