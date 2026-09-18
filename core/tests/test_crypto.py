import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from core.crypto import decrypt_value, encrypt_value
from core.models import SiteSettings


def _raw_smtp_password(pk) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT smtp_password FROM core_sitesettings WHERE id = %s",
            [pk],
        )
        return cursor.fetchone()[0]


@pytest.mark.django_db
def test_orm_write_stores_fernet_ciphertext():
    site = SiteSettings.objects.create(smtp_password="plain-from-orm")
    raw = _raw_smtp_password(site.pk)
    assert raw != "plain-from-orm"
    assert raw.startswith("gAAAAA")
    assert decrypt_value(raw) == "plain-from-orm"
    site.refresh_from_db()
    assert site.smtp_password == "plain-from-orm"


@pytest.mark.django_db
def test_legacy_plaintext_is_reencrypted_on_next_save():
    site = SiteSettings.objects.create(smtp_password="placeholder")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE core_sitesettings SET smtp_password = %s WHERE id = %s",
            ["legacy-plaintext", site.pk],
        )
    site.refresh_from_db()
    assert site.smtp_password == "legacy-plaintext"
    site.save()
    raw = _raw_smtp_password(site.pk)
    assert raw != "legacy-plaintext"
    assert raw.startswith("gAAAAA")
    assert decrypt_value(raw) == "legacy-plaintext"
    site.refresh_from_db()
    assert site.smtp_password == "legacy-plaintext"


@pytest.mark.django_db
def test_existing_ciphertext_is_not_double_encrypted():
    token = encrypt_value("already-encrypted")
    site = SiteSettings.objects.create(smtp_password=token)
    assert _raw_smtp_password(site.pk) == token
    site.refresh_from_db()
    assert site.smtp_password == "already-encrypted"


def test_an_empty_key_is_refused_rather_than_hashed(settings):
    """sha256("") is a key anyone can compute: encrypting with it is plaintext."""
    settings.FIELD_ENCRYPTION_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        encrypt_value("smtp-password")


@pytest.mark.django_db
def test_reading_ciphertext_from_another_key_fails_loudly(settings):
    """After a key change the stored token must not come back as the password."""
    site = SiteSettings.objects.create(smtp_password="real-password")
    settings.FIELD_ENCRYPTION_KEY = "a-different-key"
    with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEY"):
        SiteSettings.objects.get(pk=site.pk)


@pytest.mark.django_db
def test_saving_ciphertext_from_another_key_is_not_encrypted_again(settings):
    """Wrapping a foreign token in a second layer would lose the password."""
    settings.FIELD_ENCRYPTION_KEY = "the-old-key"
    foreign = encrypt_value("real-password")
    settings.FIELD_ENCRYPTION_KEY = "the-new-key"
    with pytest.raises(ValueError, match="FIELD_ENCRYPTION_KEY"):
        SiteSettings.objects.create(smtp_password=foreign)
