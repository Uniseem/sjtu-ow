"""Articles keep their plain text, word count and reading time on the row,
read off at save time (design 12.5.1, v7.14); the rows that already exist
are filled in here (each body is parsed once, dead b23 links cost one lookup
each thanks to the failure cache in content.embeds)."""

from django.db import migrations, models


def backfill(apps, schema_editor):
    from content.article_meta import stored_counts

    ArticlePage = apps.get_model("content", "ArticlePage")
    for page in ArticlePage.objects.all().iterator():
        plain, words, minutes = stored_counts(page.body)
        page.body_plain = plain
        page.body_words = words
        page.body_minutes = minutes
        page.save(update_fields=["body_plain", "body_words", "body_minutes"])


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0011_article_category_while_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="articlepage",
            name="body_minutes",
            field=models.PositiveIntegerField(default=1, verbose_name="阅读分钟数"),
        ),
        migrations.AddField(
            model_name="articlepage",
            name="body_plain",
            field=models.TextField(blank=True, verbose_name="正文纯文本"),
        ),
        migrations.AddField(
            model_name="articlepage",
            name="body_words",
            field=models.PositiveIntegerField(default=0, verbose_name="字数"),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
