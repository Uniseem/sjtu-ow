"""Download fonts from a URL or from Google Fonts (design 13.12.1)."""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from core.fonts.processing import MAX_FONT_BYTES, FontError, slice_storage_dir

GOOGLE_CSS_URL = "https://fonts.googleapis.com/css2"
GOOGLE_FONT_HOSTS = {"fonts.gstatic.com"}
# Google serves woff2 with unicode-range slices only to modern browsers.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DOWNLOAD_TIMEOUT = 30


class DownloadError(FontError):
    """The font could not be downloaded."""


def _assert_public_url(url: str) -> None:
    from core.net import UnsafeUrl, assert_public_https_url

    try:
        assert_public_https_url(url)
    except UnsafeUrl as exc:
        raise DownloadError(f"下载地址不可用：{exc}") from exc


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _assert_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_SafeRedirectHandler)


def fetch_bytes(url: str, *, max_bytes: int = MAX_FONT_BYTES) -> bytes:
    """Fetch a URL over https, refusing internal addresses and huge bodies."""
    _assert_public_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_USER_AGENT})
    try:
        with _opener.open(request, timeout=DOWNLOAD_TIMEOUT) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > max_bytes:
                raise DownloadError(
                    f"文件 {int(declared) / 1024 / 1024:.1f}MB，超过 "
                    f"{max_bytes // 1024 // 1024}MB 上限。"
                )
            data = response.read(max_bytes + 1)
    except urllib.error.URLError as exc:
        raise DownloadError(f"下载失败：{exc.reason}") from exc
    except OSError as exc:
        raise DownloadError(f"下载失败：{exc}") from exc
    if len(data) > max_bytes:
        raise DownloadError(f"文件超过 {max_bytes // 1024 // 1024}MB 上限。")
    if not data:
        raise DownloadError("下载到的文件是空的。")
    return data


def filename_from_url(url: str) -> str:
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:100]
    return name or "font.ttf"


def google_css_url(family: str, weights) -> str:
    axis = ";".join(str(weight) for weight in sorted(set(weights)))
    query = urllib.parse.urlencode(
        {"family": f"{family}:wght@{axis}", "display": "swap"},
        safe=":;@",
    )
    return f"{GOOGLE_CSS_URL}?{query}"


def fetch_google_css(family: str, weights) -> str:
    url = google_css_url(family, weights)
    _assert_public_url(url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": BROWSER_USER_AGENT},
    )
    try:
        with _opener.open(request, timeout=DOWNLOAD_TIMEOUT) as response:
            return response.read(2 * 1024 * 1024).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 400:
            raise DownloadError(
                f"Google Fonts 没有「{family}」这个字体，或者它没有所选字重。"
            ) from exc
        raise DownloadError(f"访问 Google Fonts 失败：HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"访问 Google Fonts 失败：{exc.reason}") from exc
    except OSError as exc:
        raise DownloadError(f"访问 Google Fonts 失败：{exc}") from exc


_FACE_RE = re.compile(r"@font-face\s*\{(?P<body>[^}]*)\}", re.S)


def _declaration(body: str, name: str) -> str:
    match = re.search(rf"{name}\s*:\s*([^;]+);", body)
    return match.group(1).strip() if match else ""


def parse_google_css(css: str) -> list[dict]:
    """Extract (weight, style, url, unicode-range) from a Google Fonts stylesheet."""
    faces = []
    for match in _FACE_RE.finditer(css):
        body = match.group("body")
        src = _declaration(body, "src")
        url_match = re.search(r"url\(([^)]+)\)", src)
        if not url_match:
            continue
        url = url_match.group(1).strip("'\" ")
        if "format('woff2')" not in src and 'format("woff2")' not in src:
            continue
        host = urllib.parse.urlsplit(url).hostname or ""
        if host not in GOOGLE_FONT_HOSTS:
            raise DownloadError(f"Google Fonts 返回了意外的下载地址：{host}")
        weight = _declaration(body, "font-weight") or "400"
        try:
            weight_value = int(weight.split()[0])
        except ValueError:
            continue
        faces.append(
            {
                "weight": weight_value,
                "style": _declaration(body, "font-style") or "normal",
                "url": url,
                "unicode_range": _declaration(body, "unicode-range"),
            }
        )
    if not faces:
        raise DownloadError("Google Fonts 返回的样式表里没有 woff2 分片。")
    return faces


def download_google_slices(family_id: int, faces: list[dict]) -> dict:
    """Download every Google slice into our own media storage.

    Returns ``{(weight, style): [slice records]}``; Google has already sliced
    these fonts, so they are stored as-is (design 13.12.2 step 5).
    """
    grouped: dict = {}
    for face in faces:
        key = (face["weight"], face["style"])
        payload = fetch_bytes(face["url"])
        digest = hashlib.sha256(payload).hexdigest()[:8]
        grouped.setdefault(key, [])
        # Google serves one variable file for several weights; name slices by
        # content so the same bytes are stored once.
        name = f"{slice_storage_dir(family_id)}/google-{digest}.woff2"
        if not default_storage.exists(name):
            default_storage.save(name, ContentFile(payload))
        grouped[key].append(
            {
                "path": name,
                "unicode_range": face["unicode_range"],
                "bytes": len(payload),
                "chars": 0,
            }
        )
    return grouped
