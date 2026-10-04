"""The switch to Markdown, run backwards and forwards on real rows (round
192): content 0007 converts the live bodies and every saved revision,
tournaments 0012 the descriptions."""

import json
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from accounts.models import User
from content.markdown import render
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from tournaments.models import Tournament

BEFORE = [
    ("content", "0006_retire_stock_workflow"),
    ("tournaments", "0011_participant_contact"),
]
AFTER = [
    ("content", "0007_markdown_body"),
    ("tournaments", "0012_markdown_description"),
]


def _migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)


@pytest.mark.django_db(transaction=True)
def test_bodies_drafts_and_descriptions_survive_the_switch():
    call_command("init_site", verbosity=0)
    author = User.objects.create_user(
        email="mig@example.com",
        password="Correct-Horse-Battery-1",
        nickname="迁移",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    live_body = "开头 **加粗**\n\n## 一节\n\n- 甲\n- 乙\n\n第一行\n第二行"
    article = ArticlePage(
        title="迁移文章",
        slug="migrated",
        category=ArticleCategory.objects.get(slug="guide"),
        author=author,
        owner=author,
        body=live_body,
    )
    ArticleIndexPage.objects.get(slug="news").add_child(instance=article)
    article.save_revision().publish()
    article.body = "草稿里 *改过*"
    article.save_revision()  # an unpublished draft, opened from its revision
    now = timezone.now()
    tournament = Tournament.objects.create(
        registration_mode="team",
        title="迁移赛",
        description="## 赛制\n\n**双败**淘汰",
        registration_opens_at=now,
        registration_closes_at=now + timedelta(days=1),
        roster_min=2,
        roster_max=3,
    )
    try:
        _migrate(BEFORE)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT body FROM content_articlepage WHERE page_ptr_id = %s",
                [article.pk],
            )
            stream = json.loads(cursor.fetchone()[0])
            cursor.execute(
                "SELECT description FROM tournaments_tournament WHERE id = %s",
                [tournament.pk],
            )
            rich_text = cursor.fetchone()[0]
        assert stream[0]["type"] == "paragraph"
        assert "<strong>加粗</strong>" in stream[0]["value"]
        assert "<h2>赛制</h2>" in rich_text
        _migrate(AFTER)
    finally:
        call_command("migrate", verbosity=0)

    article = ArticlePage.objects.get(pk=article.pk)
    assert render(article.body) == render(live_body)
    draft = article.get_latest_revision().content["body"]
    assert render(draft) == render("草稿里 *改过*")
    tournament.refresh_from_db()
    assert render(tournament.description) == render("## 赛制\n\n**双败**淘汰")
