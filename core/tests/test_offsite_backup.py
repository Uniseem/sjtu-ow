"""Design 16.7 step 3: encrypt the backup and keep a copy off the server.

A fake bucket stands in for S3 — these tests are about our encryption and
our wiring, not about boto3 or Cloudflare.
"""

import datetime
import shutil
import tarfile
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core import offsite
from core.models import SiteSettings

KEY = "a-backup-encryption-key-for-tests"


class FakeBucket:
    """Records what was uploaded, and hands it back on download."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.uploads: list[tuple[str, str]] = []

    def upload_file(self, source, bucket, key):
        self.objects[key] = Path(source).read_bytes()
        self.uploads.append((bucket, key))

    def download_file(self, bucket, key, target):
        if key not in self.objects:
            raise RuntimeError(f"no such key: {key}")
        Path(target).write_bytes(self.objects[key])

    def list_objects_v2(self, Bucket, Prefix=""):  # noqa: N803 — boto3's spelling
        now = datetime.datetime.now(datetime.UTC)
        return {
            "Contents": [
                {"Key": key, "Size": len(body), "LastModified": now}
                for key, body in self.objects.items()
                if key.startswith(Prefix)
            ]
        }


@pytest.fixture
def bucket(monkeypatch, settings):
    settings.BACKUP_ENCRYPTION_KEY = KEY
    fake = FakeBucket()
    monkeypatch.setattr(offsite, "client_factory", lambda config: fake)
    return fake


@pytest.fixture
def configured(db):
    site = SiteSettings.load()
    site.backup_s3_enabled = True
    site.backup_s3_endpoint = "https://account.r2.cloudflarestorage.com"
    site.backup_s3_bucket = "sjtu-ow-backups"
    site.backup_s3_access_key_id = "AKIAEXAMPLE"
    site.backup_s3_secret_access_key = "s3cret"
    site.backup_s3_prefix = "sjtu-ow/"
    site.save()
    return site


def run(*args, **kwargs):
    out = StringIO()
    call_command(*args, stdout=out, stderr=out, **kwargs)
    return out.getvalue()


# --- encryption ----------------------------------------------------------------


def test_encrypt_and_decrypt_round_trip(tmp_path, settings):
    settings.BACKUP_ENCRYPTION_KEY = KEY
    source = tmp_path / "backup.tar.gz"
    source.write_bytes(b"pretend this is a database and some uploads")

    encrypted = offsite.encrypt_file(source, tmp_path / "backup.enc")
    assert encrypted.read_bytes() != source.read_bytes()
    assert b"pretend this is" not in encrypted.read_bytes()

    restored = offsite.decrypt_file(encrypted, tmp_path / "back.tar.gz")
    assert restored.read_bytes() == source.read_bytes()


def test_a_different_key_cannot_decrypt(tmp_path, settings):
    settings.BACKUP_ENCRYPTION_KEY = KEY
    source = tmp_path / "backup.tar.gz"
    source.write_bytes(b"secrets")
    encrypted = offsite.encrypt_file(source, tmp_path / "backup.enc")

    settings.BACKUP_ENCRYPTION_KEY = "a-completely-different-key"

    with pytest.raises(offsite.OffsiteError, match="BACKUP_ENCRYPTION_KEY"):
        offsite.decrypt_file(encrypted, tmp_path / "out.tar.gz")


def test_without_a_key_nothing_is_encrypted_or_uploaded(tmp_path, settings):
    """Design 16.7: never ship a plaintext backup off the server."""
    settings.BACKUP_ENCRYPTION_KEY = ""
    source = tmp_path / "backup.tar.gz"
    source.write_bytes(b"secrets")

    with pytest.raises(offsite.OffsiteError, match="BACKUP_ENCRYPTION_KEY"):
        offsite.encrypt_file(source, tmp_path / "backup.enc")


# --- the key must not live in the database -------------------------------------


def test_the_encryption_key_is_not_a_database_setting():
    """A key stored in the database would be inside the backup it protects.

    Restore after losing the server and you would hold a file you cannot
    open. It has to come from the environment.
    """
    fields = {field.name for field in SiteSettings._meta.get_fields()}
    for forbidden in (
        "backup_encryption_key",
        "backup_key",
        "backup_secret",
        "backup_passphrase",
    ):
        assert forbidden not in fields, forbidden

    from django.conf import settings as django_settings

    assert hasattr(django_settings, "BACKUP_ENCRYPTION_KEY")


# --- upload --------------------------------------------------------------------


@pytest.mark.django_db
def test_backup_uploads_an_encrypted_copy(tmp_path, settings, bucket, configured):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    backups = tmp_path / "backups"

    output = run("backup", "--output", str(backups))

    assert len(bucket.uploads) == 1
    bucket_name, key = bucket.uploads[0]
    assert bucket_name == "sjtu-ow-backups"
    assert key.startswith("sjtu-ow/sjtu-ow-")
    assert key.endswith(".tar.gz.enc")
    assert "已加密并上传" in output

    # What landed in the bucket is not readable as an archive.
    body = bucket.objects[key]
    assert not body.startswith(b"\x1f\x8b")  # not gzip
    assert b"sqlite" not in body.lower()


@pytest.mark.django_db
def test_the_local_copy_stays_unencrypted_and_usable(
    tmp_path, settings, bucket, configured
):
    """Only the off-server copy is encrypted; the local one restores directly."""
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    backups = tmp_path / "backups"

    run("backup", "--output", str(backups))

    archives = list(backups.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as bundle:
        assert "db.sqlite3" in bundle.getnames()
    # The temporary encrypted file is not left lying around.
    assert list(backups.glob("*.enc")) == []


@pytest.mark.django_db
def test_no_upload_when_the_feature_is_off(tmp_path, settings, bucket, db):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()

    output = run("backup", "--output", str(tmp_path / "backups"))

    assert bucket.uploads == []
    assert "异地备份没有开启" in output
    assert "服务器没了这份也跟着没了" in output


@pytest.mark.django_db
def test_no_upload_flag(tmp_path, settings, bucket, configured):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()

    output = run("backup", "--output", str(tmp_path / "backups"), "--no-upload")

    assert bucket.uploads == []
    assert "跳过上传" in output


@pytest.mark.django_db
def test_a_half_configured_bucket_fails_loudly(tmp_path, settings, bucket, configured):
    """A backup that did not reach the bucket must not report success."""
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    configured.backup_s3_bucket = ""
    configured.save()

    with pytest.raises(CommandError, match="上传失败"):
        run("backup", "--output", str(tmp_path / "backups"))


@pytest.mark.django_db
def test_upload_failure_is_not_silent(tmp_path, settings, monkeypatch, configured):
    settings.BACKUP_ENCRYPTION_KEY = KEY
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()

    class Broken:
        def upload_file(self, *args, **kwargs):
            raise RuntimeError("network is down")

    monkeypatch.setattr(offsite, "client_factory", lambda config: Broken())

    with pytest.raises(CommandError, match="network is down"):
        run("backup", "--output", str(tmp_path / "backups"))


# --- restore from the bucket ---------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_restore_pulls_from_the_bucket_and_decrypts(
    tmp_path, settings, bucket, configured
):
    from accounts.models import User

    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    settings.PRERENDER_ROOT = tmp_path / "prerendered"
    from django.utils import timezone

    now = timezone.now()
    User.objects.create_user(
        email="offsite@example.com",
        password="Correct-Horse-Battery-1",
        nickname="异地备份用户",
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    run("backup", "--output", str(tmp_path / "backups"))
    _bucket_name, key = bucket.uploads[0]

    User.objects.filter(email="offsite@example.com").delete()
    shutil.rmtree(tmp_path / "backups")  # the local copy is gone too

    run("restore", "--from-s3", key, "--yes")

    assert User.objects.filter(email="offsite@example.com").exists()


@pytest.mark.django_db
def test_listing_shows_what_is_in_the_bucket(tmp_path, settings, bucket, configured):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    run("backup", "--output", str(tmp_path / "backups"))

    output = run("restore", "--list-s3")

    assert "sjtu-ow/sjtu-ow-" in output
    assert "--from-s3" in output


@pytest.mark.django_db
def test_restore_needs_a_source():
    with pytest.raises(CommandError, match="--from-s3"):
        run("restore")
