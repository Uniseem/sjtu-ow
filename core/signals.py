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
