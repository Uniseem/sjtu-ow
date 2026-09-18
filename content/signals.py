"""Keep the static pages in step with the content (design 13.13.4)."""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from wagtail.models import Page, Site
from wagtail.signals import (
    page_published,
    page_slug_changed,
    page_unpublished,
    post_page_move,
)

from content.models import (
    ArticleCategory,
    ArticleIndexPage,
    ArticlePage,
    HomePage,
    StandardPage,
)
from core import prerender

logger = logging.getLogger(__name__)

PUBLIC_KINDS = {
    HomePage: "home",
    ArticleIndexPage: "article_index",
    ArticlePage: "article",
    StandardPage: "standard",
}


def kind_for(page) -> str:
    specific = page.specific_class or type(page)
    for model, kind in PUBLIC_KINDS.items():
        if issubclass(specific, model):
            return kind
    return ""


def public_url(url_path: str) -> str:
    """Turn Wagtail's internal ``url_path`` into the address visitors use."""
    site = Site.objects.filter(is_default_site=True).first()
    if site is None:
        return ""
    root_path = site.root_page.url_path
    if not url_path.startswith(root_path):
        return ""
    return "/" + url_path[len(root_path) :]


def refresh_related_tournament(page) -> None:
    """An article may be linked to a tournament, whose page lists it (13.13.4)."""
    tournament = getattr(page.specific, "tournament", None)
    if tournament is not None and tournament.is_listed:
        prerender.request_page(tournament.get_absolute_url(), kind="tournament")


def refresh_listings(kind: str) -> None:
    """A published article changes the article index and the homepage too."""
    if kind in {"article", "article_index", "home"}:
        for page in ArticleIndexPage.objects.live().public():
            url = page.get_url()
            if url:
                prerender.request_page(url, kind="article_index")
        prerender.request_page("/", kind="home")


@receiver(page_published)
def on_page_published(sender, instance, **kwargs):
    kind = kind_for(instance)
    if not kind:
        return
    prerender.forget_targets()
    url = instance.get_url()
    if url:
        prerender.request_page(url, kind=kind)
    refresh_listings(kind)
    if kind == "article":
        refresh_related_tournament(instance)


@receiver(page_unpublished)
def on_page_unpublished(sender, instance, **kwargs):
    kind = kind_for(instance)
    if not kind:
        return
    prerender.forget_targets()
    url = instance.get_url() or public_url(instance.url_path)
    if url:
        prerender.request_removal(url)
    refresh_listings(kind)
    if kind == "article":
        refresh_related_tournament(instance)


@receiver(post_delete, sender=Page)
def on_page_deleted(sender, instance, **kwargs):
    kind = kind_for(instance)
    if not kind:
        return
    prerender.forget_targets()
    url = public_url(instance.url_path)
    if url:
        prerender.request_removal(url)
    refresh_listings(kind)


@receiver(page_slug_changed)
def on_slug_changed(sender, instance, instance_before, **kwargs):
    kind = kind_for(instance)
    if not kind:
        return
    prerender.forget_targets()
    old_url = public_url(instance_before.url_path)
    if old_url:
        prerender.request_removal(old_url)
    new_url = instance.get_url()
    if new_url and instance.live:
        prerender.request_page(new_url, kind=kind)
    refresh_listings(kind)
    if kind == "article":
        refresh_related_tournament(instance)


@receiver(post_page_move)
def on_page_moved(sender, instance, url_path_before, url_path_after, **kwargs):
    kind = kind_for(instance)
    if not kind:
        return
    prerender.forget_targets()
    old_url = public_url(url_path_before)
    if old_url:
        prerender.request_removal(old_url)
    new_url = public_url(url_path_after)
    if new_url and instance.live:
        prerender.request_page(new_url, kind=kind)
    refresh_listings(kind)
    if kind == "article":
        refresh_related_tournament(instance)


@receiver(post_save, sender=ArticleCategory)
def on_category_saved(sender, instance, **kwargs):
    """Category names show up on the listing and on every article."""
    refresh_listings("article_index")
    for page in ArticlePage.objects.live().public().filter(category=instance):
        url = page.get_url()
        if url:
            prerender.request_page(url, kind="article")
