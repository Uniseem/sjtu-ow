"""The motto is public text (docs/design-details.md 3.1, 10; v5.2): it is
reviewed like a nickname, a reviewer can clear it, the pages that print it
are regenerated, and the export carries it."""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import GameAccount, User
from accounts.ranks import encode_rank
from accounts.services import personal_data
from core.models import PrerenderedPage
from moderation import services
from moderation.models import ModerationItem, Risk, TargetType
from moderation.tests.test_moderation import _user, moderation_on  # noqa: F401
from teams import services as team_services
from teams.models import TeamAlumnus


@pytest.fixture
def prerender_on(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path


def _requested():
    return set(PrerenderedPage.objects.values_list("path", flat=True))


@pytest.mark.django_db
def test_a_motto_goes_to_review_and_an_empty_one_does_not(moderation_on):  # noqa: F811
    user = _user()
    user.motto = "推车不停"
    user.save()
    item = ModerationItem.objects.get(target_type=TargetType.MOTTO, target_id=user.pk)
    assert item.excerpt == "推车不停"
    user.motto = ""
    user.save()
    assert ModerationItem.objects.filter(target_type=TargetType.MOTTO).count() == 1


@pytest.mark.django_db
def test_a_reviewer_can_clear_a_motto_and_nothing_else(client, moderation_on):  # noqa: F811
    admin = User.objects.create_superuser(
        email="r@example.com",
        password="Correct-Horse-Battery-1",
        nickname="复核员",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    author = _user("m@example.com", "写宣言的")
    author.motto = "可疑的宣言"
    author.save()
    item = ModerationItem.objects.get(target_type=TargetType.MOTTO)
    services.record(
        item, risk=Risk.MEDIUM, categories=[], reason="疑似", quote="", model="m"
    )
    client.force_login(admin)
    page = client.get(reverse("moderation_detail", args=[item.pk])).content.decode()
    assert 'name="clear_motto"' in page
    client.post(
        reverse("moderation_action", args=[item.pk]),
        {"action": "handled", "clear_motto": "1"},
    )
    author.refresh_from_db()
    assert author.motto == ""
    assert author.nickname == "写宣言的"
    # The box only shows on motto items, and is ignored on others.
    nick = ModerationItem.objects.get(
        target_type=TargetType.NICKNAME, target_id=author.pk
    )
    page = client.get(reverse("moderation_detail", args=[nick.pk])).content.decode()
    assert 'name="clear_motto"' not in page


@pytest.mark.django_db
def test_changing_what_the_cards_print_regenerates_the_member_page(prerender_on):
    user = _user("p@example.com", "公开的")
    PrerenderedPage.objects.all().delete()
    user.save()  # nothing changed
    assert _requested() == set()
    for field, value in (
        ("motto", "开团"),
        ("main_role", "tank"),
        ("flex_roles", "support"),
        ("show_rank", False),
    ):
        PrerenderedPage.objects.all().delete()
        setattr(user, field, value)
        user.save()
        assert "/members/" in _requested(), field


@pytest.mark.django_db
def test_a_new_rank_regenerates_the_pages_unless_it_is_private(prerender_on):
    user = _user("k@example.com", "有段位")
    account = GameAccount.objects.create(user=user, battletag="有段位#1234")
    PrerenderedPage.objects.all().delete()
    account.rank_damage = encode_rank("diamond", 3)
    account.save()
    assert "/members/" in _requested()
    user.show_rank = False
    user.save()
    PrerenderedPage.objects.all().delete()
    account.rank_damage = encode_rank("master", 1)
    account.save()
    assert _requested() == set()


@pytest.mark.django_db
def test_the_export_carries_the_profile_and_the_alumni_records():
    captain = _user("c@example.com", "队长")
    GameAccount.objects.create(user=captain, battletag="队长#1234")
    member = _user("e@example.com", "导出的")
    GameAccount.objects.create(user=member, battletag="导出的#1234")
    member.motto, member.main_role, member.flex_roles = "推车", "support", "tank"
    member.save()
    team = team_services.create_team(user=captain, name="一队")
    application = team_services.apply_to_team(
        team=team, user=member, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    team_services.leave_team(team=team, user=member)
    assert TeamAlumnus.objects.filter(user=member).exists()
    data = personal_data(member)
    assert data["account"]["motto"] == "推车"
    assert data["account"]["main_role"] == "支援"
    assert data["account"]["flex_roles"] == ["坦克"]
    assert data["account"]["show_rank"] is True
    assert [entry["team"] for entry in data["team_alumni"]] == ["一队"]
    assert data["team_alumni"][0]["reason"] == "退出"
