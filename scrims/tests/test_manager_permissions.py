"""Design 4.1: the scrim manager group can create scrims, pick players, split teams.

Until round 055 init_site never granted the group anything, so only superusers
could manage scrims. No test had opened the scrim admin as anyone else.
"""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from accounts.models import User
from accounts.services import GROUP_SCRIM
from scrims import services
from scrims.tests.test_scrims import make_scrim, make_user


@pytest.fixture
def scrim_manager(db):
    call_command("init_site", verbosity=0)
    user = make_user("scrim-manager@example.com", "内战管理员甲")
    user.groups.add(Group.objects.get(name=GROUP_SCRIM))
    # A fresh instance, so no permission cache from before the group was added.
    return User.objects.get(pk=user.pk)


def test_init_site_grants_the_scrim_permissions(scrim_manager):
    assert not scrim_manager.is_superuser
    for codename in services.SCRIM_PERMISSIONS:
        assert scrim_manager.has_perm(f"scrims.{codename}"), codename
    assert services.can_manage(scrim_manager)


def test_a_scrim_manager_can_open_the_scrim_admin(client, scrim_manager):
    scrim = make_scrim()
    client.force_login(scrim_manager)
    for url in (
        reverse("scrims:index"),
        reverse("scrims:add"),
        reverse("scrims:edit", args=[scrim.pk]),
        reverse("scrim_split", args=[scrim.pk]),
    ):
        response = client.get(url)
        assert response.status_code == 200, url


def test_scrim_managers_do_not_get_tournament_permissions(scrim_manager):
    assert not scrim_manager.has_perm("tournaments.change_tournament")
