"""Render public pages to static files for Caddy to serve (design 13.13)."""

from __future__ import annotations

import gzip
import hashlib
import logging
import os
import re
import secrets
import shutil
from pathlib import Path

import brotli
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

INDEX_FILE = "index.html"
# Marks the generator's own request so the fallback middleware ignores it.
PRERENDER_HEADER = "x-prerender"
PATHS_CACHE_KEY = "sjtu_ow:prerender_paths"
PATHS_CACHE_SECONDS = 60
COALESCE_SECONDS = 30

# A prerendered page is served to everyone, so it must never carry these.
SECRET_MARKERS = (
    "csrfmiddlewaretoken",
    "csrf_token",
    "sessionid",
)


class PrerenderError(Exception):
    """The page could not be rendered or is not safe to publish."""


class PageGone(PrerenderError):
    """The page is no longer public, so it should not exist as a file."""


def is_enabled() -> bool:
    return bool(getattr(settings, "PRERENDER_ENABLED", False))


def root() -> Path:
    return Path(settings.PRERENDER_ROOT)


def normalize_path(path: str) -> str:
    """Public paths always look like ``/`` or ``/news/slug/``."""
    if not path.startswith("/"):
        raise PrerenderError(f"路径必须以 / 开头：{path}")
    if "?" in path or "#" in path:
        raise PrerenderError(f"预渲染路径不能带查询参数：{path}")
    if ".." in path or "//" in path:
        raise PrerenderError(f"路径不合法：{path}")
    if not path.endswith("/"):
        path += "/"
    return path


def file_for(path: str) -> Path:
    relative = normalize_path(path).strip("/")
    directory = root() / relative if relative else root()
    return directory / INDEX_FILE


def site_host() -> tuple[str, bool]:
    """Host and https flag to render with, taken from the Wagtail site."""
    from wagtail.models import Site

    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        return "localhost", False
    return site.hostname, site.port == 443


TARGET_PROVIDERS = []


def register_targets(provider) -> None:
    """Apps add their own public pages in ``AppConfig.ready()``."""
    if provider not in TARGET_PROVIDERS:
        TARGET_PROVIDERS.append(provider)


def page_targets() -> dict[str, str]:
    """Every public page that should exist as a static file: path -> kind."""
    targets: dict[str, str] = {}
    for provider in TARGET_PROVIDERS:
        for path, kind in provider().items():
            try:
                targets[normalize_path(path)] = kind
            except PrerenderError:
                logger.warning("跳过不合法的预渲染路径 %s", path)
    targets.setdefault("/", "home")
    return targets


def cached_targets() -> dict[str, str]:
    targets = cache.get(PATHS_CACHE_KEY)
    if targets is None:
        targets = page_targets()
        cache.set(PATHS_CACHE_KEY, targets, PATHS_CACHE_SECONDS)
    return targets


def forget_targets() -> None:
    cache.delete(PATHS_CACHE_KEY)


# (mtime, size) of the static manifest this process last read.
_manifest_seen: tuple[int, int] | None = None


