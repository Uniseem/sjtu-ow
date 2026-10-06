"""Markdown for article and page bodies and event descriptions (design 5.2,
v6.70).

One renderer for everything that shows or reads them: the public pages, the
admin preview, word counts, search and moderation, so what the editor
previews is what the page shows. CommonMark plus tables and strikethrough;
one newline is a line break; no HTML (it shows as text); # and ## are
second-level headings and ### or smaller third-level, the page title being
the first; an image alone on a line becomes a figure with its caption, and
only this site's images are shown; a Bilibili link alone on a line becomes
the player.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse

from django.conf import settings
from django.utils.html import escape, strip_tags
from django.utils.safestring import SafeString, mark_safe
from markdown_it import MarkdownIt
from markdown_it.token import Token

# A bare address in running text, up to the first space or Chinese
# punctuation; trailing ASCII punctuation is the sentence's, not the link's.
BARE_URL = re.compile(r"https?://[^\s<>\"'（）【】「」『』《》，。！？；：、]+")
TRAILING = ".,;:!?)]}'\""
HEADING_TAGS = {"h1": "h2", "h2": "h2", "h3": "h3", "h4": "h3", "h5": "h3", "h6": "h3"}
VIDEO_TITLE = "B 站视频"


@dataclass(frozen=True)
class Rendered:
    html: SafeString
    images: int
    videos: int


def own_image(src: str) -> bool:
    """On this site: a path here, or the site's own address (the public
    pages' CSP allows no other images, 15)."""
    parsed = urlparse(src)
    if not parsed.scheme and not parsed.netloc:
        return src.startswith("/")
    site = urlparse(getattr(settings, "SITE_URL", "") or "")
    return (
        parsed.scheme in ("http", "https")
        and bool(site.netloc)
        and (parsed.netloc == site.netloc)
    )


def video_src(url: str) -> str:
    """The Bilibili player for a video address, or "" for anything else."""
    from content import embeds

    url = url.strip()
    host = (urlparse(url).hostname or "").lower()
    if host in embeds.BILIBILI_HOSTS:
        bvid, page = embeds.extract_bvid_and_page(url)
        return embeds.player_src(bvid, page) if bvid else ""
    if host in embeds.B23_HOSTS:
        # Short links need one lookup; Wagtail keeps the answer (Embed) —
        # and a miss is remembered too, for an hour, so a dead link does
        # not put every render on the network (design 5.2, v7.14).
        from wagtail.embeds.embeds import get_embed
        from wagtail.embeds.exceptions import EmbedException

        try:
            found = re.search(r'\bsrc="([^"]+)"', get_embed(url).html or "")
        except EmbedException:
            embeds.remember_failed_lookup(url)
            return ""
        return found.group(1) if found else ""
    return ""


def _figure(src: str, caption: str) -> str:
    img = f'<img src="{escape(src)}" alt="{escape(caption)}" loading="lazy">'
    note = f"<figcaption>{escape(caption)}</figcaption>" if caption else ""
    return f"<figure>{img}{note}</figure>\n"


def _player(src: str) -> str:
    return (
        f'<figure class="c-prose__video"><iframe src="{escape(src)}" '
        f'title="{VIDEO_TITLE}" allowfullscreen loading="lazy" '
        'referrerpolicy="strict-origin-when-cross-origin"></iframe></figure>\n'
    )


def _html_block(content: str) -> Token:
    token = Token("html_block", "", 0)
    token.content = content
    token.block = True
    return token


def _alone(inline: Token) -> list[Token]:
    return [
        child
        for child in inline.children or []
        if not (child.type == "text" and not child.content.strip())
    ]


def _standalone(inline: Token, md: MarkdownIt, env: dict) -> Token | None:
    """Images, one to a line, or a video link that are the whole paragraph."""
    children = _alone(inline)
    images = [child for child in children if child.type == "image"]
    lines = [child for child in children if child.type in ("softbreak", "hardbreak")]
    if images and len(images) + len(lines) == len(children):
        if not all(own_image(image.attrGet("src") or "") for image in images):
            return None
        figures = []
        for image in images:
            caption = md.renderer.renderInlineAsText(
                image.children or [], md.options, env
            )
            figures.append(_figure(image.attrGet("src") or "", caption))
        env["images"] = env.get("images", 0) + len(images)
        return _html_block("".join(figures))
    url = ""
    if len(children) == 1 and children[0].type == "text":
        url = children[0].content.strip()
        if not BARE_URL.fullmatch(url):
            url = ""
    elif (
        len(children) == 3
        and children[0].type == "link_open"
        and children[2].type == "link_close"
    ):
        url = children[0].attrGet("href") or ""
    src = video_src(url) if url else ""
    if not src:
        return None
    env["videos"] = env.get("videos", 0) + 1
    return _html_block(_player(src))


