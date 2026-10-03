"""Demo only (user asked 2026-10-03): take the picture off every other demo
user (even IDs) so the 默认头像 pool shows. The pictures stay in the media
library; the old picture of each user goes to /tmp/avatars_removed.json so
it can be put back."""

import json

from accounts.models import User

removed = {}
for user in User.objects.filter(is_active=True).exclude(avatar=None).order_by("pk"):
    if user.pk % 2 == 0:
        removed[user.pk] = user.avatar_id
        user.avatar = None
        user.save(update_fields=["avatar"])  # signals regenerate their pages

with open("/tmp/avatars_removed.json", "w") as handle:
    json.dump(removed, handle)
print("removed", len(removed), "| with picture", User.objects.exclude(avatar=None).count(),
      "| without", User.objects.filter(avatar=None).count())
