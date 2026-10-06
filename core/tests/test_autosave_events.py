"""Round 206 (design 13.17, 8.1, 9.1; v7.10): tournaments and scrims save
themselves. Something new exists from its first change with required fields
still empty, and publishing checks them; a rule across fields holds back one
field; the reminders and refreshes saving arranges are arranged once, and a
reminder due while the admin is still editing waits ten minutes.
"""

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from django_tasks_db.models import DBTaskResult

from accounts.tests.test_onboarding import _user
from core.tasks import REMINDER_GRACE, enqueue_once, prerender_page
from scrims import services as scrim_services
from scrims.models import Scrim, ScrimStatus
from scrims.tasks import finish_past_scrim, send_scrim_reminder
from tournaments import services as tournament_services
from tournaments.models import Tournament, TournamentStatus

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _save(client, url, data):
    return json.loads(client.post(url, data, **AUTOSAVE).content)


def _waiting(task_obj, *args):
    rows = DBTaskResult.objects.filter(status="READY", task_path=task_obj.module_path)
    return [row for row in rows if row.args_kwargs["args"] == list(args)]


def _tournament_fields(tournament, **changes):
    data = {
        "title": tournament.title,
        "summary": tournament.summary,
        "description": tournament.description,
        "registration_mode": tournament.registration_mode,
        "roster_min": tournament.roster_min,
        "roster_max": tournament.roster_max,
        "registration_opens_at": timezone.localtime(
            tournament.registration_opens_at
        ).strftime("%Y-%m-%dT%H:%M"),
        "registration_closes_at": timezone.localtime(
            tournament.registration_closes_at
        ).strftime("%Y-%m-%dT%H:%M"),
    }
    data.update(changes)
    return data


def _published_tournament(**extra):
    now = timezone.now()
    return Tournament.objects.create(
        title="自动保存杯",
        summary="原来的简介",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=3),
        status=TournamentStatus.PUBLISHED,
        **extra,
    )


# --- new ones exist at once; publishing checks ------------------------------------


@pytest.mark.django_db
def test_a_new_tournament_exists_from_its_first_change(site, client):
    manager = _user("tm206@example.com", "赛事管理员")
    client.force_login(manager)
    _published_tournament()
    answer = _save(client, reverse("tournaments:add"), {"summary": "先写一句简介"})
    tournament = Tournament.objects.get(status=TournamentStatus.DRAFT)
    assert answer["location"] == reverse("tournaments:edit", args=[tournament.pk])
    assert {"title", "registration_opens_at", "registration_closes_at"} <= set(
        answer["errors"]
    )
    assert tournament.status == TournamentStatus.DRAFT
    assert tournament.summary == "先写一句简介" and tournament.title == ""
    assert tournament.registration_opens_at is None
    assert tournament.created_by == manager
    listing = client.get(reverse("tournaments:index")).content.decode()
    # The one being written comes first, not after every dated one.
    assert 0 <= listing.find("（未命名赛事）") < listing.find("自动保存杯")

    publish = reverse("tournament_action", args=[tournament.pk, "publish"])
    page = client.get(publish).content.decode()
    assert "还没填好：标题、报名开始时间、报名截止时间" in page
    client.post(publish)
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.DRAFT
    with pytest.raises(tournament_services.TournamentError, match="还没填好"):
        tournament_services.publish(tournament=tournament, actor=manager)

    now = timezone.localtime()
    _save(
        client,
        answer["location"],
        {
            "title": "补齐了杯",
            "summary": "先写一句简介",
            "registration_mode": "individual",
            "roster_min": 5,
            "roster_max": 6,
            "registration_opens_at": now.strftime("%Y-%m-%dT%H:%M"),
            "registration_closes_at": (now + timedelta(days=2)).strftime(
                "%Y-%m-%dT%H:%M"
            ),
        },
    )
    client.post(publish)
    tournament.refresh_from_db()
    assert tournament.status == TournamentStatus.PUBLISHED


@pytest.mark.django_db
def test_a_new_scrim_exists_with_its_start_still_empty(site, client):
    client.force_login(_user("sm206@example.com", "内战管理员"))
    answer = _save(
        client, reverse("scrims:add"), {"description": "周五晚上", "format": "rq_5v5"}
    )
    scrim = Scrim.objects.get()
    assert answer["location"] == reverse("scrims:edit", args=[scrim.pk])
    assert scrim.status == ScrimStatus.DRAFT and scrim.starts_at is None
    assert scrim.description == "周五晚上"
    assert "（未命名内战）" in client.get(reverse("scrims:index")).content.decode()
    page = client.get(reverse("scrim_action", args=[scrim.pk, "publish"])).content
    assert "还没填好：标题、开始时间" in page.decode()
    with pytest.raises(scrim_services.ScrimError, match="还没填好"):
        scrim_services.publish(scrim=scrim)
    # Cancelled is public: a half-filled draft is deleted instead.
    with pytest.raises(scrim_services.ScrimError, match="直接删除"):
        scrim_services.cancel_scrim(scrim=scrim)
    edit = client.get(answer["location"]).content.decode()
    assert reverse("scrim_cancel", args=[scrim.pk]) not in edit


