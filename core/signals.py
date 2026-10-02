"""Regenerate the homepage when the settings it prints change (design 13.13.4)."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.models import SiteSettings

HOMEPAGE_FIELDS = ("founded_on", "qq_group_url", "hero_image_id")


@receiver(pre_save, sender=SiteSettings)
def remember_homepage_fields(sender, instance, raw=False, **kwargs):
    instance._homepage_before = None
    if raw or instance.pk is None:
        return
    instance._homepage_before = (
        SiteSettings.objects.filter(pk=instance.pk).values(*HOMEPAGE_FIELDS).first()
    )


@receiver(post_save, sender=SiteSettings)
def homepage_fields_changed(sender, instance, created, raw=False, **kwargs):
    """社区成立日期, QQ 群链接 and 首屏图片 appear on the prerendered homepage (5.2)."""
    if raw:
        return
    before = getattr(instance, "_homepage_before", None)
    now = {field: getattr(instance, field) for field in HOMEPAGE_FIELDS}
    if before is not None and before == now:
        return
    if created and not any(now.values()):
        return
    from core import prerender

    prerender.request_page("/", kind="home")


# The 栏目横幅 (v5.0) sit on these prerendered pages (13.13.4).
BANNER_PAGES = {
    "banner_tournaments_id": ("/tournaments/", "tournament_index"),
    "banner_scrims_id": ("/scrims/", "scrim_index"),
    "banner_teams_id": ("/teams/", "team_index"),
    "banner_members_id": ("/members/", "members"),
}


@receiver(pre_save, sender=SiteSettings)
def remember_banners(sender, instance, raw=False, **kwargs):
    instance._banners_before = None
    if raw or instance.pk is None:
        return
    instance._banners_before = (
        SiteSettings.objects.filter(pk=instance.pk)
        .values("banner_news_id", *BANNER_PAGES)
        .first()
    )


@receiver(post_save, sender=SiteSettings)
def banners_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    before = getattr(instance, "_banners_before", None) or {}
    from core import prerender

    for field, (path, kind) in BANNER_PAGES.items():
        if before.get(field) != getattr(instance, field):
            prerender.request_page(path, kind=kind)
    if before.get("banner_news_id") != instance.banner_news_id:
        # The news section is a Wagtail page; its address comes from the tree.
        from content.services import first_article_index

        index = first_article_index()
        url = index.url if index else None
        if url:
            prerender.request_page(url, kind="article_index")
