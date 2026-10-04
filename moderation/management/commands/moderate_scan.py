"""Put existing content on record for the AI patrol (design 5.5.4 全量扫描,
v6.72): the patrols read it over the next rounds, within the daily cap."""

from django.core.management.base import BaseCommand

from moderation import integrations, services
from moderation.models import ModerationItem


class Command(BaseCommand):
    help = (
        "把现有内容记进 AI 巡查的待看列表，之后每 30 分钟的巡查陆续看完。"
        "去重和每日上限照常生效。"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--what",
            choices=["all", *integrations.SCAN_KINDS],
            default="all",
        )
        parser.add_argument("--limit", type=int, default=0, help="最多送审多少条")

    def handle(self, *args, **options):
        if not services.is_enabled():
            self.stdout.write(self.style.NOTICE("AI 审核在后台是关闭的，未做任何事。"))
            return

        submitted = integrations.scan_existing(options["what"], options["limit"])

        pending = ModerationItem.objects.filter(checked_at__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"已记下 {submitted} 条（含此前已存在的记录，不会重复送审）；"
                f"等巡查看的 {pending} 条，今天剩余额度 {services.quota_left()}"
            )
        )
