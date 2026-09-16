from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User
from accounts.services import sync_sjtu_groups


@receiver(post_save, sender=User)
def sync_groups_when_user_saved(sender, instance, raw, **kwargs):
    if raw:
        return
    sync_sjtu_groups(instance)