def _link_bare_urls(inline: Token, md: MarkdownIt) -> None:
    """Pasted addresses become links (CommonMark leaves them as text)."""
    out, depth = [], 0
    for child in inline.children or []:
        if child.type == "link_open":
            depth += 1
        elif child.type == "link_close":
            depth -= 1
        if child.type != "text" or depth or "://" not in child.content:
            out.append(child)
            continue
        text, start = child.content, 0
        for match in BARE_URL.finditer(text):
            url = match.group(0).rstrip(TRAILING)
            href = md.normalizeLink(url)
            if not url or not md.validateLink(href):
                continue
            end = match.start() + len(url)
            if match.start() > start:
                out.append(_text(text[start : match.start()]))
            opening = Token("link_open", "a", 1)
            opening.attrSet("href", href)
            out.extend([opening, _text(url), Token("link_close", "a", -1)])
            start = end
        if start < len(text):
            out.append(_text(text[start:]))
    inline.children = out


def _text(content: str) -> Token:
    token = Token("text", "", 0)
    token.content = content
    return token


def _site_rules(md: MarkdownIt):
    def rule(state):
        tokens, out, index = state.tokens, [], 0
        while index < len(tokens):
            token = tokens[index]
            if token.type in ("heading_open", "heading_close"):
                token.tag = HEADING_TAGS.get(token.tag, token.tag)
            if (
                token.type == "paragraph_open"
                and not token.hidden
                and index + 2 < len(tokens)
                and tokens[index + 1].type == "inline"
                and tokens[index + 2].type == "paragraph_close"
            ):
                block = _standalone(tokens[index + 1], md, state.env)
                if block is not None:
                    out.append(block)
                    index += 3
                    continue
            if token.type == "inline":
                _link_bare_urls(token, md)
            out.append(token)
            index += 1
        state.tokens = _attributions(out)

    return rule


def _attributions(tokens: list[Token]) -> list[Token]:
    """A quote's last line starting with 「——」 is its source, set right
    under the quote as before (design-details 6.4)."""
    out: list[Token] = []
    for token in tokens:
        if token.type == "blockquote_close" and len(out) >= 3:
            opening, inline, closing = out[-3], out[-2], out[-1]
            if (
                opening.type == "paragraph_open"
                and inline.type == "inline"
                and closing.type == "paragraph_close"
            ):
                children = inline.children or []
                breaks = [
                    number
                    for number, child in enumerate(children)
                    if child.type in ("softbreak", "hardbreak")
                ]
                start = breaks[-1] + 1 if breaks else 0
                tail = children[start:]
                source = "".join(child.content for child in tail).strip()
                if (
                    source.startswith("——")
                    and tail
                    and all(child.type == "text" for child in tail)
                ):
                    footer = _html_block(f"<footer>{escape(source)}</footer>\n")
                    if breaks:
                        inline.children = children[: breaks[-1]]
                        out.append(footer)
                    else:
                        out[-3:] = [footer]
        out.append(token)
    return out


def _render_image(self, tokens, index, options, env):
    """An image inside running text: this site's as a small image, anyone
    else's as a link to it."""
    token = tokens[index]
    src = token.attrGet("src") or ""
    alt = self.renderInlineAsText(token.children or [], options, env)
    if own_image(src):
        env["images"] = env.get("images", 0) + 1
        return f'<img src="{escape(src)}" alt="{escape(alt)}" loading="lazy">'
    if urlparse(src).scheme in ("http", "https"):
        return f'<a href="{escape(src)}">{escape(alt or "图片")}</a>'
    return escape(alt)


def _render_table_open(self, tokens, index, options, env):
    return '<div class="c-prose__table">' + self.renderToken(
        tokens, index, options, env
    )


def _render_table_close(self, tokens, index, options, env):
    return self.renderToken(tokens, index, options, env) + "</div>\n"


@lru_cache(maxsize=1)
def parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False, "breaks": True})
    md.enable(["table", "strikethrough"])
    md.core.ruler.push("site_rules", _site_rules(md))
    md.add_render_rule("image", _render_image)
    md.add_render_rule("table_open", _render_table_open)
    md.add_render_rule("table_close", _render_table_close)
    return md


def analyse(source: str | None) -> Rendered:
    env: dict = {}
    output = parser().render(source or "", env)
    return Rendered(mark_safe(output), env.get("images", 0), env.get("videos", 0))


def render(source: str | None) -> SafeString:
    return analyse(source).html


def plain_html(rendered_html: str) -> str:
    """The words a reader sees, from rendered HTML (counts, search, review)."""
    text = html.unescape(strip_tags(str(rendered_html)))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def plain_text(source: str | None) -> str:
    """The words a reader sees, no markup: for counts, search and review."""
    return plain_html(render(source))
