"""Round 174: the admin's user list cannot delete people or switch them off
in bulk (design 3.7, v6.58). Before, Wagtail's bulk 「删除」 deleted a user
outright. Since v7.0 that list is Wagtail's own admin under /wagtail/, for
superusers; the back office's user list has no bulk actions at all."""

import pytest
from django.core.management import call_command

from accounts.models import User


@pytest.fixture
def root_and_member(db):
    from core.tests.test_chapter15_audit import _verified, make_user

    call_command("init_site", verbosity=0)
    root = _verified(make_user(1))
    root.is_superuser = True
    root.is_staff = True
    root.save()
    return root, _verified(make_user(2))


def test_only_assigning_roles_is_left(client, root_and_member):
    root, _member = root_and_member
    client.force_login(root)
    html = client.get("/wagtail/users/").content.decode()
    assert "/wagtail/bulk/accounts/user/assign_role/" in html
    assert "/wagtail/bulk/accounts/user/delete/" not in html
    assert "/wagtail/bulk/accounts/user/set_active_state/" not in html
    ours = client.get("/admin/users/").content.decode()
    assert "/bulk/" not in ours


def test_the_addresses_do_nothing(client, root_and_member):
    root, member = root_and_member
    client.force_login(root)
    for action, data in (
        ("delete", {}),
        ("set_active_state", {"mark_as_active": "False"}),
    ):
        url = f"/wagtail/bulk/accounts/user/{action}/?id={member.pk}"
        assert client.get(url).status_code == 404
        assert client.post(url, data).status_code == 404
    member = User.objects.get(pk=member.pk)  # still there
    assert member.is_active
