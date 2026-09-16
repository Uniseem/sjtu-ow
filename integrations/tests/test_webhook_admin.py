"""Design 11.8.3 / 14.2: the webhook half of the API client admin."""

import pytest
from django.utils import timezone

from accounts.models import User
from integrations import services as api_services
from integrations.models import DeliveryStatus, WebhookDelivery, WebhookPayloadMode


@pytest.fixture(autouse=True)
def allow_local_webhooks(settings):
    settings.WEBHOOK_ALLOW_INSECURE_URLS = True


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        email="root@example.com", password="Correct-Horse-Battery-1", nickname="超管"
    )


@pytest.fixture
def api_client(db):
    client, _ = api_services.create_client(
        name="上游", scopes=["registrations:read"], allowed_includes=["team"]
    )
    return client


@pytest.fixture
def admin(client, superuser):
    client.login(email="root@example.com", password="Correct-Horse-Battery-1")
    return client


def detail_url(api_client):
    return f"/admin/settings/api-clients/{api_client.pk}/"


@pytest.mark.django_db
def test_saving_the_webhook_configuration(admin, api_client):
    response = admin.post(
        detail_url(api_client),
        {
            "action": "webhook",
            "webhook_url": "https://upstream.example.com/hooks",
            "webhook_secret": "s3cret",
            "webhook_events": ["ping", "registration.status_changed"],
            "webhook_payload_mode": WebhookPayloadMode.FULL,
        },
    )
    assert response.status_code == 302
    api_client.refresh_from_db()
    assert api_client.webhook_url == "https://upstream.example.com/hooks"
    assert api_client.webhook_secret == "s3cret"
    assert api_client.webhook_events == ["ping", "registration.status_changed"]
    assert api_client.webhook_payload_mode == WebhookPayloadMode.FULL


@pytest.mark.django_db
def test_an_empty_secret_keeps_the_old_one(admin, api_client):
    api_client.webhook_secret = "keep-me"
    api_client.save()
    admin.post(
        detail_url(api_client),
        {
            "action": "webhook",
            "webhook_url": "https://upstream.example.com/hooks",
            "webhook_secret": "",
            "webhook_events": ["ping"],
            "webhook_payload_mode": WebhookPayloadMode.THIN,
        },
    )
    api_client.refresh_from_db()
    assert api_client.webhook_secret == "keep-me"


@pytest.mark.django_db
def test_an_internal_webhook_url_is_refused(admin, api_client, settings):
    settings.WEBHOOK_ALLOW_INSECURE_URLS = False
    admin.post(
        detail_url(api_client),
        {
            "action": "webhook",
            "webhook_url": "https://127.0.0.1/hooks",
            "webhook_events": ["ping"],
            "webhook_payload_mode": WebhookPayloadMode.THIN,
        },
    )
    api_client.refresh_from_db()
    assert api_client.webhook_url == ""


@pytest.mark.django_db
def test_the_test_event_button(admin, api_client):
    api_client.webhook_url = "https://upstream.example.com/hooks"
    api_client.webhook_secret = "s"
    api_client.save()

    admin.post(detail_url(api_client), {"action": "ping"})

    delivery = WebhookDelivery.objects.get()
    assert delivery.event_type == "ping"
    assert delivery.client_id == api_client.pk


@pytest.mark.django_db
def test_the_test_event_button_needs_a_url(admin, api_client):
    admin.post(detail_url(api_client), {"action": "ping"})
    assert WebhookDelivery.objects.count() == 0


@pytest.mark.django_db
def test_manual_resend_keeps_the_event_id(admin, api_client):
    delivery = WebhookDelivery.objects.create(
        client=api_client,
        event_type="ping",
        payload={},
        status=DeliveryStatus.FAILED,
        attempts=8,
        last_status_code=500,
    )
    event_id = delivery.event_id

    admin.post(detail_url(api_client), {"action": "resend", "delivery": delivery.pk})

    delivery.refresh_from_db()
    assert delivery.event_id == event_id
    assert delivery.status == DeliveryStatus.PENDING
    assert delivery.attempts == 0


@pytest.mark.django_db
def test_cannot_resend_another_clients_delivery(admin, api_client):
    other, _ = api_services.create_client(name="别人", scopes=[], allowed_includes=[])
    delivery = WebhookDelivery.objects.create(
        client=other, event_type="ping", payload={}, status=DeliveryStatus.FAILED
    )

    response = admin.post(
        detail_url(api_client), {"action": "resend", "delivery": delivery.pk}
    )

    assert response.status_code == 404
    delivery.refresh_from_db()
    assert delivery.status == DeliveryStatus.FAILED


@pytest.mark.django_db
def test_the_delivery_list_page(admin, api_client):
    WebhookDelivery.objects.create(
        client=api_client,
        event_type="registration.status_changed",
        payload={},
        status=DeliveryStatus.SUCCEEDED,
        delivered_at=timezone.now(),
    )
    response = admin.get(f"/admin/settings/api-clients/{api_client.pk}/deliveries/")
    assert response.status_code == 200
    assert "registration.status_changed" in response.content.decode()


@pytest.mark.django_db
def test_a_wagtail_admin_who_is_not_a_superuser_is_refused(client, api_client):
    """Give them real Wagtail admin access, so superuser_required is what bites."""
    from django.contrib.auth.models import Group, Permission

    staff = User.objects.create_user(
        email="staff@example.com",
        password="Correct-Horse-Battery-1",
        nickname="职员",
        is_staff=True,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    group = Group.objects.create(name="后台可进")
    group.permissions.add(
        Permission.objects.get(
            codename="access_admin", content_type__app_label="wagtailadmin"
        )
    )
    staff.groups.add(group)
    client.force_login(staff)

    # Wagtail turns the PermissionDenied from superuser_required into a
    # redirect back to the admin home, so the denial looks like a 302 to
    # "/admin/" rather than a 403 body.
    for path in (
        f"/admin/settings/api-clients/{api_client.pk}/",
        f"/admin/settings/api-clients/{api_client.pk}/deliveries/",
    ):
        response = client.get(path)
        assert response.status_code == 302, path
        assert response["Location"] == "/admin/", path
        assert api_client.key_id not in response.content.decode(), path

    # And the page really is unreachable, not merely redirected once.
    followed = client.get(
        f"/admin/settings/api-clients/{api_client.pk}/deliveries/", follow=True
    )
    assert api_client.key_id not in followed.content.decode()
