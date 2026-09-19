import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import (
    BATTLTAG_TAKEN,
    ContactMethod,
    ContactType,
    Feature,
    FeatureGroupRestriction,
    FeatureUserRule,
    User,
    validate_battletag,
    validate_contact_value,
)
from accounts.permissions import FEATURE_DENIED_MESSAGE, can_use, feature_denied_message
from accounts.services import (
    add_game_account,
    max_game_accounts,
    profile_gaps,
    profile_is_complete,
)


def _user(email="player@example.com", **kwargs):
    kwargs.setdefault("nickname", "玩家甲")
    kwargs.setdefault("password", "Correct-Horse-Battery-1")
    kwargs.setdefault("agreed_terms_at", timezone.now())
    kwargs.setdefault("agreed_cross_border_at", timezone.now())
    return User.objects.create_user(email=email, **kwargs)


@pytest.mark.django_db
def test_battletag_format_rules():
    validate_battletag("Ab#1234")
    validate_battletag("名称名称名称#123456")
    with pytest.raises(ValidationError):
        validate_battletag("A#1234")
    with pytest.raises(ValidationError):
        validate_battletag("Has space#1234")
    with pytest.raises(ValidationError):
        validate_battletag("Hash#Hash#1234")
    with pytest.raises(ValidationError):
        validate_battletag("Name#12")
    with pytest.raises(ValidationError):
        validate_battletag("Name#1234567")


@pytest.mark.django_db
def test_battletag_is_case_insensitive_unique():
    owner = _user()
    other = _user(email="other@example.com", nickname="玩家乙")
    add_game_account(owner, battletag="Tank#1234")
    with pytest.raises(ValidationError) as exc:
        add_game_account(other, battletag="tank#1234")
    assert BATTLTAG_TAKEN in exc.value.messages


@pytest.mark.django_db
def test_game_account_max_from_site_settings():
    user = _user()
    limit = max_game_accounts()
    for i in range(limit):
        add_game_account(user, battletag=f"Player#{1000 + i}")
    with pytest.raises(ValidationError):
        add_game_account(user, battletag="Player#1999")
    assert user.game_accounts.count() == limit


@pytest.mark.parametrize(
    ("contact_type", "value", "ok"),
    [
        (ContactType.QQ, "12345", True),
        (ContactType.QQ, "12345678901", True),
        (ContactType.QQ, "1234", False),
        (ContactType.WECHAT, "wxid_ab", True),
        (ContactType.WECHAT, "short", False),
        (ContactType.PHONE, "13800138000", True),
        (ContactType.PHONE, "23800138000", False),
        (ContactType.PHONE, "1380013800", False),
        (ContactType.OTHER, "discord:player", True),
        (ContactType.OTHER, "x" * 65, False),
    ],
)
def test_contact_value_validators(contact_type, value, ok):
    if ok:
        validate_contact_value(contact_type, value)
    else:
        with pytest.raises(ValidationError):
            validate_contact_value(contact_type, value)


@pytest.mark.django_db
def test_contact_type_unique_per_user():
    user = _user()
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456")
    contact = ContactMethod(user=user, type=ContactType.QQ, value="654321")
    with pytest.raises(ValidationError):
        contact.full_clean()


@pytest.mark.django_db
def test_profile_completeness_requires_game_id_and_contact():
    user = _user()
    gaps = {item[0] for item in profile_gaps(user)}
    assert gaps == {"游戏 ID", "联系方式"}
    assert profile_is_complete(user) is False
    add_game_account(user, battletag="Comp#1000")
    gaps = {item[0] for item in profile_gaps(user)}
    assert gaps == {"联系方式"}
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456")
    assert profile_gaps(user) == []
    assert profile_is_complete(user) is True


@pytest.mark.django_db
def test_can_use_user_rule_then_group_then_default():
    user = _user()
    group = Group.objects.create(name="违规观察名单")
    user.groups.add(group)
    feature = Feature.TOURNAMENT_REGISTER
    assert can_use(user, feature) is True
    FeatureGroupRestriction.objects.create(group=group, feature=feature)
    assert can_use(user, feature) is False
    FeatureUserRule.objects.create(user=user, feature=feature, allowed=True)
    assert can_use(user, feature) is True
    FeatureUserRule.objects.filter(user=user, feature=feature).update(allowed=False)
    assert can_use(user, feature) is False
    assert feature_denied_message(feature) == FEATURE_DENIED_MESSAGE
    assert "原因" not in feature_denied_message(feature)


@pytest.mark.django_db
def test_can_use_inactive_and_anonymous():
    user = _user()
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert can_use(user, Feature.TEAM_CREATE) is False
    assert can_use(None, Feature.TEAM_CREATE) is False


@pytest.mark.django_db
def test_game_account_ranks_updated_at_changes_with_ranks():
    user = _user()
    account = add_game_account(user, battletag="Rank#1000", rank_tank=22)
    first = account.ranks_updated_at
    account.battletag = "Rank#1001"
    account.save()
    account.refresh_from_db()
    assert account.ranks_updated_at == first
    account.rank_damage = 10
    account.save()
    account.refresh_from_db()
    assert account.ranks_updated_at >= first


@pytest.mark.django_db
def test_can_use_rejects_an_unknown_feature_name():
    """A misspelt feature would otherwise fall through to the default allow."""
    user = _user()
    with pytest.raises(ValueError, match="Unknown feature"):
        can_use(user, "tournament_regsiter")
