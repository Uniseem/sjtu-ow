"""Tournaments keep the plain text of the description on the row, read off
at save time (design 12.8.1, v7.14); existing rows are filled in here."""

from django.db import migrations, models


def backfill(apps, schema_editor):
    from content.markdown import plain_text

    Tournament = apps.get_model("tournaments", "Tournament")
    for tournament in Tournament.objects.all().iterator():
        tournament.description_plain = plain_text(tournament.description)
        tournament.save(update_fields=["description_plain"])


class Migration(migrations.Migration):

    dependencies = [
        ("tournaments", "0014_times_while_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="description_plain",
            field=models.TextField(blank=True, verbose_name="详细说明纯文本"),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
