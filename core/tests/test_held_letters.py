"""Round 204 (design 10.5, v7.8): letters an action writes wait for the
person who did it, who sends them or not on 「发信」.

User 10-05: 「然后所有的发信都必须手动点发信，这个逻辑也要改！」 — verification
codes and timed reminders still go by themselves.

The flows through real pages use ``transaction=True``: the letters are
written in ``on_commit``, which in production runs inside the request; in a
test wrapped in one transaction it would only run after the page answered,
outside the batch, and the letters would go at once.
"""

import inspect
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from core import outbox
from core.letters import Letter
from core.models import HeldLetter
from core.tests.test_chapter15_audit import _verified, make_user


def _letter(subject="入队申请：测试队"):
    return Letter(
        subject=subject,
        lead="有人申请加入。",
        facts=[("战队", "测试队")],
        action=("打开", "https://example.com/teams/1/"),
    )


def _people(*indexes):
    return [_verified(make_user(index)) for index in indexes]


# --- the rule ---------------------------------------------------------------------


@pytest.mark.django_db
def test_outside_a_request_the_letter_goes_at_once():
    """The worker, a command, a service called on its own: nobody to ask."""
    (someone,) = _people(1)
    assert outbox.hold(_letter(), [someone]) == 1
    assert [message.to for message in mail.outbox] == [[someone.email]]
    assert not HeldLetter.objects.exists()


@pytest.mark.django_db
def test_inside_an_action_the_letter_waits_written_down_whole():
    actor, captain = _people(1, 2)
    with outbox.asking(actor) as batch:
        assert outbox.hold(_letter(), [captain]) == 0
    assert mail.outbox == []
    row = HeldLetter.objects.get()
    assert (row.batch, row.actor, row.state) == (batch.key, actor, "waiting")
    assert row.recipients == [[captain.email, captain.nickname]]
    assert outbox.thaw(row.letter) == _letter()  # what goes out is what was seen


@pytest.mark.django_db
def test_the_same_letter_to_more_people_is_one_letter():
    actor, first, second = _people(1, 2, 3)
    with outbox.asking(actor):
        outbox.hold(_letter("赛事取消"), [first])
        outbox.hold(_letter("赛事取消"), [second, first])
        outbox.hold(_letter("另一封"), [first])
    rows = list(HeldLetter.objects.all())
    assert [len(row.recipients) for row in rows] == [2, 1]
    assert outbox.who(rows[0], actor) == f"{first.nickname}、{second.nickname}"
    assert outbox.who(rows[0], first) == f"你自己、{second.nickname}"


@pytest.mark.django_db
def test_a_cancelled_tournament_is_one_letter_to_all_its_people():
    """Cancelling writes the same letter once per person (design 8.1); the
    「发信」 page shows it once, with all of them on it."""
    from tournaments import services
    from tournaments.tests.test_adhoc_teams import formed

    tournament, _registration, entries, admin = formed.__wrapped__(None)
    with outbox.asking(admin):
        services.cancel(tournament=tournament, actor=admin, reason="场地没了")
    row = HeldLetter.objects.get(letter__subject=f"赛事已取消：{tournament.title}")
    assert sorted(address for address, _name in row.recipients) == sorted(
        entry.user.email for entry in entries
    )
    assert mail.outbox == []


@pytest.mark.django_db
def test_only_the_ticked_letters_go_and_only_once():
    actor, first, second = _people(1, 2, 3)
    with outbox.asking(actor) as batch:
        outbox.hold(_letter("第一封"), [first])
        outbox.hold(_letter("第二封"), [second])
    keep, drop = HeldLetter.objects.order_by("pk")
    assert outbox.decide(actor, batch.key, {keep.pk}) == (1, 1)
    assert [message.subject for message in mail.outbox] == ["第一封"]
    assert mail.outbox[0].to == [first.email]
    keep.refresh_from_db()
    drop.refresh_from_db()
    assert (keep.state, drop.state) == ("sent", "skipped")
    assert outbox.decide(actor, batch.key, {keep.pk, drop.pk}) == (0, 0)
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_two_clicks_at_once_send_once(monkeypatch):
    """Both requests read the letters while they were still waiting; each
    row is claimed once, so only the first sends."""
    actor, captain = _people(1, 2)
    with outbox.asking(actor) as batch:
        outbox.hold(_letter(), [captain])
    seen = list(HeldLetter.objects.values_list("pk", flat=True))
    monkeypatch.setattr(
        outbox, "waiting", lambda person: HeldLetter.objects.filter(pk__in=seen)
    )
    assert outbox.decide(actor, batch.key, set(seen)) == (1, 1)
    assert outbox.decide(actor, batch.key, set(seen)) == (0, 0)
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_a_letter_left_seven_days_is_void():
    actor, captain = _people(1, 2)
    with outbox.asking(actor) as batch:
        outbox.hold(_letter(), [captain])
    HeldLetter.objects.update(created_at=timezone.now() - timedelta(days=8))
    assert outbox.waiting_count(actor) == 0
    every = set(HeldLetter.objects.values_list("pk", flat=True))
    assert outbox.decide(actor, batch.key, every) == (0, 0)
    assert mail.outbox == []


