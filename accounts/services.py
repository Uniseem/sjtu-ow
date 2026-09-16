"""Account helpers: SJTU / off-campus group membership."""

from django.contrib.auth.models import Group

GROUP_SJTU = "交大用户"
GROUP_EXTERNAL = "校外用户"


def ensure_user_groups() -> tuple[Group, Group]:
    """Create the two automatic groups if they are missing."""
    sjtu, _ = Group.objects.get_or_create(name=GROUP_SJTU)
    external, _ = Group.objects.get_or_create(name=GROUP_EXTERNAL)
    return sjtu, external


def sync_sjtu_groups(user) -> None:
    """Assign 交大用户 or 校外用户 from is_sjtu; leave other groups alone."""
    if user.pk is None:
        return
    sjtu, external = ensure_user_groups()
    if user.is_sjtu:
        user.groups.add(sjtu)
        user.groups.remove(external)
    else:
        user.groups.add(external)
        user.groups.remove(sjtu)
