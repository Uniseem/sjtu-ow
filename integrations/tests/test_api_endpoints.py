import csv
import io
import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from integrations import services as api_services
from integrations.tests.test_api_auth import sign_request
from teams import services as team_services
from tournaments import registration as reg
from tournaments.models import (
    ActorType,
    RegistrationStatus,
    ReviewMode,
    Tournament,
    TournamentStatus,
)

ALL_INCLUDES = ["tournament", "team", "members", "members.ranks", "logs"]


def call(client, method, path, *, api, secret, body=None, query=()):
    payload = json.dumps(body).encode() if body is not None else b""
    headers = sign_request(method, path, query, payload, api.key_id, secret)
    full = path
    if query:
        full = path + "?" + "&".join(f"{name}={value}" for name, value in query)
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["data"] = payload
        kwargs["content_type"] = "application/json"
    return getattr(client, method.lower())(full, **kwargs)


@pytest.fixture
def api(db):
    cache.clear()
    return api_services.create_client(
        name="上游平台",
        scopes=[
            "tournaments:read",
            "tournaments:write",
            "registrations:read",
            "registrations:review",
        ],
        allowed_includes=ALL_INCLUDES,
    )


def _player(email, nickname, *, sjtu=True, rank=22):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=sjtu,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    GameAccount.objects.create(
        user=user, battletag=f"{nickname}#1234", rank_damage=rank
    )
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


@pytest.fixture
def tournament(db):
    now = timezone.now()
    return Tournament.objects.create(
        title="秋季邀请赛",
        summary="面向上海高校",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=7),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
        review_mode=ReviewMode.UPSTREAM,
    )


@pytest.fixture
def registration(tournament):
    captain = _player("api-cap@example.com", "接口队长")
    mate = _player("api-mate@example.com", "接口队员", sjtu=False, rank=40)
    team = team_services.create_team(user=captain, name="接口战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    selections = {
        str(membership.user.pk): membership.user.game_accounts.first().pk
        for membership in team.memberships.all()
    }
    return reg.submit(
        tournament=tournament, team=team, actor=captain, selections=selections
    )


# --- tournaments ---------------------------------------------------------------


@pytest.mark.django_db
def test_tournament_list_and_detail(client, api, tournament):
    api_obj, secret = api
    response = call(client, "GET", "/api/v1/tournaments", api=api_obj, secret=secret)
    assert response.status_code == 200
    body = response.json()
    assert body["has_more"] is False
    item = body["data"][0]
    assert item["id"] == tournament.pk
    assert item["source"] == "local"
    assert item["external_id"] is None
    assert "description_html" not in item
    assert item["url"].endswith(f"/tournaments/{tournament.pk}/")

    path = f"/api/v1/tournaments/{tournament.pk}"
    detail = call(client, "GET", path, api=api_obj, secret=secret).json()["data"]
    assert "description_html" in detail


