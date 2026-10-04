import pytest
from django.core.management import call_command

from core.worker import write_worker_heartbeat


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("createcachetable", verbosity=0)


@pytest.fixture(autouse=True)
def _media_in_a_throwaway_folder(settings, tmp_path_factory):
    """Uploads made by tests land in a temporary folder, never in the
    project's media/ (round 104). Tests needing a particular one set it."""
    settings.MEDIA_ROOT = tmp_path_factory.mktemp("media")


@pytest.fixture(autouse=True)
def _cheap_password_hashing(settings):
    """Argon2 spends 100 MB and tens of milliseconds on every hash, and the
    tests make hundreds of users and logins (round 128). No test is about
    which hasher the site uses; base.py keeps Argon2 for the real thing."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _rate_limit_window_stays_put(monkeypatch):
    """Rate limits count per clock minute (core.ratelimit). A test that makes
    61 requests could straddle a minute and see the count start over, more
    often when the machine is busy (round 155). Tests that need the clock to
    move patch ``core.ratelimit.time.time`` themselves."""
    from types import SimpleNamespace

    from core import ratelimit

    monkeypatch.setattr(
        ratelimit, "time", SimpleNamespace(time=lambda: 1_800_000_000.0)
    )


@pytest.fixture(autouse=True)
def _forget_renditions():
    """The thumbnail cache lives in memory across tests, while the images
    behind it roll back with each test and their ids come round again."""
    from django.core.cache import caches

    caches["renditions"].clear()


@pytest.fixture
def worker_heartbeat():
    write_worker_heartbeat()
