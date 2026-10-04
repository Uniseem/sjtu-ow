"""Faces show as soon as they are uploaded (design-details 2.3, v6.73).
Whatever was still waiting for review when this shipped goes up now."""

from django.db import migrations
from django.utils import timezone


def forwards(apps, schema_editor):
    AvatarSubmission = apps.get_model("accounts", "AvatarSubmission")
    now = timezone.now()
    waiting = AvatarSubmission.objects.filter(status="pending").select_related("user")
    for submission in waiting.order_by("created_at"):
        if submission.image_id is None:
            submission.status = "withdrawn"
            submission.save(update_fields=["status"])
            continue
        submission.status = "approved"
        submission.reviewed_at = now
        submission.save(update_fields=["status", "reviewed_at"])
        user = submission.user
        user.avatar_id = submission.image_id
        user.save(update_fields=["avatar"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0008_user_accepts_announcements"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
