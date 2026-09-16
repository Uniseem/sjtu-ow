"""Keep only safe tags in upstream-supplied HTML (design 11.6.3).

A tiny allowlist parser: the upstream sends 段落、标题、列表、加粗、斜体、链接,
everything else is dropped. No new dependency for something this small.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

ALLOWED_TAGS = {
    "p",
    "br",
    "h2",
    "h3",
    "h4",
    "ul",
    "ol",
    "li",
    "b",
    "strong",
    "i",
    "em",
    "a",
    "hr",
}
VOID_TAGS = {"br", "hr"}
ALLOWED_ATTRS = {"a": {"href", "title"}}
ALLOWED_SCHEMES = {"http", "https", "mailto"}
# Their text is dropped as well, not just the tags.
DROP_CONTENT_TAGS = {"script", "style", "template"}


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth or tag not in ALLOWED_TAGS:
            return
        allowed = ALLOWED_ATTRS.get(tag, set())
        rendered = []
        for name, value in attrs:
            if name not in allowed or value is None:
                continue
            if name == "href" and not self._safe_url(value):
                continue
            rendered.append(f' {name}="{escape(value, quote=True)}"')
        if tag in VOID_TAGS:
            self.parts.append(f"<{tag}{''.join(rendered)}>")
            return
        self.open_tags.append(tag)
        self.parts.append(f"<{tag}{''.join(rendered)}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag in self.open_tags:
            while self.open_tags:
                open_tag = self.open_tags.pop()
                self.parts.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data):
        if self.skip_depth:
            return
        self.parts.append(escape(data, quote=False))

    @staticmethod
    def _safe_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        if not parsed.scheme:
            return not value.strip().lower().startswith("javascript:")
        return parsed.scheme.lower() in ALLOWED_SCHEMES

    def result(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def clean_html(value: str) -> str:
    if not value:
        return ""
    parser = _Sanitizer()
    parser.feed(value)
    parser.close()
    return parser.result()