@pytest.mark.django_db
def test_local_drafts_are_hidden(client, api, tournament):
    api_obj, secret = api
    Tournament.objects.filter(pk=tournament.pk).update(status=TournamentStatus.DRAFT)
    body = call(client, "GET", "/api/v1/tournaments", api=api_obj, secret=secret).json()
    assert body["data"] == []
    path = f"/api/v1/tournaments/{tournament.pk}"
    missing = call(client, "GET", path, api=api_obj, secret=secret)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_upsert_creates_then_updates(client, api):
    api_obj, secret = api
    now = timezone.now()
    payload = {
        "title": "上游推的赛事",
        "summary": "摘要",
        "description_html": "<p>说明</p><script>alert(1)</script>",
        "status": "published",
        "registration_opens_at": (now - timedelta(days=1)).isoformat(),
        "registration_closes_at": (now + timedelta(days=5)).isoformat(),
        "roster_min": 2,
        "roster_max": 6,
        "review_mode": "upstream",
    }
    created = call(
        client,
        "PUT",
        "/api/v1/tournaments/external/up-1",
        api=api_obj,
        secret=secret,
        body=payload,
    )
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["external_id"] == "up-1"
    assert data["source"] == "upstream"
    assert data["description_html"] == "<p>说明</p>"  # script dropped

    payload["title"] = "改了标题"
    updated = call(
        client,
        "PUT",
        "/api/v1/tournaments/external/up-1",
        api=api_obj,
        secret=secret,
        body=payload,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "改了标题"
    assert Tournament.objects.filter(external_id="up-1").count() == 1


@pytest.mark.django_db
def test_upsert_validates(client, api):
    api_obj, secret = api
    response = call(
        client,
        "PUT",
        "/api/v1/tournaments/external/up-2",
        api=api_obj,
        secret=secret,
        body={"title": "缺字段"},
    )
    assert response.status_code == 422  # design 11.10
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_review_mode_locks_after_a_registration(client, api, registration):
    api_obj, secret = api
    tournament = registration.tournament
    tournament.source_client = api_obj
    tournament.external_id = "up-3"
    tournament.save()
    now = timezone.now()
    response = call(
        client,
        "PUT",
        "/api/v1/tournaments/external/up-3",
        api=api_obj,
        secret=secret,
        body={
            "title": tournament.title,
            "registration_opens_at": (now - timedelta(days=1)).isoformat(),
            "registration_closes_at": (now + timedelta(days=5)).isoformat(),
            "roster_min": 2,
            "roster_max": 3,
            "review_mode": "local",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "review_mode_locked"


@pytest.mark.django_db
def test_external_id_is_only_visible_to_its_owner(client, api, db):
    api_obj, secret = api
    other, other_secret = api_services.create_client(
        name="别的上游", scopes=["tournaments:read"], allowed_includes=[]
    )
    now = timezone.now()
    Tournament.objects.create(
        title="甲推的",
        source_client=api_obj,
        external_id="mine",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=1),
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    mine = call(client, "GET", "/api/v1/tournaments", api=api_obj, secret=secret).json()
    assert mine["data"][0]["external_id"] == "mine"
    theirs = call(
        client, "GET", "/api/v1/tournaments", api=other, secret=other_secret
    ).json()
    assert theirs["data"][0]["external_id"] is None


# --- registrations -------------------------------------------------------------


@pytest.mark.django_db
def test_registration_list_with_includes(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("include", "team,members.ranks")],
    )
    item = response.json()["data"][0]
    assert item["team"]["name"] == "接口战队"
    assert item["member_count"] == 2
    captain = next(member for member in item["members"] if member["is_captain"])
    assert captain["battletag"] == "接口队长#1234"
    assert captain["ranks"]["damage"]["label"] == "钻石 3"
    assert captain["ranks"]["tank"] is None
    assert "123456789" not in json.dumps(item, ensure_ascii=False)


@pytest.mark.django_db
def test_include_needs_permission(client, db, registration):
    limited, secret = api_services.create_client(
        name="只读基本信息",
        scopes=["registrations:read"],
        allowed_includes=["team"],
    )
    response = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=limited,
        secret=secret,
        query=[("include", "members")],
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "include_not_allowed"


@pytest.mark.django_db
def test_fields_filtering(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("include", "team"), ("fields", "status,team.name")],
    )
    item = response.json()["data"][0]
    assert set(item) == {"id", "status", "team"}
    assert set(item["team"]) == {"id", "name"}

    bad = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("fields", "nope")],
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_field"


