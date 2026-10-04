"""Turn the bodies written before v6.70 into Markdown (design 5.2).

Until then article and page bodies were StreamFields (rich-text paragraphs,
images, quotes, Bilibili videos) and tournament descriptions rich text, both
in Wagtail's stored HTML. The migrations that switched them to Markdown call
this, so it stays while they do.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from html.parser import HTMLParser

# Characters that would turn into markup; escaped wherever they appear in text.
_INLINE_SPECIAL = re.compile(r"([\\`*_\[\]<>~|])")
# What would start a block at the beginning of a line.
_BLOCK_START = re.compile(r"^(\s*)(#{1,6}\s|>|[-+]\s|\d+[.)]\s)")

LinkFor = Callable[[dict], str]


def _escape(text: str) -> str:
    return _INLINE_SPECIAL.sub(r"\\\1", text)


def _escape_line_start(line: str) -> str:
    match = _BLOCK_START.match(line)
    if not match:
        return line
    head = match.group(2)
    if head[0].isdigit():
        number = re.match(r"\d+", head).group(0)
        return f"{match.group(1)}{number}\\{head[len(number) :]}{line[match.end() :]}"
    return f"{match.group(1)}\\{head}{line[match.end() :]}"


class _ToMarkdown(HTMLParser):
    """Wagtail's stored rich text (p, h2–h4, b, i, a, ol/ul/li, br, hr,
    image embeds) as Markdown blocks."""

    def __init__(self, link_for: LinkFor, image_for: LinkFor):
        super().__init__(convert_charrefs=True)
        self.link_for, self.image_for = link_for, image_for
        self.blocks: list[str] = []
        self.line: list[str] = []
        self.prefix = ""
        self.lists: list[list] = []  # [tag, counter, marker width]
        self.links: list[str] = []

    def _flush(self):
        raw = "".join(self.line)
        self.line = []
        if not raw.strip():
            return
        if self.lists:
            # A line break inside an item continues under its text.
            indent = " " * (len(raw) - len(raw.lstrip(" ")) + self.lists[-1][2])
            lines = raw.strip("\n").rstrip().split("\n")
            self.blocks.append(
                f"\n{indent}".join(
                    line.strip() if number else line
                    for number, line in enumerate(lines)
                )
            )
            return
        text = raw.strip()
        lines = [_escape_line_start(part) for part in text.split("\n")]
        self.blocks.append(self.prefix + "\n".join(lines))
        self.prefix = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("p", "div"):
            self._flush()
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self.prefix = "## " if tag in ("h1", "h2") else "### "
        elif tag in ("b", "strong"):
            self.line.append("**")
        elif tag in ("i", "em"):
            self.line.append("*")
        elif tag == "code":
            self.line.append("`")
        elif tag == "br":
            self.line.append("\n")
        elif tag == "hr":
            self._flush()
            self.blocks.append("---")
        elif tag in ("ul", "ol"):
            self._flush()
            self.lists.append([tag, 0, 0])
        elif tag == "li" and self.lists:
            self._flush()
            current = self.lists[-1]
            current[1] += 1
            # Nested items start under their parent's text (CommonMark).
            indent = " " * sum(parent[2] for parent in self.lists[:-1])
            marker = f"{current[1]}." if current[0] == "ol" else "-"
            current[2] = len(marker) + 1
            self.line.append(f"{indent}{marker} ")
        elif tag == "a":
            href = attrs.get("href") or (
                self.link_for(attrs) if attrs.get("linktype") else ""
            )
            self.links.append(href or "")
            if href:
                self.line.append("[")
        elif tag == "embed" and attrs.get("embedtype") == "image":
            src = self.image_for({"id": attrs.get("id")})
            if src:
                alt = attrs.get("alt", "")
                self._flush()
                self.blocks.append(f"![{_escape(alt)}]({src})")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("p", "div", "li"):
            self._flush()
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self.prefix = ""
        elif tag in ("b", "strong"):
            self.line.append("**")
        elif tag in ("i", "em"):
            self.line.append("*")
        elif tag == "code":
            self.line.append("`")
        elif tag in ("ul", "ol") and self.lists:
            self._flush()
            self.lists.pop()
            if not self.lists:
                self.blocks.append("")  # a list ends with a blank line
        elif tag == "a" and self.links:
            href = self.links.pop()
            if href:
                self.line.append(f"]({href})")

    def handle_data(self, data):
        data = data.replace("\r", "")
        if not data.strip() and "\n" in data:
            return  # layout between tags, not text
        self.line.append(_escape(data.replace("\n", " ")))

    def markdown(self) -> str:
        self._flush()
        out, previous_item = [], False
        for block in self.blocks:
            if block == "":
                previous_item = False
                continue
            item = bool(re.match(r"\s*(-|\d+\.)\s", block)) and not block.startswith(
                ("## ", "### ")
            )
            if out:
                out.append("\n" if item and previous_item else "\n\n")
            out.append(block)
            previous_item = item
        return "".join(out).strip()


def no_link(_attrs: dict) -> str:
    return ""


def from_html(
    html: str, link_for: LinkFor = no_link, image_for: LinkFor = no_link
) -> str:
    parser = _ToMarkdown(link_for, image_for)
    parser.feed(html or "")
    parser.close()
    return parser.markdown()


def from_stream(raw, link_for: LinkFor = no_link, image_for: LinkFor = no_link) -> str:
    """A StreamField's raw data (a list, or the JSON a revision keeps)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else []
        except ValueError:
            return raw  # already text
    parts = []
    for block in raw or []:
        kind, value = block.get("type"), block.get("value")
        if kind == "paragraph":
            text = from_html(value or "", link_for, image_for)
        elif kind == "image":
            value = value or {}
            src = image_for({"id": value.get("image")})
            caption = _escape(value.get("caption") or "")
            text = f"![{caption}]({src})" if src else ""
        elif kind == "quote":
            value = value or {}
            lines = [_escape(line) for line in (value.get("text") or "").splitlines()]
            if value.get("attribution"):
                lines.append("——" + _escape(value["attribution"]))
            text = "\n".join(f"> {line}" if line else ">" for line in lines)
        elif kind == "video":
            text = (value or "").strip() if isinstance(value, str) else ""
        else:
            text = ""
        if text:
            parts.append(text)
    return "\n\n".join(parts)
