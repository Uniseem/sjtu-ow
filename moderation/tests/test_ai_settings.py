"""Round 197: AI review is configured in 全站设置, not in .env (design 5.5.3,
v7.1). The user, 10-05: 「把 ai 的设置也放到后台去，我不想改什么 env，只想在后台改」.
"""

import pytest
from django.core.management import call_command
from django.db import connection
from django.urls import reverse
from wagtail.test.utils.form_data import querydict_from_html

from accounts.tests.test_onboarding import _user
from core.models import SiteSettings
from moderation import services
from moderation.providers import DEFAULT_BASE_URL, get_provider
from moderation.tests.test_moderation import configure_ai


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _root():
    from accounts.models import User

    user = _user("root197@example.com")
    User.objects.filter(pk=user.pk).update(is_superuser=True, is_staff=True)
    return User.objects.get(pk=user.pk)


def _settings_form(client):
    url = reverse("backoffice:site_settings")
    page = client.get(url).content.decode()
    return url, page, querydict_from_html(page, form_index=0)


# --- what the provider is built from ------------------------------------------


@pytest.mark.django_db
def test_the_provider_comes_from_the_settings_row():
    site = configure_ai("sk-197", "https://ai.example.com/v1/")
    site.moderation_timeout = 12
    site.moderation_max_output_tokens = 345
    site.moderation_extra_body = {"thinking": {"type": "disabled"}}
    site.save()
    provider = get_provider()
    assert provider.api_key == "sk-197"
    assert provider.base_url == "https://ai.example.com/v1"
    assert provider.timeout == 12
    payload = provider.build_payload(["昵称"], "m")
    assert payload["max_tokens"] == 345
    assert payload["thinking"] == {"type": "disabled"}
    configure_ai("sk-197", "")
    assert get_provider().base_url == DEFAULT_BASE_URL  # blank: DeepSeek


@pytest.mark.django_db
def test_a_key_or_an_address_is_enough_and_nothing_else_is_read(settings):
    settings.MODERATION_API_KEY = "from-the-environment"  # no longer read
    configure_ai("", "")
    assert services.is_configured() is False
    assert get_provider().api_key == ""
    configure_ai("sk-197", "")
    assert services.is_configured() is True
    configure_ai("", "http://10.0.0.5:8000/v1")  # self-hosted, no key
    assert services.is_configured() is True


def test_the_extra_body_is_an_object_without_the_request_s_own_keys():
    assert services.clean_extra_body(None) == {}
    assert services.clean_extra_body("") == {}
    body = {"thinking": {"type": "disabled"}}
    assert services.clean_extra_body(body) == body
    for wrong in ([1, 2], "abc", 3):
        with pytest.raises(ValueError, match="JSON 对象"):
            services.clean_extra_body(wrong)
    for key in ("messages", "tools", "tool_choice"):
        with pytest.raises(ValueError, match=key):
            services.clean_extra_body({key: []})


def test_the_environment_variables_are_gone():
    from django.conf import settings

    for name in (
        "MODERATION_API_KEY",
        "MODERATION_BASE_URL",
        "MODERATION_EXTRA_BODY",
        "MODERATION_TIMEOUT",
        "MODERATION_MAX_OUTPUT_TOKENS",
    ):
        assert not hasattr(settings, name), name


# --- the settings page --------------------------------------------------------


@pytest.mark.django_db
def test_the_key_is_saved_encrypted_never_shown_and_kept_when_blank(site, client):
    client.force_login(_root())
    url, page, data = _settings_form(client)
    assert "现在：还没有。" in page
    data["moderation_api_key"] = "sk-secret-197"
    data["moderation_base_url"] = "https://ai.example.com/v1"
    data["moderation_extra_body"] = '{"thinking": {"type": "disabled"}}'
    response = client.post(url, data)
    assert response.status_code == 302, response.content.decode()[:1500]
    site_settings = SiteSettings.load()
    assert site_settings.moderation_api_key == "sk-secret-197"
    assert site_settings.moderation_extra_body == {"thinking": {"type": "disabled"}}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT moderation_api_key FROM core_sitesettings WHERE id = %s",
            [site_settings.pk],
        )
        stored = cursor.fetchone()[0]
    assert stored and "sk-secret-197" not in stored  # ciphertext only

    url, page, data = _settings_form(client)
    assert "sk-secret-197" not in page
    assert "现在：已保存。" in page
    assert data["moderation_api_key"] == ""
    data["moderation_timeout"] = "20"
    client.post(url, data)  # the key box left blank
    site_settings = SiteSettings.load()
    assert site_settings.moderation_api_key == "sk-secret-197"
    assert site_settings.moderation_timeout == 20


