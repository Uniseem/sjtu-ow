"""Send existing content through AI review (design 5.5.4 全量扫描)."""

from django.core.management.base import BaseCommand

from moderation import integrations, services
from moderation.models import ModerationItem


class Command(BaseCommand):
    help = "对现有内容发起一次 AI 审核扫描。去重和每日上限照常生效。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--what",
            choices=["all", "nicknames", "pages"],
            default="all",
        )
        parser.add_argument("--limit", type=int, default=0, help="最多送审多少条")
        parser.add_argument("--digest", action="store_true", help="改为发送每日汇总")

    def handle(self, *args, **options):
        if options["digest"]:
            from moderation.notifications import send_digest

            count = send_digest()
            self.stdout.write(self.style.SUCCESS(f"汇总邮件已排队，包含 {count} 条"))
            return

        if not services.is_enabled():
            self.stdout.write(self.style.NOTICE("AI 审核在后台是关闭的，未做任何事。"))
            return

        limit = options["limit"]
        submitted = 0
        if options["what"] in ("all", "nicknames"):
            from accounts.models import User

            for user in User.objects.filter(is_active=True).order_by("pk"):
                if limit and submitted >= limit:
                    break
                if integrations.submit_nickname(user) is not None:
                    submitted += 1

        if options["what"] in ("all", "pages"):
            from content.models import ArticlePage, StandardPage

            for model in (ArticlePage, StandardPage):
                for page in model.objects.live().order_by("pk"):
                    if limit and submitted >= limit:
                        break
                    if integrations.submit_page(page) is not None:
                        submitted += 1

        pending = ModerationItem.objects.filter(checked_at__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"已提交 {submitted} 条（含此前已存在的记录，不会重复送审）；"
                f"当前待审 {pending} 条，今天剩余额度 {services.quota_left()}"
            )
        )