@pytest.mark.django_db
def test_cursor_paging_and_updated_since(client, api, tournament, registration):
    api_obj, secret = api
    captain = _player("second-cap@example.com", "第二队长")
    mate = _player("second-mate@example.com", "第二队员")
    team = team_services.create_team(user=captain, name="第二战队")
    application = team_services.apply_to_team(
        team=team, user=mate, roles={"tank": True}
    )
    team_services.approve_application(application=application, actor=captain)
    selections = {
        str(membership.user.pk): membership.user.game_accounts.first().pk
        for membership in team.memberships.all()
    }
    second = reg.submit(
        tournament=tournament, team=team, actor=captain, selections=selections
    )

    first_page = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("limit", "1")],
    ).json()
    assert len(first_page["data"]) == 1
    assert first_page["has_more"] is True
    cursor = first_page["next_cursor"]

    second_page = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("cursor", cursor), ("limit", "1")],
    ).json()
    assert second_page["data"][0]["id"] != first_page["data"][0]["id"]

    since = second.updated_at.isoformat().replace("+00:00", "Z")
    incremental = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("updated_since", since)],
    ).json()
    assert [row["id"] for row in incremental["data"]] == [second.pk]


@pytest.mark.django_db
def test_logs_endpoint_hides_the_actor(client, api, registration):
    api_obj, secret = api
    body = call(
        client,
        "GET",
        f"/api/v1/registrations/{registration.pk}/logs",
        api=api_obj,
        secret=secret,
    ).json()
    entry = body["data"][0]
    assert entry["action"] == "submit"
    assert entry["from_status"] is None
    assert entry["actor_type"] == "captain"
    assert "actor_user" not in entry
    assert "actor_client" not in entry


# --- review --------------------------------------------------------------------


@pytest.mark.django_db
def test_upstream_review(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve", "roster_version": registration.roster_version},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "approved"
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED
    entry = registration.logs.order_by("-id").first()
    assert entry.actor_type == "upstream"
    assert entry.actor_client_id == api_obj.pk


@pytest.mark.django_db
def test_roster_version_mismatch(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve", "roster_version": 99},
    )
    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "roster_version_mismatch"
    assert body["details"]["current_roster_version"] == 1


@pytest.mark.django_db
def test_reject_needs_a_note(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "reject", "roster_version": 1},
    )
    assert response.status_code == 422  # design 11.10
    assert "备注" in response.json()["error"]["message"]


@pytest.mark.django_db
def test_local_mode_rejects_upstream_review(client, api, registration):
    """Design 8.5: in 本站审核 mode the upstream must not change any status."""
    api_obj, secret = api
    Tournament.objects.filter(pk=registration.tournament_id).update(
        review_mode=ReviewMode.LOCAL
    )
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve", "roster_version": 1},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "review_not_allowed"
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.PENDING
    assert not registration.logs.filter(actor_type=ActorType.UPSTREAM).exists()


@pytest.mark.django_db
def test_two_stage_upstream_cannot_skip_the_local_stage(client, api, registration):
    """Design 8.5: 两级审核 means this site decides first."""
    api_obj, secret = api
    Tournament.objects.filter(pk=registration.tournament_id).update(
        review_mode=ReviewMode.TWO_STAGE
    )
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve", "roster_version": 1},
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "invalid_state_transition"
    assert error["details"]["current_status"] == RegistrationStatus.PENDING
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.PENDING


@pytest.mark.django_db
def test_two_stage_upstream_confirms_after_the_local_stage(client, api, registration):
    api_obj, secret = api
    Tournament.objects.filter(pk=registration.tournament_id).update(
        review_mode=ReviewMode.TWO_STAGE
    )
    registration.refresh_from_db()
    admin = User.objects.create_user(
        email="stage-admin@example.com",
        password="Correct-Horse-Battery-1",
        nickname="赛事管理员",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    reg.approve(registration=registration, actor=admin)
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.AWAITING_UPSTREAM

    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "approve", "roster_version": registration.roster_version},
    )
    assert response.status_code == 200
    registration.refresh_from_db()
    assert registration.status == RegistrationStatus.APPROVED