@pytest.mark.django_db
def test_timed_reminders_go_by_themselves_even_during_a_request():
    """「到点的提醒照旧到点自动发」: they call ``send``, not ``hold``."""
    from teams import notifications
    from teams import services as team_services

    actor, captain, applicant = _people(1, 2, 3)
    team = team_services.create_team(user=captain, name="提醒队")
    with outbox.asking(actor):
        notifications.applications_waiting(team, [], captain)
    assert [message.to for message in mail.outbox] == [[captain.email]]
    assert not HeldLetter.objects.exists()


ACTION_LETTERS = {
    "teams.notifications": [
        "application_submitted",
        "application_decided",
        "member_removed",
        "member_left",
        "captain_changed",
        "team_disbanded",
    ],
    "tournaments.notifications": ["tournament_cancelled"],
    "tournaments.notifications_registration": [
        "registration_submitted",
        "team_members_entered",
        "registration_status_changed",
        "adhoc_team_formed",
        "adhoc_members_returned",
        "adhoc_member_left",
    ],
    "scrims.notifications": ["scrim_cancelled"],
    "accounts.notifications": ["avatar_taken_down"],
}


def test_every_letter_an_action_brings_is_held():
    """The fifteen of design 10.5; going back to ``send`` would skip 「发信」."""
    import importlib

    found = 0
    for module_name, names in ACTION_LETTERS.items():
        module = importlib.import_module(module_name)
        for name in names:
            source = inspect.getsource(getattr(module, name))
            assert "hold(" in source, f"{module_name}.{name}"
            assert " send(" not in source and "\tsend(" not in source, name
            found += 1
    assert found == 15


@pytest.mark.django_db
def test_nobody_left_to_ask_means_the_letters_go():
    """Deleting the account signs the person out; their leaving an ad-hoc
    team still has to reach the tournament admins."""
    actor, admin = _people(1, 2)
    with outbox.asking(actor) as batch:
        outbox.hold(_letter("临时队伍成员退出"), [admin])
    request = RequestFactory().post("/me/delete/")
    request.user = AnonymousUser()
    response = outbox.settle(request, HttpResponseRedirect("/"), batch)
    assert response.url == "/"
    assert [message.to for message in mail.outbox] == [[admin.email]]
    assert HeldLetter.objects.get().state == "sent"


@pytest.mark.django_db
def test_deleting_the_account_drops_its_letters():
    from accounts.services import delete_account

    actor, captain = _people(1, 2)
    with outbox.asking(actor):
        outbox.hold(_letter(), [captain])
    delete_account(actor)
    assert not HeldLetter.objects.filter(actor=actor).exists()


# --- through the pages ---------------------------------------------------------------


def _applying(client):
    from accounts.models import GameAccount
    from teams import services as team_services

    captain, applicant = _people(1, 2)
    GameAccount.objects.create(user=applicant, battletag="申请人#1234")
    team = team_services.create_team(user=captain, name="发信测试队")
    client.force_login(applicant)
    response = client.post(reverse("team_apply", args=[team.pk]), {"role_tank": "on"})
    return captain, applicant, team, response