def refresh_static_manifest() -> bool:
    """Re-read collectstatic's manifest if it changed on disk (round 064).

    Django's manifest storage reads the file once per process. On an upgrade
    the worker starts alongside ``web``, which runs collectstatic only on
    start-up; a page the worker rendered in between would load the previous
    version's manifest and keep pointing at the old CSS until the worker
    restarts. Returns True when the storage was reset.
    """
    global _manifest_seen
    from django.contrib.staticfiles.storage import (
        ManifestFilesMixin,
        staticfiles_storage,
    )

    if not isinstance(staticfiles_storage, ManifestFilesMixin):
        return False
    storage = staticfiles_storage
    try:
        stat = os.stat(storage.manifest_storage.path(storage.manifest_name))
        seen = (stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        seen = None
    if seen is not None and seen == _manifest_seen:
        return False
    # The instance is cached by django.core.files.storage.storages, so reload
    # in place the way ManifestFilesMixin.__init__ does.
    storage.hashed_files, storage.manifest_hash = storage.load_manifest()
    _manifest_seen = seen
    return True


def render_html(path: str) -> bytes:
    """Render as an anonymous visitor, then refuse anything personal."""
    from django.test import Client

    refresh_static_manifest()
    host, secure = site_host()
    client = Client(
        SERVER_NAME=host,
        raise_request_exception=False,
        headers={PRERENDER_HEADER: "1"},
    )
    try:
        response = client.get(path, secure=secure)
    except Exception as exc:  # noqa: BLE001 — the reason goes into the record
        raise PrerenderError(f"渲染出错：{exc}") from exc

    if response.status_code in (404, 410):
        raise PageGone(f"页面返回 {response.status_code}，已不再公开")
    if response.status_code != 200:
        raise PrerenderError(f"页面返回 {response.status_code}，不生成静态文件")
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        raise PrerenderError(f"不是 HTML 响应（{content_type}）")
    if response.cookies:
        names = "、".join(sorted(response.cookies))
        raise PrerenderError(f"响应带 Cookie（{names}），拒绝写入静态文件")
    html = response.content
    text = html.decode("utf-8", "ignore")
    for marker in SECRET_MARKERS:
        if marker in text:
            raise PrerenderError(f"页面里出现「{marker}」，拒绝写入静态文件")
    return html


def _atomic_write(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp-{secrets.token_hex(4)}")
    tmp.write_bytes(payload)
    os.replace(tmp, target)


def write_page(path: str, html: bytes) -> None:
    """Write index.html plus its precompressed twins, atomically."""
    target = file_for(path)
    _atomic_write(target, html)
    _atomic_write(target.with_suffix(".html.br"), brotli.compress(html, quality=11))
    _atomic_write(
        target.with_suffix(".html.gz"),
        gzip.compress(html, compresslevel=9, mtime=0),
    )


def remove_page(path: str) -> bool:
    """Delete a page's static files. Returns True if anything was removed."""
    target = file_for(path)
    removed = False
    candidates = (
        target,
        target.with_suffix(".html.br"),
        target.with_suffix(".html.gz"),
    )
    for candidate in candidates:
        if candidate.exists():
            candidate.unlink()
            removed = True
    directory = target.parent
    while directory != root() and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent
    return removed


def generate(path: str, kind: str = ""):
    """Render one page and store the result. Returns the PrerenderedPage row."""
    from core.models import PrerenderedPage

    path = normalize_path(path)
    record, _created = PrerenderedPage.objects.get_or_create(
        path=path,
        defaults={"kind": kind or cached_targets().get(path, "page")},
    )
    if kind and record.kind != kind:
        record.kind = kind
    try:
        html = render_html(path)
    except PageGone:
        # Unpublished or renamed in the meantime: drop it instead of logging a
        # failure the admin would have to look at.
        drop(path)
        record.status = PrerenderedPage.Status.FAILED
        record.error = "页面已不再公开，静态文件已删除"
        return record
    except PrerenderError as exc:
        record.status = PrerenderedPage.Status.FAILED
        record.error = str(exc)
        record.requested_at = None
        record.save(update_fields=["kind", "status", "error", "requested_at"])
        logger.warning("预渲染失败 %s：%s", path, exc)
        return record

    digest = hashlib.sha256(html).hexdigest()
    if digest != record.content_hash or not file_for(path).exists():
        write_page(path, html)
    record.status = PrerenderedPage.Status.READY
    record.content_hash = digest
    record.bytes = len(html)
    record.error = ""
    record.generated_at = timezone.now()
    record.requested_at = None
    record.save()
    return record


def drop(path: str) -> bool:
    """Remove a page from disk and from the record table."""
    from core.models import PrerenderedPage

    path = normalize_path(path)
    removed = remove_page(path)
    PrerenderedPage.objects.filter(path=path).delete()
    forget_targets()
    return removed


def generate_all() -> dict:
    """Rebuild every public page and drop the ones that are gone."""
    from core.models import PrerenderedPage

    forget_targets()
    targets = page_targets()
    stats = {"generated": 0, "failed": 0, "removed": 0}
    for path, kind in targets.items():
        record = generate(path, kind=kind)
        if record.status == PrerenderedPage.Status.READY:
            stats["generated"] += 1
        else:
            stats["failed"] += 1
    for record in PrerenderedPage.objects.exclude(path__in=targets):
        remove_page(record.path)
        record.delete()
        stats["removed"] += 1
    return stats


def clear_all() -> int:
    """Delete every static file; the site falls back to live rendering."""
    from core.models import PrerenderedPage

    count = PrerenderedPage.objects.count()
    if root().exists():
        for child in root().iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    PrerenderedPage.objects.all().update(
        status=PrerenderedPage.Status.PENDING,
        content_hash="",
        generated_at=None,
    )
    return count


def disk_usage() -> int:
    if not root().exists():
        return 0
    return sum(item.stat().st_size for item in root().rglob("*") if item.is_file())


UNSAFE_CHARS = re.compile(r"[\x00-\x1f\x7f\\]")


def looks_prerenderable(path: str) -> bool:
    """Cheap sanity check before touching the filesystem. Unicode slugs are fine."""
    if not path.startswith("/") or ".." in path or "//" in path:
        return False
    return not UNSAFE_CHARS.search(path)


def request_page(path: str, kind: str = "") -> bool:
    """Ask for one page to be regenerated, merging requests 30 seconds apart."""
    from datetime import timedelta

    from django.db import transaction

    from core.models import PrerenderedPage
    from core.tasks import prerender_page

    if not is_enabled():
        return False
    try:
        path = normalize_path(path)
    except PrerenderError:
        logger.warning("跳过不合法的预渲染路径 %s", path)
        return False

    now = timezone.now()
    record, created = PrerenderedPage.objects.get_or_create(
        path=path,
        defaults={
            "kind": kind or cached_targets().get(path, "page"),
            "requested_at": now,
        },
    )
    if not created:
        pending = record.requested_at and (
            (now - record.requested_at).total_seconds() < COALESCE_SECONDS
        )
        PrerenderedPage.objects.filter(pk=record.pk).update(
            requested_at=now,
            kind=kind or record.kind,
        )
        if pending:
            return False  # an earlier request is already scheduled

    run_after = now + timedelta(seconds=COALESCE_SECONDS)
    transaction.on_commit(
        lambda: prerender_page.using(run_after=run_after).enqueue(path)
    )
    return True


def request_removal(path: str) -> None:
    """Content just went private: delete the static file right away."""
    from django.db import transaction

    from core.tasks import remove_prerendered

    if not is_enabled():
        return
    transaction.on_commit(lambda: remove_prerendered.enqueue(path))


def request_all() -> None:
    from django.db import transaction

    from core.tasks import prerender_all

    if not is_enabled():
        return
    transaction.on_commit(lambda: prerender_all.enqueue())
