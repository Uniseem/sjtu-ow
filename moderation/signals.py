"""Hook content into the review queue (design 5.5.1)."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from wagtail.signals import page_published, workflow_submitted

from accounts.models import User
from moderation import integrations


@receiver(post_save, sender=User)
def on_user_saved(sender, instance, **kwargs):
    """Nicknames are public the moment they are set (design 5.5.1)."""
    integrations.submit_nickname(instance)


@receiver(page_published)
def on_page_published(sender, instance, **kwargs):
    integrations.submit_page(instance)


@receiver(workflow_submitted)
def on_workflow_submitted(sender, instance, **kwargs):
    """A submission entering review: the AI's read is shown to the editor."""
    page = getattr(instance, "content_object", None)
    if page is not None:
        integrations.submit_page(page)
