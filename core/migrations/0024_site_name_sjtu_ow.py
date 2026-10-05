# Round 208 (design 13.2, v7.12): the site is called SJTU-OW. Stored values
# that are still the old defaults follow; ones the site owner changed stay.

from django.db import migrations, models

RENAMES = (
    ("core", "SiteSettings", "from_name", "SJTU 守望先锋社区", "SJTU-OW"),
    ("core", "SiteSettings", "email_subject_prefix", "[SJTU OW]", "[SJTU-OW]"),
    ("wagtailcore", "Site", "site_name", "上海交通大学守望先锋社区", "SJTU-OW"),
)


def forwards(apps, schema_editor):
    for app, model, field, old, new in RENAMES:
        apps.get_model(app, model).objects.filter(**{field: old}).update(**{field: new})


def backwards(apps, schema_editor):
    for app, model, field, old, new in RENAMES:
        apps.get_model(app, model).objects.filter(**{field: new}).update(**{field: old})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_heldletter'),
        ('wagtailcore', '0098_apitoken'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='email_subject_prefix',
            field=models.CharField(default='[SJTU-OW]', max_length=40, verbose_name='邮件主题前缀'),
        ),
        migrations.AlterField(
            model_name='sitesettings',
            name='from_name',
            field=models.CharField(default='SJTU-OW', max_length=100, verbose_name='发件人名称'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
