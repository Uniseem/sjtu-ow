"""Generate, list or clear the static pages (design 13.13.4, 13.13.6)."""

from django.core.management.base import BaseCommand

from core import prerender
from core.models import PrerenderedPage


class Command(BaseCommand):
    help = "生成预渲染页面。默认全量生成，供每日兜底和升级后使用。"

    def add_arguments(self, parser):
        parser.add_argument("--path", help="只生成这一个路径，比如 /news/hello/")
        parser.add_argument("--clear", action="store_true", help="清空全部静态文件")
        parser.add_argument("--list", action="store_true", help="列出已记录的页面")
        parser.add_argument(
            "--force",
            action="store_true",
            help="PRERENDER_ENABLED 为关时也执行",
        )

    def handle(self, *args, **options):
        if not prerender.is_enabled() and not options["force"]:
            self.stdout.write(
                self.style.NOTICE(
                    "PRERENDER_ENABLED 为关，未做任何事。加 --force 可强制执行。"
                )
            )
            return

        if options["list"]:
            for record in PrerenderedPage.objects.all():
                line = (
                    f"{record.path:<40} {record.get_status_display():<6} "
                    f"{record.bytes:>8} 字节  {record.generated_at or '-'}"
                )
                self.stdout.write(line)
                if record.error:
                    self.stdout.write(self.style.ERROR(f"    {record.error}"))
            return

        if options["clear"]:
            count = prerender.clear_all()
            self.stdout.write(
                self.style.SUCCESS(f"已清空静态文件（原有 {count} 个页面记录）")
            )
            return

        if options["path"]:
            record = prerender.generate(options["path"])
            if record.status == PrerenderedPage.Status.READY:
                self.stdout.write(
                    self.style.SUCCESS(f"已生成 {record.path}（{record.bytes} 字节）")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"失败 {record.path}：{record.error}")
                )
            return

        stats = prerender.generate_all()
        self.stdout.write(
            self.style.SUCCESS(
                f"全量生成完成：成功 {stats['generated']}，失败 {stats['failed']}，"
                f"删除 {stats['removed']}；目录占用 "
                f"{prerender.disk_usage() // 1024} KB"
            )
        )
