"""Round 067: the open API and the upstream review paths are gone (design v1.6).

Round 066 pinned the removal of the LFG board the same way: a "gone" test
is the only thing that notices when a deleted feature quietly comes back
through a merge or a stale settings file.
"""

import pytest
from django.apps import apps
from django.conf import settings


def test_the_api_packages_are_not_installed():
    for name in ("rest_framework", "drf_spectacular", "drf_spectacular_sidecar"):
        assert name not in settings.INSTALLED_APPS, name
    assert "integrations.middleware.ApiRequestLogMiddleware" not in settings.MIDDLEWARE
    gone = ("REST_FRAMEWORK", "SPECTACULAR_SETTINGS", "WEBHOOK_ALLOW_INSECURE_URLS")
    for name in gone:
        assert not hasattr(settings, name), name


def test_integrations_keeps_only_its_migration_history():
    """The package stays installed: tournaments/0004 depends on its 0001."""
    assert "integrations" in settings.INSTALLED_APPS
    assert list(apps.get_app_config("integrations").get_models()) == []


@pytest.mark.django_db
def test_the_api_routes_are_gone(client):
    for path in ("/api/v1/ping/", "/api/v1/docs/", "/api/v1/tournaments/"):
        assert client.get(path).status_code == 404, path


def test_the_upstream_left_no_enum_values_or_fields():
    from tournaments import models

    assert not hasattr(models, "ReviewMode")
    assert "awaiting_upstream" not in models.RegistrationStatus.values
    assert "upstream" not in models.ActorType.values
    names = {field.name for field in models.Tournament._meta.get_fields()}
    assert {"review_mode", "source_client", "external_id"}.isdisjoint(names)
    assert "auto_approve" in names
    log_fields = models.RegistrationStatusLog._meta.get_fields()
    assert "actor_client" not in {field.name for field in log_fields}


@pytest.mark.django_db
def test_the_wagtail_admin_api_works_without_our_drf_settings(client):
    """Wagtail's page explorer calls /admin/api/main/pages/ through Django
    REST framework. The REST_FRAMEWORK settings left with the open API; the
    admin API must keep working on DRF's defaults (design 2.2)."""
    from django.contrib.auth import get_user_model

    root = get_user_model().objects.create_superuser(
        email="root-admin-api@example.com", password="Correct-Horse-Battery-1"
    )
    client.force_login(root)

    response = client.get("/admin/api/main/pages/")

    assert response.status_code == 200
    assert "meta" in response.json()