@pytest.mark.django_db
def test_a_bad_extra_body_is_refused_on_the_field(site, client):
    client.force_login(_root())
    url, _page, data = _settings_form(client)
    for wrong, said in (
        ("[1, 2]", "JSON 对象"),
        ('{"tools": []}', "tools"),
        ("{这不是 JSON", ""),
    ):
        data["moderation_extra_body"] = wrong
        response = client.post(url, data)
        assert response.status_code == 200, wrong
        assert said in response.content.decode()
    assert SiteSettings.load().moderation_extra_body == {}
    data["moderation_extra_body"] = ""
    assert client.post(url, data).status_code == 302
    assert SiteSettings.load().moderation_extra_body == {}


@pytest.mark.django_db
def test_wagtails_own_settings_page_keeps_the_key_too(site, client):
    """The fallback under /wagtail/ (superusers) uses core.forms."""
    configure_ai("sk-kept-197")
    client.force_login(_root())
    row = SiteSettings.load()
    response = client.get(
        reverse("wagtailsettings:edit", args=["core", "sitesettings", row.pk]),
        follow=True,
    )
    url = response.request["PATH_INFO"]
    page = response.content.decode()
    assert "sk-kept-197" not in page
    data = querydict_from_html(page, form_id="w-editor-form")
    data["site_description"] = "从底层后台改的"
    client.post(url, data)
    row = SiteSettings.load()
    assert row.site_description == "从底层后台改的"
    assert row.moderation_api_key == "sk-kept-197"


@pytest.mark.django_db
def test_the_ai_is_tried_from_the_settings_page_and_comes_back(site, client):
    from unittest import mock

    from moderation.models import Risk
    from moderation.providers import ProviderResult, Verdict

    configure_ai("sk-197")
    client.force_login(_root())
    settings_url = reverse("backoffice:site_settings")
    page = client.get(settings_url).content.decode()
    assert f'action="{reverse("moderation_try")}"' in page and "data-try-ai" in page
    provider = mock.Mock()
    provider.review.return_value = ProviderResult(
        verdicts=[Verdict(index=0, risk=Risk.NONE)], model="m"
    )
    with mock.patch("moderation.providers.get_provider", return_value=provider):
        response = client.post(reverse("moderation_try"), {"next": settings_url})
        assert response["Location"] == settings_url
        away = client.post(reverse("moderation_try"), {"next": "https://evil.example/"})
        assert away["Location"] == reverse("moderation_index")


@pytest.mark.django_db
def test_without_a_key_the_owner_is_sent_to_the_settings(site):
    assert "全站设置" in services.disabled_reason()
    assert ".env" not in services.disabled_reason()


# --- the migration ------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_migration_carries_the_old_environment_in(monkeypatch):
    from django.db.migrations.executor import MigrationExecutor

    def migrate(target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])

    SiteSettings.load()  # the row the migration fills
    try:
        migrate(("core", "0020_ai_patrol"))
        monkeypatch.setenv("MODERATION_API_KEY", "sk-from-env")
        monkeypatch.setenv("MODERATION_BASE_URL", "https://env.example.com/v1")
        monkeypatch.setenv(
            "MODERATION_EXTRA_BODY", '{"thinking": {"type": "disabled"}}'
        )
        monkeypatch.setenv("MODERATION_TIMEOUT", "45")
        monkeypatch.setenv("MODERATION_MAX_OUTPUT_TOKENS", "800")
        migrate(("core", "0021_ai_settings_in_admin"))
        row = SiteSettings.load()
        assert row.moderation_api_key == "sk-from-env"
        assert row.moderation_base_url == "https://env.example.com/v1"
        assert row.moderation_extra_body == {"thinking": {"type": "disabled"}}
        assert (row.moderation_timeout, row.moderation_max_output_tokens) == (45, 800)
        with connection.cursor() as cursor:
            cursor.execute("SELECT moderation_api_key FROM core_sitesettings")
            assert "sk-from-env" not in cursor.fetchone()[0]
    finally:
        # Later tests in this process need today's tables (round 211).
        call_command("migrate", verbosity=0)
