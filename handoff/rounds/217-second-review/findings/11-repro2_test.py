"""217 复核 11 后台：第二批复现（只读业务代码）。

    bash scripts/remote-check.sh run uv run pytest -q -s \
        handoff/rounds/217-second-review/findings/11-repro2_test.py
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.tests.test_onboarding import _user


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _root(email):
    root = _user(email)
    root.is_superuser = True
    root.is_staff = True
    root.save()
    return root


# --- 11-6：操作记录按「到 9999-12-31」筛选 -> 500 ----------------------------------


@pytest.mark.django_db
def test_11_6_action_log_until_far_future_500s(site):
    client = Client(raise_request_exception=False)
    client.force_login(_root("r217log@example.com"))
    response = client.get(reverse("backoffice:log"), {"until": "9999-12-31"})
    print("操作记录 until=9999-12-31:", response.status_code)
    assert response.status_code == 500


# --- 11-7：清理空草稿把只写了简介的赛事草稿删掉 -------------------------------------


@pytest.mark.django_db
def test_11_7_cleanup_deletes_tournament_draft_with_only_a_summary(site):
    from core.management.commands.cleanup_old_data import Command
    from tournaments.models import Tournament

    draft = Tournament.objects.create(
        title="",
        summary="下学期新生杯的简介，还没想好名字",
        participant_contact="QQ 群 123",
    )
    Tournament.objects.filter(pk=draft.pk).update(
        updated_at=timezone.now() - timedelta(days=30)
    )
    found = Command.empty_drafts(False, timezone.now())
    print("清理数到的空草稿:", found)
    print("只写了简介的草稿还在吗:", Tournament.objects.filter(pk=draft.pk).exists())
    assert not Tournament.objects.filter(pk=draft.pk).exists()
