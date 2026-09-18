"""Game modes are printed in the LFG shell's filter bar (design 13.13.4)."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from core.models import GameMode


@receiver(post_save, sender=GameMode)
@receiver(post_delete, sender=GameMode)
def refresh_lfg_shell(sender, instance, **kwargs):
    from core import prerender

    prerender.request_page("/lfg/", kind="lfg_shell")