@pytest.mark.django_db
def test_review_is_idempotent(client, api, registration):
    """Design 11.6.7: a retry after a timeout writes no second log entry."""
    api_obj, secret = api
    body = {"action": "approve", "roster_version": registration.roster_version}
    first = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body=body,
    )
    assert first.status_code == 200
    registration.refresh_from_db()
    log_count = registration.logs.count()

    second = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body=body,
    )
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "approved"
    registration.refresh_from_db()
    assert registration.logs.count() == log_count


@pytest.mark.django_db
def test_unknown_action_is_rejected(client, api, registration):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=api_obj,
        secret=secret,
        body={"action": "delete", "roster_version": 1},
    )
    assert response.status_code == 422  # design 11.10
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_batch_review_handles_each_row(client, api, registration, tournament):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        "/api/v1/registrations/review-batch",
        api=api_obj,
        secret=secret,
        body={
            "items": [
                {"id": registration.pk, "action": "approve", "roster_version": 1},
                {"id": registration.pk + 999, "action": "approve", "roster_version": 1},
                {"id": registration.pk, "action": "approve", "roster_version": 7},
            ]
        },
    )
    assert response.status_code == 200
    results = response.json()["data"]
    assert results[0]["ok"] is True
    assert results[0]["registration"]["status"] == "approved"
    assert results[1]["ok"] is False
    assert results[1]["error"]["code"] == "not_found"
    assert results[2]["ok"] is False
    assert results[2]["error"]["code"] == "roster_version_mismatch"


@pytest.mark.django_db
def test_batch_limit(client, api):
    api_obj, secret = api
    response = call(
        client,
        "POST",
        "/api/v1/registrations/review-batch",
        api=api_obj,
        secret=secret,
        body={"items": [{"id": index} for index in range(101)]},
    )
    assert response.status_code == 422  # design 11.10
    assert response.json()["error"]["details"]["limit"] == 100


# --- scenario endpoints --------------------------------------------------------


@pytest.mark.django_db
def test_roster_endpoint(client, api, registration):
    api_obj, secret = api
    reg.approve(registration=registration, actor=None, actor_type="upstream")
    body = call(
        client,
        "GET",
        f"/api/v1/tournaments/{registration.tournament_id}/roster",
        api=api_obj,
        secret=secret,
        query=[("include", "members.ranks")],
    ).json()["data"]
    assert body["tournament"]["id"] == registration.tournament_id
    entry = body["registrations"][0]
    assert entry["team"]["name"] == "接口战队"
    assert entry["members"][0]["ranks"]["damage"]["tier"] in ("diamond", "top500")
    assert "123456789" not in json.dumps(body, ensure_ascii=False)


@pytest.mark.django_db
def test_roster_csv(client, api, registration):
    api_obj, secret = api
    reg.approve(registration=registration, actor=None, actor_type="upstream")
    response = call(
        client,
        "GET",
        f"/api/v1/tournaments/{registration.tournament_id}/roster.csv",
        api=api_obj,
        secret=secret,
        query=[("include", "members.ranks")],
    )
    assert response["Content-Type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0][:5] == [
        "registration_id",
        "status",
        "roster_version",
        "team_id",
        "team_name",
    ]
    assert "rank_damage" in rows[0]
    assert any("接口队长" in row for row in rows[1:])


@pytest.mark.django_db
def test_stats(client, api, registration):
    api_obj, secret = api
    body = call(
        client,
        "GET",
        f"/api/v1/tournaments/{registration.tournament_id}/stats",
        api=api_obj,
        secret=secret,
    ).json()["data"]
    assert body["registrations_by_status"]["pending"] == 1
    assert body["active_members"] == 2
    assert body["active_sjtu_members"] == 1
    assert body["active_non_sjtu_members"] == 1


