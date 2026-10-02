"""Split the SJTU emblem into the hero's two layers (design 13.2.5, v5.0).

Run after the emblem file changes and commit the two files. A test splits the
emblem again and fails if the committed layers are out of date.
"""

from django.core.management.base import BaseCommand

from core import emblem


class Command(BaseCommand):
    help = (
        "把交大校徽拆成首屏用的两层：齿轮和其余部分（static/img/sjtu-emblem-*.svg）。"
    )

    def handle(self, *args, **options):
        for name, content in emblem.render().items():
            emblem.static_file(name).write_text(content, encoding="utf-8", newline="\n")
            self.stdout.write(f"已生成 static/{name}")
