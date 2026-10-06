"""Round 213, B3: the per-image edit/delete guards, tested with the role they
actually protect against (design 14.x; until now only superusers were tested,
so deleting the guards turned nothing red).

The 投稿者 group may add to and choose from 「投稿图片」; Wagtail's ownership
rule lets them change and delete their own uploads there. Changing or
deleting *someone else's* picture rests entirely on the two `if`s in
backoffice/views/images.py.
"""

import pytest
from django.core.management import call_command
from django.urls import reverse
from wagtail.images import get_image_model
from wagtail.models import Collection

from accounts.tests.test_onboarding import _user
from backoffice.tests.test_backoffice import _png
from content.services import SUBMISSION_IMAGE_COLLECTION


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.mark.django_db
def test_a_submitter_cannot_edit_or_delete_anothers_image(
    site, client, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    author = _user("imga213@example.com", "投稿者")
    stranger = _user("imgb213@example.com", "投稿者")
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    image = get_image_model().objects.create(
        title="作者的图",
        file=_png(),
        collection=collection,
        uploaded_by_user=author,
    )
    edit = reverse("backoffice:image_edit", args=[image.pk])
    delete = reverse("backoffice:image_delete", args=[image.pk])

    client.force_login(stranger)
    assert client.get(edit).status_code == 403
    tamper = client.post(edit, {"title": "偷改", "collection": str(collection.pk)})
    assert tamper.status_code == 403
    assert client.post(delete).status_code == 403
    image.refresh_from_db()
    assert image.title == "作者的图"

    # One's own upload is editable (the ownership rule, unchanged).
    client.force_login(author)
    assert client.get(edit).status_code == 200