@pytest.mark.django_db
def test_scopes_are_enforced(client, db, registration):
    read_only, secret = api_services.create_client(
        name="只读", scopes=["tournaments:read"], allowed_includes=[]
    )
    response = call(
        client, "GET", "/api/v1/registrations", api=read_only, secret=secret
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "scope_denied"

    review = call(
        client,
        "POST",
        f"/api/v1/registrations/{registration.pk}/review",
        api=read_only,
        secret=secret,
        body={"action": "approve", "roster_version": 1},
    )
    assert review.json()["error"]["code"] == "scope_denied"


@pytest.mark.django_db
def test_no_contact_details_anywhere(client, api, registration):
    api_obj, secret = api
    paths = [
        ("/api/v1/registrations", [("include", "team,members.ranks,logs")]),
        (f"/api/v1/registrations/{registration.pk}", [("include", "members.ranks")]),
        (f"/api/v1/registrations/{registration.pk}/logs", []),
        (f"/api/v1/tournaments/{registration.tournament_id}/roster", []),
    ]
    for path, query in paths:
        response = call(client, "GET", path, api=api_obj, secret=secret, query=query)
        assert "123456789" not in response.content.decode()
        assert "@example.com" not in response.content.decode()


# --- design 11.10: the published error table -----------------------------------


def test_the_error_table_matches_the_design():
    """Design 11.10 is a published contract: names and statuses both."""
    from integrations.api import ERRORS

    documented = {
        "invalid_request": 400,
        "invalid_field": 400,
        "invalid_include": 400,
        "invalid_cursor": 400,
        "missing_auth": 401,
        "invalid_api_key": 401,
        "timestamp_expired": 401,
        "nonce_reused": 401,
        "invalid_signature": 401,
        "scope_denied": 403,
        "include_not_allowed": 403,
        "review_not_allowed": 403,
        "not_found": 404,
        "roster_version_mismatch": 409,
        "invalid_state_transition": 409,
        "review_mode_locked": 409,
        "validation_error": 422,
        "rate_limited": 429,
        "internal_error": 500,
    }
    actual = {code: status for code, (status, _msg) in ERRORS.items()}
    assert actual == documented


@pytest.mark.django_db
def test_an_unknown_include_is_a_bad_request_not_a_permission_error(
    client, api, registration
):
    """Design 11.10 separates a typo (400) from a denied expansion (403)."""
    api_obj, secret = api

    typo = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("include", "menbers")],
    )

    assert typo.status_code == 400
    error = typo.json()["error"]
    assert error["code"] == "invalid_include"
    assert "members" in error["details"]["allowed"]


@pytest.mark.django_db
def test_a_real_include_without_permission_is_still_403(client, db, registration):
    limited, secret = api_services.create_client(
        name="只读基本信息", scopes=["registrations:read"], allowed_includes=["team"]
    )

    response = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=limited,
        secret=secret,
        query=[("include", "logs")],
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "include_not_allowed"


@pytest.mark.django_db
def test_a_broken_cursor_says_so(client, api, registration):
    api_obj, secret = api

    response = call(
        client,
        "GET",
        "/api/v1/registrations",
        api=api_obj,
        secret=secret,
        query=[("cursor", "not-a-real-cursor")],
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


@pytest.mark.django_db
def test_unparseable_json_says_so(client, api):
    api_obj, secret = api
    body = b"{not json at all"
    headers = sign_request(
        "POST", "/api/v1/registrations/review-batch", (), body, api_obj.key_id, secret
    )

    response = client.post(
        "/api/v1/registrations/review-batch",
        data=body,
        content_type="application/json",
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


@pytest.mark.django_db
def test_an_unexpected_failure_still_returns_the_envelope(
    client, api, registration, monkeypatch
):
    """Design 11.10: even a crash answers with a code and the request id."""
    from integrations import api_views

    def boom(*args, **kwargs):
        raise RuntimeError("something nobody predicted")

    monkeypatch.setattr(api_views, "visible_registrations", boom)
    api_obj, secret = api

    response = call(client, "GET", "/api/v1/registrations", api=api_obj, secret=secret)

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "X-Request-Id" in error["message"] or error.get("details", {}).get(
        "request_id"
    )