@pytest.mark.django_db
def test_a_copy_keeps_what_it_copied_when_a_field_is_wrong(site, client):
    source = _published_tournament(roster_min=3, roster_max=4)
    client.force_login(_user("copy206@example.com", "赛事管理员"))
    copied = tournament_services.copy_for_new(source)
    data = _tournament_fields(copied, summary="复制后改的简介", roster_max=1)
    answer = _save(client, reverse("tournaments:copy", args=[source.pk]), data)
    assert set(answer["errors"]) == {"roster_max"}
    new = Tournament.objects.exclude(pk=source.pk).get()
    assert new.summary == "复制后改的简介"
    assert (new.roster_min, new.roster_max) == (3, 4)  # copied, the bad one held back
    # As the form showed it (the browser's box holds minutes).
    shown = copied.registration_closes_at.replace(second=0, microsecond=0)
    assert new.registration_closes_at == shown


# --- rules across fields, required fields on published ones ---------------------------


@pytest.mark.django_db
def test_a_rule_across_fields_holds_back_one_field(site, client):
    tournament = _published_tournament()
    client.force_login(_user("rule206@example.com", "赛事管理员"))
    edit = reverse("tournaments:edit", args=[tournament.pk])
    before = tournament.registration_closes_at
    late = timezone.localtime(tournament.registration_opens_at - timedelta(days=1))
    answer = _save(
        client,
        edit,
        _tournament_fields(
            tournament,
            summary="新简介",
            registration_closes_at=late.strftime("%Y-%m-%dT%H:%M"),
        ),
    )
    assert set(answer["errors"]) == {"registration_closes_at"}
    assert "summary" in answer["saved"]
    tournament.refresh_from_db()
    assert (
        tournament.summary == "新简介" and tournament.registration_closes_at == before
    )


@pytest.mark.django_db
def test_a_published_one_keeps_its_required_fields(site, client):
    tournament = _published_tournament()
    client.force_login(_user("keep206@example.com", "赛事管理员"))
    edit = reverse("tournaments:edit", args=[tournament.pk])
    answer = _save(client, edit, _tournament_fields(tournament, title=""))
    assert "title" in answer["errors"]
    tournament.refresh_from_db()
    assert tournament.title == "自动保存杯"


# --- the tasks saving arranges -------------------------------------------------------


@pytest.mark.django_db
def test_saving_again_and_again_arranges_each_task_once(
    site, client, django_capture_on_commit_callbacks
):
    starts = timezone.now() + timedelta(days=2)
    scrim = Scrim.objects.create(
        title="反复保存",
        starts_at=starts,
        format="rq_5v5",
        status=ScrimStatus.PUBLISHED,
    )
    client.force_login(_user("again206@example.com", "内战管理员"))
    edit = reverse("scrims:edit", args=[scrim.pk])
    local = timezone.localtime(starts).strftime("%Y-%m-%dT%H:%M")
    for text in ("一", "二", "三"):
        with django_capture_on_commit_callbacks(execute=True):
            _save(
                client,
                edit,
                {
                    "title": "反复保存",
                    "description": text,
                    "starts_at": local,
                    "format": "rq_5v5",
                },
            )
    assert len(_waiting(send_scrim_reminder, scrim.pk)) == 1
    assert len(_waiting(finish_past_scrim, scrim.pk)) == 1


@pytest.mark.django_db
def test_a_page_refresh_counts_only_at_the_same_moment():
    first = timezone.now() + timedelta(days=1)
    second = first + timedelta(days=1)
    enqueue_once(prerender_page, "/tournaments/", run_after=first)
    enqueue_once(prerender_page, "/tournaments/", run_after=first)
    enqueue_once(prerender_page, "/tournaments/", run_after=second)
    enqueue_once(prerender_page, "/", run_after=second)
    assert sorted(
        row.run_after for row in _waiting(prerender_page, "/tournaments/")
    ) == [
        first,
        second,
    ]


@pytest.mark.django_db
def test_an_earlier_waiting_reminder_is_enough_a_later_one_is_not():
    soon = timezone.now() + timedelta(hours=1)
    enqueue_once(send_scrim_reminder, 7, run_after=soon, earlier_counts=True)
    enqueue_once(
        send_scrim_reminder, 7, run_after=soon + timedelta(hours=1), earlier_counts=True
    )
    assert len(_waiting(send_scrim_reminder, 7)) == 1
    enqueue_once(
        send_scrim_reminder,
        7,
        run_after=soon - timedelta(minutes=30),
        earlier_counts=True,
    )
    assert len(_waiting(send_scrim_reminder, 7)) == 2


