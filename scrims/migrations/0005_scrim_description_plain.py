"""Scrims keep the plain text of the description on the row, read off at
save time (design 12.9.1, v7.14); existing rows are filled in here."""

from django.db import migrations, models


def backfill(apps, schema_editor):
    from content.markdown import plain_text

    Scrim = apps.get_model("scrims", "Scrim")
    for scrim in Scrim.objects.all().iterator():
        scrim.description_plain = plain_text(scrim.description)
        scrim.save(update_fields=["description_plain"])


class Migration(migrations.Migration):

    dependencies = [
        ("scrims", "0004_start_while_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="scrim",
            name="description_plain",
            field=models.TextField(blank=True, verbose_name="说明纯文本"),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
