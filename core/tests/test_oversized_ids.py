"""Round 166: numbers and dates no database can hold give a 404 or a word,
never a 500."""

import re
from datetime import date
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from accounts.tests.test_onboarding import _user
from core import activity

ROOT = Path(__file__).resolve().parents[2]
HUGE = "99999999999999999999"  # 20 digits, past 64 bits


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _superuser():
    root = _user("root166@example.com")
    root.is_superuser = True
    root.is_staff = True
    root.save()
    return root


@pytest.mark.django_db
def test_a_huge_article_number_is_not_found(site):
    client = Client(raise_request_exception=False)
    assert client.get(f"/comments/{HUGE}/more/").status_code == 404
    client.force_login(_superuser())
    assert client.get(f"/admin/announce/article/{HUGE}/").status_code == 404
    # The longest id that fits still reaches the view.
    assert client.get("/comments/999999999999999999/more/").status_code == 404
    assert reverse("comment_more", args=[999999999999999999])


@pytest.mark.django_db
def test_dates_past_any_calendar_get_a_word(site):
    client = Client(raise_request_exception=False)
    client.force_login(_superuser())
    page = client.get(
        reverse("admin_activity"), {"start": "0001-01-01", "end": "9999-12-31"}
    )
    assert page.status_code == 200
    assert "2000 年到 2100 年" in page.content.decode()
    today = date(2026, 10, 4)
    for wide in (
        {"start": "1999-12-31", "end": "2026-01-01"},
        {"start": "2026-01-01", "end": "2101-01-01"},
    ):
        period, error = activity.period_from(wide, today)
        assert period == activity.school_year(today) and error
    edges = {"start": "2000-01-01", "end": "2100-12-31"}
    assert activity.period_from(edges, today)[1] == ""


def test_no_address_takes_numbers_of_any_length():
    """Every id in the project's own addresses goes through <id:…>."""
    offenders = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith((".venv/", "handoff/")) or "/tests/" in relative:
            continue
        if re.search(r"<int:", path.read_text(encoding="utf-8")):
            offenders.append(relative)
    assert offenders == []