@pytest.mark.django_db
def test_a_reminder_due_while_editing_waits_ten_minutes(
    django_capture_on_commit_callbacks,
):
    scrim = Scrim.objects.create(
        title="一小时后",
        starts_at=timezone.now() + timedelta(hours=1),  # inside the 2-hour window
        format="rq_5v5",
        status=ScrimStatus.PUBLISHED,
    )
    with django_capture_on_commit_callbacks(execute=True):
        scrim_services.schedule_reminder(scrim)
    (row,) = _waiting(send_scrim_reminder, scrim.pk)
    wait = row.run_after - timezone.now()
    assert REMINDER_GRACE - timedelta(minutes=1) < wait <= REMINDER_GRACE

    # Starting sooner than that: at once, a late reminder beats none.
    close = Scrim.objects.create(
        title="五分钟后",
        starts_at=timezone.now() + timedelta(minutes=5),
        format="rq_5v5",
        status=ScrimStatus.PUBLISHED,
    )
    with django_capture_on_commit_callbacks(execute=True):
        scrim_services.schedule_reminder(close)
    (row,) = _waiting(send_scrim_reminder, close.pk)
    assert row.run_after <= timezone.now()


@pytest.mark.django_db
def test_a_tournament_reminder_waits_too(django_capture_on_commit_callbacks):
    from tournaments.tasks import send_tournament_reminder

    tournament = _published_tournament(starts_at=timezone.now() + timedelta(hours=3))
    with django_capture_on_commit_callbacks(execute=True):
        tournament_services.schedule_reminder(tournament)
        tournament_services.schedule_reminder(tournament)
    (row,) = _waiting(send_tournament_reminder, tournament.pk)
    assert row.run_after - timezone.now() > REMINDER_GRACE - timedelta(minutes=1)


# --- round 212, T1: the rule reports on one field; the pair saves or not at all -----


@pytest.mark.django_db
def test_changing_the_other_half_of_a_rule_saves_nothing_of_the_pair(site, client):
    """Editing registration_opens_at past the deadline: the error lands on
    registration_closes_at (v7.10), and opens must not save alone — alone it
    breaks the tournament_registration_window constraint (IntegrityError,
    and the rest of the request lost with it)."""
    tournament = _published_tournament()
    client.force_login(_user("half212@example.com", "赛事管理员"))
    edit = reverse("tournaments:edit", args=[tournament.pk])
    before = tournament.registration_opens_at
    late = timezone.localtime(tournament.registration_closes_at + timedelta(days=1))
    answer = _save(
        client,
        edit,
        _tournament_fields(
            tournament,
            summary="又改了简介",
            registration_opens_at=late.strftime("%Y-%m-%dT%H:%M"),
        ),
    )
    assert "registration_closes_at" in answer["errors"]
    assert "summary" in answer["saved"]
    assert "registration_opens_at" not in answer["saved"]
    tournament.refresh_from_db()
    assert tournament.summary == "又改了简介"
    assert tournament.registration_opens_at == before


@pytest.mark.django_db
def test_a_copy_with_the_window_backwards_is_no_500_and_keeps_the_times(site, client):
    """The new/copy path creates the draft from the fields that are fine; a
    backwards window used to die as an IntegrityError 500 and retry forever."""
    source = _published_tournament()
    client.force_login(_user("copy212@example.com", "赛事管理员"))
    copied = tournament_services.copy_for_new(source)
    late = timezone.localtime(copied.registration_closes_at + timedelta(days=1))
    data = _tournament_fields(
        copied,
        summary="复制时改的简介",
        registration_opens_at=late.strftime("%Y-%m-%dT%H:%M"),
    )
    response = client.post(
        reverse("tournaments:copy", args=[source.pk]), data, **AUTOSAVE
    )
    assert response.status_code == 200
    answer = json.loads(response.content)
    assert "registration_closes_at" in answer["errors"]
    new = Tournament.objects.exclude(pk=source.pk).get()
    assert answer["location"] == reverse("tournaments:edit", args=[new.pk])
    assert new.summary == "复制时改的简介"
    # The bad half of the pair kept what the copy had; the pair stays legal.
    assert new.registration_opens_at == copied.registration_opens_at
    assert new.registration_opens_at < new.registration_closes_at


@pytest.mark.django_db
def test_the_roster_pair_also_saves_together_or_not_at_all(site, client):
    """Changing roster_min past roster_max: min must not save alone either
    (the tournament_roster_range constraint)."""
    tournament = _published_tournament(roster_min=5, roster_max=6)
    client.force_login(_user("roster212@example.com", "赛事管理员"))
    edit = reverse("tournaments:edit", args=[tournament.pk])
    answer = _save(
        client, edit, _tournament_fields(tournament, summary="简介三", roster_min=7)
    )
    assert "roster_max" in answer["errors"]
    assert "summary" in answer["saved"] and "roster_min" not in answer["saved"]
    tournament.refresh_from_db()
    assert tournament.roster_min == 5 and tournament.summary == "简介三"
