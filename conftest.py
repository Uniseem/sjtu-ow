import pytest
from django.core.management import call_command

from core.worker import write_worker_heartbeat


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("createcachetable", verbosity=0)


@pytest.fixture(autouse=True)
def _forget_renditions():
    """The thumbnail cache lives in memory across tests, while the images
    behind it roll back with each test and their ids come round again."""
    from django.core.cache import caches

    caches["renditions"].clear()


@pytest.fixture
def worker_heartbeat():
    write_worker_heartbeat()
