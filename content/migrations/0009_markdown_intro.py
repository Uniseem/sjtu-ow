"""The news section's introduction becomes Markdown (v7.0, round 196), as
the bodies did in 0007: the live rows and every saved revision."""

from django.db import migrations, models


def to_markdown(apps, schema_editor):
    from content.legacy_body import from_html

    ContentType = apps.get_model("contenttypes", "ContentType")
    Revision = apps.get_model("wagtailcore", "Revision")
    Index = apps.get_model("content", "ArticleIndexPage")
    for page in Index.objects.all():
        page.intro = from_html(page.intro or "")
        page.save(update_fields=["intro"])
    kinds = ContentType.objects.filter(app_label="content", model="articleindexpage")
    for revision in Revision.objects.filter(content_type__in=kinds):
        content = revision.content or {}
        if isinstance(content.get("intro"), str):
            content["intro"] = from_html(content["intro"])
            revision.content = content
            revision.save(update_fields=["content"])


def to_html(apps, schema_editor):
    from content.markdown import render

    Index = apps.get_model("content", "ArticleIndexPage")
    for page in Index.objects.all():
        page.intro = str(render(page.intro or ""))
        page.save(update_fields=["intro"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0008_publish_without_review"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("wagtailcore", "0098_apitoken"),
    ]

    operations = [
        migrations.AlterField(
            model_name="articleindexpage",
            name="intro",
            field=models.TextField(blank=True, verbose_name="栏目介绍"),
        ),
        migrations.RunPython(to_markdown, to_html),
    ]
