"""Round 208 (design 13.2, v7.12): the site is called SJTU-OW.

User 10-05: 「站点名称使用 SJTU-OW」, everywhere a name is used. Sentences
that say what it is stay (the footer, the default description, the line
under the name in a letter's head).
"""

import importlib
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from wagtail.models import Site

OLD_NAMES = ("上海交通大学守望先锋社区", "交大守望先锋", "SJTU OW", "SJTU 守望先锋社区")
# A made-up tournament on the specimen page, not the site's name.
ALLOWED = ("2026 秋季交大守望先锋杯",)
SKIP_PARTS = {
    ".venv",
    ".git",
    "node_modules",
    "handoff",
    "docs",
    "migrations",
    "tests",
    # Made by the site, not written: pages rendered earlier, uploads, data.
    "prerendered",
    "media",
    "data",
    "backups",
    "staticfiles",
}


def _sources():
    root = Path(settings.BASE_DIR)
    for suffix in ("*.html", "*.txt", "*.py", "*.webmanifest", "*.js"):
        for path in root.rglob(suffix):
            if SKIP_PARTS & set(path.relative_to(root).parts):
                continue
            yield path


def test_no_old_name_is_left():
    found = []
    for path in _sources():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for allowed in ALLOWED:
            text = text.replace(allowed, "")
        found += [f"{path.name}: {name}" for name in OLD_NAMES if name in text]
    assert found == []


def test_every_page_title_ends_with_the_name():
    root = Path(settings.BASE_DIR)
    titles = []
    for path in root.rglob("*.html"):
        if SKIP_PARTS & set(path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8")
        titles += re.findall(r"\{% block title %\}(.*?)\{% endblock %\}", text, re.S)
    named = [title for title in titles if "·" in title]
    assert len(named) > 20
    assert all(title.rstrip().endswith("· SJTU-OW") for title in named), [
        title for title in named if not title.rstrip().endswith("· SJTU-OW")
    ]


@pytest.mark.django_db
def test_the_pages_letters_and_settings_say_sjtu_ow(client):
    from core.letters import Letter, render
    from core.mail import get_from_email, get_subject_prefix
    from core.models import SiteSettings

    call_command("init_site", verbosity=0)
    html = client.get("/").content.decode()
    assert '<span class="c-brand__name">SJTU-OW</span>' in html
    assert re.search(r"<title>[^<]*SJTU-OW</title>", html)
    assert 'property="og:site_name" content="SJTU-OW"' in html
    assert 'class="c-hero__title"><span>SJTU-</span><span>OW</span>' in html
    assert "SJTU-OW 是上海交通大学守望先锋玩家的社团网站" in html  # says what it is
    text, letter_html = render(Letter(subject="主题", lead="正文"), "某人")
    assert "\nSJTU-OW\n" in text and ">SJTU-OW</a>" in letter_html
    site = SiteSettings.load()
    site.from_address = "ow@example.com"
    site.save()
    sender = get_from_email()
    assert sender.startswith("SJTU-OW") and sender.endswith("<ow@example.com>")
    assert get_subject_prefix() == "[SJTU-OW]"
    assert Site.objects.get(is_default_site=True).site_name == "SJTU-OW"


@pytest.mark.django_db
def test_stored_old_defaults_follow_and_changed_ones_stay():
    from django.apps import apps

    from core.models import SiteSettings

    migration = importlib.import_module("core.migrations.0024_site_name_sjtu_ow")
    site = SiteSettings.load()
    SiteSettings.objects.filter(pk=site.pk).update(
        from_name="SJTU 守望先锋社区", email_subject_prefix="[我们社团]"
    )
    migration.forwards(apps, None)
    site.refresh_from_db()
    assert site.from_name == "SJTU-OW"
    assert site.email_subject_prefix == "[我们社团]"  # the owner's own, kept
