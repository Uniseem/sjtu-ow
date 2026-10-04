"""Django's createsuperuser, with the new account's email counted as verified
(design 3.1, v6.63).

Logging in needs a verified email, and a fresh site cannot send one until a
superuser signs in to set up the mail server. Whoever runs this on the
server is trusted anyway. ``accounts`` comes before ``django.contrib.auth`` in
INSTALLED_APPS, so this command replaces the stock one.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.management.commands import createsuperuser

from accounts.services import trust_email


class Command(createsuperuser.Command):
    def handle(self, *args, **options):
        User = get_user_model()
        database = options.get("database")
        before = set(
            User.objects.db_manager(database)
            .filter(is_superuser=True)
            .values_list("pk", flat=True)
        )
        super().handle(*args, **options)
        created = (
            User.objects.db_manager(database)
            .filter(is_superuser=True)
            .exclude(pk__in=before)
        )
        for user in created:
            trust_email(user)
            if options.get("verbosity", 1) >= 1:
                self.stdout.write(
                    f"{user.email} 已记为验证过的邮箱，可以直接登录后台"
                    "（还没配发信也能登录）。"
                )
