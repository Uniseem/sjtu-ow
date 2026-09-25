"""Every address the design names still exists and still renders.

Rounds 026-028 pinned the design's numbers, enums and rank scores. This
pins its URLs: a refactor that drops or renames a route is easy to make
and easy to miss, and the design refers to these paths by name throughout.
"""

import pytest

# Paths the design writes out, with an id substituted where it uses <id>,
# each paired with the view that must answer it.
#
# The expected view matters: wagtail_urls is a catch-all at the end of the
# URLconf, so resolve() succeeds for *any* path. Deleting a route does not
# raise Resolver404 — it silently falls through to wagtail_serve.
RESOLVABLE = [
    ("/healthz", "healthz"),
    ("/members/", "members"),
    ("/me/", "me_profile"),
    ("/me/contacts/", "me_contacts"),
    ("/me/game-accounts/", "me_game_accounts"),
    ("/me/registrations/", "me_registrations"),
    ("/me/security/", "me_security"),
    ("/me/teams/", "me_teams"),
    ("/me/scrims/", "me_scrims"),
    ("/registrations/1/", "registration_detail"),
    ("/scrims/", "scrim_index"),
    ("/scrims/1/", "scrim_detail"),
    ("/submit/", "submit"),
    ("/teams/", "team_index"),
    ("/teams/1/", "team_detail"),
    ("/teams/1/apply/", "team_apply"),
    ("/teams/1/manage/", "team_manage"),
    ("/teams/new/", "team_create"),
    ("/tournaments/", "tournament_index"),
    ("/tournaments/1/", "tournament_detail"),
    ("/tournaments/1/register/", "tournament_register"),
    ("/tournaments/1/signup/", "tournament_individual_signup"),
    ("/tournaments/1/signup/cancel/", "tournament_individual_cancel"),
    ("/_fragments/state/", "state_fragment"),
]

# Wagtail pages created by init_site; these are served by the page tree.
PUBLIC_PAGES = ["/", "/news/", "/about/", "/terms/", "/privacy/"]


@pytest.mark.parametrize(("path", "expected_view"), RESOLVABLE)
def test_every_documented_path_reaches_its_own_view(path, expected_view):
    from django.urls import resolve

    match = resolve(path)
    actual = match.view_name or match.func.__name__
    assert actual == expected_view, (
        f"设计里写到的 {path} 现在由 {actual} 处理，应该是 {expected_view}。"
        "（落到 wagtail_serve 说明路由被删了或改名了，"
        "Wagtail 的兜底路由会接住一切，不会报 404。）"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_render_for_anonymous_visitors(client, path):
    """Resolving is not rendering: a template or context error still 500s."""
    from io import StringIO

    from django.core.management import call_command

    call_command("init_site", stdout=StringIO(), stderr=StringIO())

    response = client.get(path)

    assert response.status_code == 200, f"{path} 返回 {response.status_code}"
    assert response.content.strip(), f"{path} 返回了空页面"


@pytest.mark.django_db
def test_the_personal_area_sends_anonymous_visitors_to_login(client):
    response = client.get("/me/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_healthz_reports_each_check_by_name(client):
    """Design 16.6: the probe says which check failed, not just that one did."""
    response = client.get("/healthz")

    assert response.status_code in (200, 503)
    body = response.json()
    assert set(body["checks"]) == {
        "database",
        "disk",
        "worker_heartbeat",
        "task_backlog",
    }
    assert body["checks"]["database"]["ok"] is True
