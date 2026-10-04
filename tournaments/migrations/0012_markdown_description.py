"""Tournament descriptions become Markdown (design 8.1, v6.70); the rich
text kept until now is converted (content.legacy_body)."""

from django.db import migrations, models


def to_markdown(apps, schema_editor):
    from content.legacy_body import from_html

    Tournament = apps.get_model("tournaments", "Tournament")
    for tournament in Tournament.objects.exclude(description=""):
        tournament.description = from_html(tournament.description)
        tournament.save(update_fields=["description"])


def to_html(apps, schema_editor):
    from content.markdown import render

    Tournament = apps.get_model("tournaments", "Tournament")
    for tournament in Tournament.objects.exclude(description=""):
        tournament.description = str(render(tournament.description))
        tournament.save(update_fields=["description"])


class Migration(migrations.Migration):
    dependencies = [
        ("tournaments", "0011_participant_contact"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tournament",
            name="description",
            field=models.TextField(blank=True, verbose_name="详细说明"),
        ),
        migrations.RunPython(to_markdown, to_html),
    ]
