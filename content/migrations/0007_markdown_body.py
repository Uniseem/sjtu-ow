"""Article and page bodies become Markdown (design 5.2, v6.70).

The StreamField is renamed out of the way, a text field takes its name, and
every body is converted: the live rows and each saved revision (drafts and
scheduled versions open in the editor from the latest revision, which would
otherwise be a string of JSON).
"""

import json

from django.core.files.storage import default_storage
from django.db import migrations, models

MODELS = ("articlepage", "standardpage")


def _resolvers(apps):
    Page = apps.get_model("wagtailcore", "Page")
    Site = apps.get_model("wagtailcore", "Site")
    Image = apps.get_model("wagtailimages", "Image")
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    root = Page.objects.filter(pk=site.root_page_id).first() if site else None
    root_path = root.url_path if root else "/"

    def number(value):
        text = str(value or "")
        return int(text) if text.isdigit() and len(text) < 19 else None

    def link_for(attrs):
        if attrs.get("linktype") != "page":
            return ""
        page = Page.objects.filter(pk=number(attrs.get("id"))).first()
        if page is None or not page.url_path.startswith(root_path):
            return ""
        return "/" + page.url_path[len(root_path) :]

    def image_for(attrs):
        image = Image.objects.filter(pk=number(attrs.get("id"))).first()
        return default_storage.url(image.file.name) if image and image.file else ""

    return link_for, image_for


def to_markdown(apps, schema_editor):
    from content.legacy_body import from_stream

    link_for, image_for = _resolvers(apps)
    ContentType = apps.get_model("contenttypes", "ContentType")
    Revision = apps.get_model("wagtailcore", "Revision")
    for name in MODELS:
        Model = apps.get_model("content", name)
        for page in Model.objects.all():
            raw = page.body_stream.raw_data if page.body_stream else []
            page.body = from_stream(list(raw), link_for, image_for)
            page.save(update_fields=["body"])
        kinds = ContentType.objects.filter(app_label="content", model=name)
        for revision in Revision.objects.filter(content_type__in=kinds):
            content = revision.content or {}
            if "body" not in content:
                continue
            content["body"] = from_stream(content["body"], link_for, image_for)
            revision.content = content
            revision.save(update_fields=["content"])


def to_stream(apps, schema_editor):
    """Back: each body as one paragraph of its rendered HTML."""
    from content.markdown import render

    def stream(text):
        return [{"type": "paragraph", "value": str(render(text))}] if text else []

    ContentType = apps.get_model("contenttypes", "ContentType")
    Revision = apps.get_model("wagtailcore", "Revision")
    for name in MODELS:
        Model = apps.get_model("content", name)
        for page in Model.objects.all():
            page.body_stream = stream(page.body)
            page.save(update_fields=["body_stream"])
        kinds = ContentType.objects.filter(app_label="content", model=name)
        for revision in Revision.objects.filter(content_type__in=kinds):
            content = revision.content or {}
            if isinstance(content.get("body"), str):
                content["body"] = json.dumps(stream(content["body"]))
                revision.content = content
                revision.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0006_retire_stock_workflow"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("wagtailcore", "0098_apitoken"),
        ("wagtailimages", "0027_image_description"),
    ]

    operations = [
        migrations.RenameField("articlepage", "body", "body_stream"),
        migrations.RenameField("standardpage", "body", "body_stream"),
        migrations.AddField(
            model_name="articlepage",
            name="body",
            field=models.TextField(blank=True, default="", verbose_name="正文"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="standardpage",
            name="body",
            field=models.TextField(blank=True, default="", verbose_name="正文"),
            preserve_default=False,
        ),
        migrations.RunPython(to_markdown, to_stream),
        migrations.RemoveField("articlepage", "body_stream"),
        migrations.RemoveField("standardpage", "body_stream"),
    ]
