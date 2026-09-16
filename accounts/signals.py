from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule, User
from accounts.services import (
    sync_sjtu_groups,
    sync_submitter_group,
    sync_submitters_for_group,
)


@receiver(post_save, sender=User)
def sync_groups_when_user_saved(sender, instance, raw, **kwargs):
    if raw:
        return
    sync_sjtu_groups(instance)
    sync_submitter_group(instance)


@receiver(m2m_changed, sender=User.groups.through)
def sync_submitter_when_groups_change(sender, instance, action, pk_set, **kwargs):
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if isinstance(instance, User):
        sync_submitter_group(instance)
        return
    if pk_set:
        for user in User.objects.filter(pk__in=pk_set):
            sync_submitter_group(user)


def _sync_article_submit_restriction(instance: FeatureGroupRestriction) -> None:
    if instance.feature != Feature.ARTICLE_SUBMIT:
        return
    if instance.group_id:
        sync_submitters_for_group(instance.group)


@receiver(post_save, sender=FeatureGroupRestriction)
def sync_submitter_when_group_restriction_saved(sender, instance, raw, **kwargs):
    if raw:
        return
    _sync_article_submit_restriction(instance)


@receiver(post_delete, sender=FeatureGroupRestriction)
def sync_submitter_when_group_restriction_deleted(sender, instance, **kwargs):
    _sync_article_submit_restriction(instance)


@receiver(post_save, sender=FeatureUserRule)
def sync_submitter_when_user_rule_saved(sender, instance, raw, **kwargs):
    if raw or instance.feature != Feature.ARTICLE_SUBMIT:
        return
    if instance.user_id:
        sync_submitter_group(instance.user)


@receiver(post_delete, sender=FeatureUserRule)
def sync_submitter_when_user_rule_deleted(sender, instance, **kwargs):
    if instance.feature != Feature.ARTICLE_SUBMIT:
        return
    if instance.user_id:
        sync_submitter_group(instance.user)


@receiver(email_confirmed, dispatch_uid="accounts_submitter_email_confirmed")
def sync_submitter_when_email_confirmed(request, email_address, **kwargs):
    sync_submitter_group(email_address.user)


@receiver(post_save, sender=EmailAddress)
def sync_submitter_when_emailaddress_saved(sender, instance, raw, **kwargs):
    if raw or instance.user_id is None:
        return
    sync_submitter_group(instance.user)
