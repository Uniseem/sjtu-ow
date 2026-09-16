"""Encrypted model field: all write paths store Fernet ciphertext."""

from __future__ import annotations

from django.db import models

from core.crypto import (
    decrypt_value,
    encrypt_value,
    is_fernet_token,
    looks_like_fernet,
)


class EncryptedTextField(models.TextField):
    """Transparent Fernet field. Legacy plaintext is returned as-is until next save."""

    def from_db_value(self, value, _expression, _connection):
        return self.to_python(value)

    def to_python(self, value):
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        if value == "":
            return ""
        try:
            return decrypt_value(value)
        except ValueError:
            if looks_like_fernet(value):
                raise
            return value

    def get_prep_value(self, value):
        # Do not call TextField.get_prep_value: it runs to_python() and would
        # decrypt ciphertext before we can detect an existing Fernet token.
        if value is None or value == "":
            return ""
        if not isinstance(value, str):
            value = str(value)
        if is_fernet_token(value):
            return value
        if looks_like_fernet(value):
            raise ValueError(
                "Stored secret is not valid ciphertext for FIELD_ENCRYPTION_KEY. "
                "If this was saved as plaintext before encryption was enforced, "
                "save the SiteSettings row again to encrypt it."
            )
        return encrypt_value(value)
