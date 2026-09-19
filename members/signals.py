"""Regenerate /members/ when what it shows changes (design 13.13.4)."""

from allauth.account.models import EmailAddress
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from accounts.models import User
from members.models import MemberGroup, MemberGroupMembership
from members.services import refresh_page


@receiver(post_save, sender=MemberGroup)
@receiver(post_delete, sender=MemberGroup)
@receiver(post_save, sender=MemberGroupMembership)
@receiver(post_delete, sender=MemberGroupMembership)
def group_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        refresh_page()


@receiver(post_save, sender=EmailAddress)
@receiver(post_delete, sender=EmailAddress)
def email_changed(sender, instance, raw=False, **kwargs):
    """A verified address is what makes someone 「已加入」 (design 6.1)."""
    if not raw:
        refresh_page()


@receiver(pre_save, sender=User)
def remember_active(sender, instance, raw, update_fields=None, **kwargs):
    instance._active_before = None
    if raw or instance.pk is None:
        return
    if update_fields is not None and "is_active" not in update_fields:
        return  # a login only saves last_login
    instance._active_before = (
        User.objects.filter(pk=instance.pk).values_list("is_active", flat=True).first()
    )


@receiver(post_save, sender=User)
def active_changed(sender, instance, created, raw, **kwargs):
    """Deactivated, reactivated or deleted accounts leave or rejoin the page.

    Nickname changes are handled by accounts.services.refresh_nickname_pages.
    """
    before = getattr(instance, "_active_before", None)
    if raw or created or before is None or before == instance.is_active:
        return
    refresh_page()
