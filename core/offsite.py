"""Encrypt a backup and put it in object storage (design 16.7 step 3).

Two things live in different places on purpose:

* The **bucket credentials** are in ``SiteSettings``. They are what you need
  to reach the bucket, and losing them along with the database costs
  nothing — you type them in again on the new server.
* The **encryption key** is an environment variable, never the database. A
  key stored in the database would be inside the very backup it protects:
  restore after a total loss and you would hold a file you cannot open.

Design 16.7 suggests age. This uses Fernet instead, because ``cryptography``
is already a dependency and the same primitive already protects the SMTP
password and API secrets. Backups are read whole into memory to encrypt,
which is fine at this size; a much larger media volume would want streaming.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

ENCRYPTED_SUFFIX = ".enc"


class OffsiteError(Exception):
    """Something went wrong reaching or writing to object storage."""


def encryption_key() -> str:
    return (getattr(settings, "BACKUP_ENCRYPTION_KEY", "") or "").strip()


def _fernet() -> Fernet:
    raw = encryption_key()
    if not raw:
        raise OffsiteError(
            "没有设置 BACKUP_ENCRYPTION_KEY，不能上传未加密的备份（设计 16.7）。"
        )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_file(source: Path, target: Path) -> Path:
    target.write_bytes(_fernet().encrypt(source.read_bytes()))
    return target


def decrypt_file(source: Path, target: Path) -> Path:
    try:
        target.write_bytes(_fernet().decrypt(source.read_bytes()))
    except InvalidToken as exc:
        raise OffsiteError(
            "解不开这个备份：BACKUP_ENCRYPTION_KEY 和加密时用的不是同一个。"
        ) from exc
    return target


# --- configuration -------------------------------------------------------------


class Config:
    """The bucket settings, read once so a half-filled form fails clearly."""

    def __init__(self, site):
        self.enabled = bool(site.backup_s3_enabled)
        self.endpoint = (site.backup_s3_endpoint or "").strip()
        self.bucket = (site.backup_s3_bucket or "").strip()
        self.region = (site.backup_s3_region or "auto").strip() or "auto"
        self.access_key = (site.backup_s3_access_key_id or "").strip()
        self.secret_key = (site.backup_s3_secret_access_key or "").strip()
        self.prefix = (site.backup_s3_prefix or "").strip()

    @property
    def missing(self) -> list[str]:
        names = {
            "对象存储地址": self.endpoint,
            "存储桶": self.bucket,
            "Access Key ID": self.access_key,
            "Secret Access Key": self.secret_key,
        }
        return [label for label, value in names.items() if not value]

    def key_for(self, name: str) -> str:
        prefix = self.prefix.strip("/")
        return f"{prefix}/{name}" if prefix else name


def load_config() -> Config:
    from core.models import SiteSettings

    return Config(SiteSettings.load())


# --- the client ----------------------------------------------------------------


def build_client(config: Config):
    """A boto3 S3 client pointed at the configured endpoint.

    Cloudflare R2 is S3-compatible, so the only difference from AWS is the
    endpoint and a region of "auto".
    """
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - boto3 is a dependency
        raise OffsiteError("没有安装 boto3，不能上传备份。") from exc

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        region_name=config.region,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
    )


# Swapped out in tests; see core/tests/test_offsite_backup.py.
client_factory = build_client


def upload(archive: Path, *, config: Config | None = None) -> str:
    """Encrypt ``archive`` and put it in the bucket. Returns the object key."""
    config = config or load_config()
    if not config.enabled:
        raise OffsiteError("异地备份没有开启。")
    if config.missing:
        raise OffsiteError(f"异地备份还缺这些设置：{'、'.join(config.missing)}")

    encrypted = archive.with_name(archive.name + ENCRYPTED_SUFFIX)
    encrypt_file(archive, encrypted)
    key = config.key_for(encrypted.name)
    try:
        client_factory(config).upload_file(str(encrypted), config.bucket, key)
    except OffsiteError:
        raise
    except Exception as exc:  # noqa: BLE001 — every boto failure reads the same
        raise OffsiteError(f"上传失败：{exc}") from exc
    finally:
        encrypted.unlink(missing_ok=True)
    return key


def listing(*, config: Config | None = None, limit: int = 50) -> list[dict]:
    """Recent objects under the prefix, newest first."""
    config = config or load_config()
    if config.missing:
        raise OffsiteError(f"异地备份还缺这些设置：{'、'.join(config.missing)}")
    try:
        response = client_factory(config).list_objects_v2(
            Bucket=config.bucket, Prefix=config.prefix.strip("/")
        )
    except Exception as exc:  # noqa: BLE001
        raise OffsiteError(f"读取列表失败：{exc}") from exc
    items = response.get("Contents", []) or []
    items.sort(key=lambda item: item.get("LastModified", 0), reverse=True)
    return items[:limit]


def download(key: str, target: Path, *, config: Config | None = None) -> Path:
    """Fetch one object and decrypt it to ``target``."""
    config = config or load_config()
    if config.missing:
        raise OffsiteError(f"异地备份还缺这些设置：{'、'.join(config.missing)}")
    encrypted = target.with_name(target.name + ENCRYPTED_SUFFIX)
    try:
        client_factory(config).download_file(config.bucket, key, str(encrypted))
    except Exception as exc:  # noqa: BLE001
        raise OffsiteError(f"下载失败：{exc}") from exc
    try:
        decrypt_file(encrypted, target)
    finally:
        encrypted.unlink(missing_ok=True)
    return target