@pytest.mark.django_db(transaction=True)
def test_a_member_applies_and_is_asked_before_the_captain_is_mailed(client):
    captain, applicant, team, response = _applying(client)
    assert team.applications.filter(applicant=applicant).exists()  # done anyway
    assert mail.outbox == []
    row = HeldLetter.objects.get()
    assert response.url == reverse("letters_confirm", args=[row.batch])
    assert row.back == reverse("team_detail", args=[team.pk])
    assert not row.in_back_office

    page = client.get(response.url).content.decode()
    assert row.letter["subject"] in page
    assert captain.nickname in page
    assert reverse("letters_preview", args=[row.batch, row.pk]) in page
    preview = client.get(reverse("letters_preview", args=[row.batch, row.pk]))
    assert row.letter["lead"] in preview.content.decode()

    done = client.post(response.url, {"send": [row.pk]})
    assert done.url == row.back
    assert [message.to for message in mail.outbox] == [[captain.email]]
    assert client.get(response.url).url == row.back  # handled: back where it went
    assert len(mail.outbox) == 1


@pytest.mark.django_db(transaction=True)
def test_not_sending_sends_nothing(client):
    captain, applicant, team, response = _applying(client)
    row = HeldLetter.objects.get()
    done = client.post(response.url, {"send": [row.pk], "skip": "1"})
    assert done.url == row.back
    assert mail.outbox == []
    row.refresh_from_db()
    assert row.state == "skipped"


@pytest.mark.django_db(transaction=True)
def test_nobody_else_opens_or_sends_them(client):
    captain, applicant, team, response = _applying(client)
    row = HeldLetter.objects.get()
    client.force_login(captain)
    assert client.get(response.url).status_code == 404
    assert client.post(response.url, {"send": [row.pk]}).status_code == 404
    preview = reverse("letters_preview", args=[row.batch, row.pk])
    assert client.get(preview).status_code == 404
    nothing = reverse("letters_confirm", args=[uuid.uuid4()])
    assert client.get(nothing).status_code == 404
    assert mail.outbox == []


@pytest.mark.django_db(transaction=True)
def test_letters_left_waiting_are_pointed_at(client):
    captain, applicant, team, response = _applying(client)
    me = client.get(reverse("me_profile")).content.decode()
    assert "有 1 件事的信还没决定发不发" in me
    listing = client.get(reverse("letters_waiting")).content.decode()
    assert response.url in listing
    client.post(response.url, {"skip": "1"})
    assert "还没决定发不发" not in client.get(reverse("me_profile")).content.decode()


@pytest.mark.django_db(transaction=True)
def test_an_admin_cancels_a_scrim_and_is_asked_in_the_back_office(client):
    from accounts.tests.test_onboarding import _user
    from scrims.tests.test_my_placement import _scrim, _signup

    call_command("init_site", verbosity=0)
    admin = _user("scrimadmin204@example.com")
    admin.is_superuser = True
    admin.save(update_fields=["is_superuser"])
    scrim = _scrim()
    first, _ = _signup(scrim, "s1-204@example.com", "报名一")
    second, _ = _signup(scrim, "s2-204@example.com", "报名二")
    client.force_login(admin)
    response = client.post(reverse("scrim_cancel", args=[scrim.pk]))
    scrim.refresh_from_db()
    assert scrim.status == "cancelled"
    row = HeldLetter.objects.get()
    assert response.url == reverse("backoffice:letters_confirm", args=[row.batch])
    assert row.in_back_office
    assert len(row.recipients) == 2  # one letter, both on it

    page = client.get(response.url).content.decode()
    assert "要不要发信" in page
    assert 'aria-current="page">活动</a>' in page  # where it was done
    home = client.get(reverse("backoffice:home")).content.decode()
    assert "有 1 件事的信还没决定发不发" in home

    client.post(response.url, {"send": [row.pk]})
    assert sorted(message.to[0] for message in mail.outbox) == sorted(
        [first.email, second.email]
    )


@pytest.mark.django_db
def test_the_daily_cleanup_drops_old_letters():
    """The addresses on them go after 30 days, as task records do."""
    from io import StringIO

    actor, captain = _people(1, 2)
    with outbox.asking(actor):
        outbox.hold(_letter("旧的"), [captain])
        outbox.hold(_letter("新的"), [captain])
    HeldLetter.objects.filter(letter__subject="旧的").update(
        created_at=timezone.now() - timedelta(days=31)
    )
    call_command("cleanup_old_data", stdout=StringIO())
    assert [row.letter["subject"] for row in HeldLetter.objects.all()] == ["新的"]
