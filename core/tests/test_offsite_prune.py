"""Off-site backups keep 14 days too (design 16.7, round 063).

Until round 063 the backup command pruned only the local copies; every
upload stayed in the bucket for ever.
"""

import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from core import offsite
from core.models import SiteSettings

KEY = "a-backup-encryption-key-for-tests"
NOW = datetime.datetime(2026, 9, 18, 12, 0, tzinfo=datetime.UTC)


class AgingBucket:
    """A bucket whose objects have ages, pages its listing, and deletes."""

    def __init__(self, page_size=1000):
        self.objects: dict[str, datetime.datetime] = {}
        self.page_size = page_size
        self.delete_batches: list[int] = []

    def put(self, key, days_old):
        self.objects[key] = NOW - datetime.timedelta(days=days_old)

    def upload_file(self, source, bucket, key):
        self.objects[key] = NOW

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None):  # noqa: N803
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start : start + self.page_size]
        response = {
            "Contents": [
                {"Key": key, "LastModified": self.objects[key]} for key in page
            ]
        }
        if start + self.page_size < len(keys):
            response["IsTruncated"] = True
            response["NextContinuationToken"] = str(start + self.page_size)
        return response

    def delete_objects(self, Bucket, Delete):  # noqa: N803
        batch = [item["Key"] for item in Delete["Objects"]]
        assert len(batch) <= 1000
        self.delete_batches.append(len(batch))
        for key in batch:
            self.objects.pop(key)


@pytest.fixture
def configured(db, settings):
    settings.BACKUP_ENCRYPTION_KEY = KEY
    site = SiteSettings.load()
    site.backup_s3_enabled = True
    site.backup_s3_endpoint = "https://account.r2.cloudflarestorage.com"
    site.backup_s3_bucket = "sjtu-ow-backups"
    site.backup_s3_access_key_id = "AKIAEXAMPLE"
    site.backup_s3_secret_access_key = "s3cret"
    site.backup_s3_prefix = "sjtu-ow/"
    site.save()
    return offsite.load_config()


def _use(monkeypatch, bucket):
    monkeypatch.setattr(offsite, "client_factory", lambda config: bucket)
    return bucket


def _archive(day):
    return f"sjtu-ow/sjtu-ow-202609{day:02d}-030000.tar.gz.enc"


@pytest.mark.django_db
def test_old_archives_go_and_recent_ones_stay(monkeypatch, configured):
    bucket = _use(monkeypatch, AgingBucket())
    bucket.put(_archive(1), days_old=17)
    bucket.put(_archive(3), days_old=15)
    bucket.put(_archive(10), days_old=8)

    removed = offsite.prune(14, config=configured, now=NOW)

    assert removed == 2
    assert set(bucket.objects) == {_archive(10)}


@pytest.mark.django_db
def test_nothing_that_is_not_ours_is_touched(monkeypatch, configured):
    """The bucket may be shared: only sjtu-ow-<stamp>.tar.gz.enc goes."""
    bucket = _use(monkeypatch, AgingBucket())
    for key in (
        "sjtu-ow/notes.txt",
        "sjtu-ow/sjtu-ow-20260901-030000.tar.gz",  # not encrypted, not ours
        "sjtu-ow/other-20260901-030000.tar.gz.enc",
        "sjtu-ow/sjtu-ow-latest.tar.gz.enc",
        "elsewhere/sjtu-ow-20260901-030000.tar.gz.enc",  # outside the prefix
        "sjtu-ow-20260901-030000.tar.gz.enc",  # bucket root, still matches "sjtu-ow"
        "sjtu-ow/old/sjtu-ow-20260901-030000.tar.gz.enc",  # a sub-folder
    ):
        bucket.put(key, days_old=100)

    assert offsite.prune(14, config=configured, now=NOW) == 0
    assert len(bucket.objects) == 7


@pytest.mark.django_db
def test_every_page_of_the_listing_is_read(monkeypatch, configured):
    bucket = _use(monkeypatch, AgingBucket(page_size=2))
    for day in range(1, 6):
        bucket.put(_archive(day), days_old=30)

    assert offsite.prune(14, config=configured, now=NOW) == 5
    assert bucket.objects == {}


@pytest.mark.django_db
def test_deletes_go_in_batches_of_a_thousand(monkeypatch, configured):
    bucket = _use(monkeypatch, AgingBucket())
    for index in range(1001):
        key = f"sjtu-ow/sjtu-ow-20250101-{index // 60:02d}{index % 60:02d}00.tar.gz.enc"
        bucket.put(key, days_old=300)

    assert offsite.prune(14, config=configured, now=NOW) == 1001
    assert bucket.delete_batches == [1000, 1]


def _run_backup(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    out = StringIO()
    call_command(
        "backup", "--output", str(tmp_path / "backups"), stdout=out, stderr=out
    )
    return out.getvalue()


@pytest.mark.django_db
def test_the_backup_command_prunes_after_uploading(
    monkeypatch, configured, tmp_path, settings
):
    bucket = _use(monkeypatch, AgingBucket())
    bucket.put(_archive(1), days_old=40)
    monkeypatch.setattr(offsite, "prune", _real_prune_at(NOW))

    output = _run_backup(tmp_path, settings)

    assert _archive(1) not in bucket.objects
    assert len(bucket.objects) == 1  # the new upload
    assert "已清理异地 1 个" in output


@pytest.mark.django_db
def test_a_failed_prune_does_not_fail_the_backup(
    monkeypatch, configured, tmp_path, settings
):
    _use(monkeypatch, AgingBucket())

    def broken(*args, **kwargs):
        raise offsite.OffsiteError("网络断了")

    monkeypatch.setattr(offsite, "prune", broken)
    output = _run_backup(tmp_path, settings)

    assert "已加密并上传" in output
    assert "异地旧备份没清理掉" in output


def _real_prune_at(now):
    real = offsite.prune

    def prune(keep_days, *, config=None):
        return real(keep_days, config=config, now=now)

    return prune
