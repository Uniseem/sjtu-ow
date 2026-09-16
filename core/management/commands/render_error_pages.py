from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string


class Command(BaseCommand):
    help = (
        "Render database-free error pages to static HTML for Caddy. "
        "Commit the output under deploy/error_pages/; "
        "the image build does not run this."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default=str(Path(settings.BASE_DIR) / "deploy" / "error_pages"),
            help="Directory to write HTML files into.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"])
        output.mkdir(parents=True, exist_ok=True)
        pages = {
            "404.html": ("errors/404.html", {}),
            "403.html": ("errors/403.html", {"reason": "你没有权限查看这个页面。"}),
            "429.html": ("errors/429.html", {"retry_after": None}),
            "500.html": ("errors/500.html", {"request_id": ""}),
            "maintenance.html": ("errors/maintenance.html", {}),
        }
        for filename, (template, context) in pages.items():
            html = render_to_string(template, context)
            (output / filename).write_text(html, encoding="utf-8")
            self.stdout.write(f"Wrote {output / filename}")
