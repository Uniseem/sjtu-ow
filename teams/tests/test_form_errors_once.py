"""Round 168: a form-level error is said once.

account/_form.html already shows ``form.non_field_errors``; the team forms
showed it again above, so 「请至少选择一个意向位置。」 appeared twice.
"""

from pathlib import Path

import pytest
from django.core.management import call_command

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.django_db
def test_the_apply_page_says_it_once(client):
    from core.tests.test_chapter15_audit import _verified, make_user
    from teams import services as team_services

    call_command("init_site", verbosity=0)
    team = team_services.create_team(user=_verified(make_user(1)), name="说一次队")
    client.force_login(_verified(make_user(2)))
    html = client.post(f"/teams/{team.pk}/apply/", {"message": ""}).content.decode()
    assert html.count("请至少选择一个意向位置。") == 1


def test_no_page_repeats_what_the_shared_form_says():
    doubled = []
    for path in ROOT.rglob("*.html"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith((".venv/", "node_modules/", "handoff/")):
            continue
        text = path.read_text(encoding="utf-8")
        if 'include "account/_form.html"' in text and "non_field_errors" in text:
            doubled.append(relative)
    assert doubled == []
