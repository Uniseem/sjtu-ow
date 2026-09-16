import os

from django.core.exceptions import ImproperlyConfigured


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    """Read a string environment variable."""
    value = os.environ.get(name)
    if value is None or value == "":
        if required and default is None:
            raise ImproperlyConfigured(f"Environment variable {name} is required.")
        return "" if default is None else default
    return value


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable (`1`/`true`/`yes`/`on`)."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable into a list of stripped items."""
    raw = env(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]
