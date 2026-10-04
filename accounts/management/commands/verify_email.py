"""Mark one account's email as verified from the server (design 3.1, v6.63):
for when mail is broken and someone cannot receive their code."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.services import trust_email


class Command(BaseCommand):
    help = "把一个账号的邮箱标成已验证（收不到验证码时用），不发邮件。"

    def add_arguments(self, parser):
        parser.add_argument("email", help="账号的登录邮箱")

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.filter(email__iexact=options["email"].strip()).first()
        if user is None:
            raise CommandError(f"没有用 {options['email']} 注册的账号。")
        trust_email(user)
        self.stdout.write(f"{user.email}（{user.nickname}）的邮箱已标成验证过。")
