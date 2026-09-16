"""Feature gates (design 4.3). Not Django's grant-only permission system."""

from __future__ import annotations

from accounts.models import Feature, FeatureGroupRestriction, FeatureUserRule

FEATURE_DENIED_MESSAGE = "你暂时无法使用此功能，如有疑问请联系管理员"


def feature_denied_message(_feature: str | None = None) -> str:
    """Front-end copy when a feature is blocked. Reason is never shown."""
    return FEATURE_DENIED_MESSAGE


def can_use(user, feature: str) -> bool:
    """Single-user rule, then any group restriction, then default allow."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if not user.is_active:
        return False
    if feature not in Feature.values:
        raise ValueError(f"Unknown feature: {feature}")
    rule = FeatureUserRule.objects.filter(user=user, feature=feature).first()
    if rule is not None:
        return bool(rule.allowed)
    if FeatureGroupRestriction.objects.filter(
        group__in=user.groups.all(), feature=feature
    ).exists():
        return False
    return True
