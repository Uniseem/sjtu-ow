"""Public content pages that get prerendered (design 13.13.1)."""

from __future__ import annotations


def content_targets() -> dict:
    from content.models import ArticleIndexPage, ArticlePage, HomePage, StandardPage

    kinds = (
        (HomePage, "home"),
        (ArticleIndexPage, "article_index"),
        (ArticlePage, "article"),
        (StandardPage, "standard"),
    )
    targets = {}
    for model, kind in kinds:
        for page in model.objects.live().public().specific():
            url = page.get_url()
            if url:
                targets[url] = kind
    return targets
