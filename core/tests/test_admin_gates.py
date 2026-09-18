"""Admin pages refuse the wrong staff member (round 059's guard sweep).

Every one of these checks could be removed without a test noticing: the
existing admin tests all logged in as a superuser, who passes every check.
Here the visitor is a content editor, who may enter the admin but has no
business in teams, scrims, moderation or site settings.
"""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from scrims.tests.test_scrims import make_scrim
from teams import services as team_services


@pytest.fixture
def editor(db):
    call_command("init_site", verbosity=0)
    user = User.objects.create_user(
        email="editor-gate@example.com",
        password="Correct-Horse-Battery-1",
        nickname="内容编辑",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    user.groups.add(Group.objects.get(name="内容编辑"))
    return User.objects.get(pk=user.pk)


def _refused(response) -> bool:
    """Wagtail turns PermissionDenied inside the admin into a redirect home."""
    return response.status_code == 403 or (
        response.status_code == 302
        and response["Location"] == reverse("wagtailadmin_home")
    )


@pytest.fixture
def team(db):
    captain = User.objects.create_user(
        email="gate-captain@example.com",
        password="Correct-Horse-Battery-1",
        nickname="队长",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    return team_services.create_team(user=captain, name="门禁测试队")


@pytest.mark.django_db
def test_the_editor_can_enter_the_admin(client, editor):
    client.force_login(editor)
    assert client.get(reverse("wagtailadmin_home")).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["team_assign_captain", "team_admin_disband"])
def test_team_rescue_pages_are_superuser_only(client, editor, team, name):
    client.force_login(editor)
    assert _refused(client.get(reverse(name, args=[team.pk])))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name, extra",
    [
        ("scrim_action", ["publish"]),
        ("scrim_cancel", []),
        ("scrim_split", []),
        ("scrim_split_text", []),
    ],
)
def test_scrim_admin_pages_need_the_scrim_manager_role(client, editor, name, extra):
    scrim = make_scrim()
    client.force_login(editor)
    assert _refused(client.get(reverse(name, args=[scrim.pk, *extra])))


@pytest.mark.django_db
def test_moderation_needs_the_review_permission(client, db):
    call_command("init_site", verbosity=0)
    author = User.objects.create_user(
        email="gate-author@example.com",
        password="Correct-Horse-Battery-1",
        nickname="认证作者",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    author.groups.add(Group.objects.get(name="认证作者"))
    client.force_login(author)
    assert _refused(client.get(reverse("moderation_index")))


@pytest.mark.django_db
def test_sending_a_test_email_needs_the_site_settings_permission(client, editor):
    from django.core import mail

    client.force_login(editor)
    response = client.post(reverse("core_send_test_email"))
    assert _refused(response)
    assert mail.outbox == []
