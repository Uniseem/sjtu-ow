from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

ERROR_CSS_PATH = Path(settings.BASE_DIR) / "static" / "css" / "error.css"


class Command(BaseCommand):
    help = (
        "Render the self-contained Caddy maintenance page. "
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
        inline_css = ERROR_CSS_PATH.read_text(encoding="utf-8")
        html = render_to_string(
            "errors/maintenance.html",
            {"error_css_inline": inline_css},
        )
        target = output / "maintenance.html"
        target.write_text(html, encoding="utf-8")
        self.stdout.write(f"Wrote {target}")
