"""Delete data past its retention window (design 16.5, 每天 04:00).

Retention comes from design 12.10.2 / 12.10.3 / 16.5:
API call logs 90 days, webhook deliveries 180 days, finished task records
30 days, plus expired sessions.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

API_LOG_DAYS = 90
WEBHOOK_DAYS = 180
TASK_DAYS = 30


class Command(BaseCommand):
    help = "清理过期的调用日志、Webhook 记录、任务记录和会话（设计 16.5）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计不删除。",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        counts = {}

        for label, queryset in self.targets(now):
            total = queryset.count()
            if total and not dry_run:
                queryset.delete()
            counts[label] = total

        counts["过期会话"] = self.clear_sessions(dry_run)

        prefix = "将删除" if dry_run else "已删除"
        for label, total in counts.items():
            self.stdout.write(f"{prefix} {label}：{total}")
        return None

    def targets(self, now):
        from django.utils import timezone as tz

        from integrations.models import ApiRequestLog, DeliveryStatus, WebhookDelivery

        yield (
            f"API 调用日志（{API_LOG_DAYS} 天前）",
            ApiRequestLog.objects.filter(
                created_at__lt=now - tz.timedelta(days=API_LOG_DAYS)
            ),
        )
        yield (
            f"Webhook 投递记录（{WEBHOOK_DAYS} 天前）",
            WebhookDelivery.objects.filter(
                created_at__lt=now - tz.timedelta(days=WEBHOOK_DAYS)
            ).exclude(status=DeliveryStatus.PENDING),
        )
        yield (f"已完成的任务记录（{TASK_DAYS} 天前）", self.finished_tasks(now))

    @staticmethod
    def finished_tasks(now):
        from django.utils import timezone as tz
        from django_tasks_db.models import DBTaskResult

        cutoff = now - tz.timedelta(days=TASK_DAYS)
        return DBTaskResult.objects.filter(
            status__in=["SUCCESSFUL", "FAILED"], finished_at__lt=cutoff
        )

    @staticmethod
    def clear_sessions(dry_run):
        from django.contrib.sessions.models import Session

        expired = Session.objects.filter(expire_date__lt=timezone.now())
        total = expired.count()
        if total and not dry_run:
            expired.delete()
        return total
