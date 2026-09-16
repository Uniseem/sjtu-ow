"""Keep the generated OpenAPI document to the public API (design 11)."""

from __future__ import annotations

PUBLIC_PREFIX = "/api/v1/"


def only_public_api(endpoints, **kwargs):
    """Wagtail's own admin API is not part of the upstream contract."""
    return [endpoint for endpoint in endpoints if endpoint[0].startswith(PUBLIC_PREFIX)]
