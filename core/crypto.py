"""Fernet helpers for SiteSettings secrets (design 3.6 / 12.4.1)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    raw = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    if not raw:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEY is required to encrypt SMTP passwords."
        )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(plaintext: str) -> str:
    """Encrypt a UTF-8 string. Empty input stays empty."""
    if plaintext == "":
        return ""
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet token. Empty input stays empty."""
    if ciphertext == "":
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError(
            "Stored secret is not valid ciphertext for FIELD_ENCRYPTION_KEY. "
            "If this was saved as plaintext before encryption was enforced, "
            "save the SiteSettings row again to encrypt it."
        ) from exc


def looks_like_fernet(value: str) -> bool:
    """True when value has the usual Fernet urlsafe-base64 prefix."""
    return bool(value) and value.startswith("gAAAAA")


def is_fernet_token(value: str) -> bool:
    """True when value decrypts with the current key."""
    if not value:
        return False
    try:
        decrypt_value(value)
    except ValueError:
        return False
    return True
