"""``manage.py scrub_originals`` (219): the pictures stored before the pipeline
existed lose what the camera wrote, once, and nothing else changes."""

import io
from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from PIL import Image
from wagtail.images import get_image_model
from wagtail.models import Collection

from accounts.tests.test_onboarding import _user
from content.services import SUBMISSION_IMAGE_COLLECTION, TEAM_LOGO_COLLECTION
from core.tests.test_upload_pipeline import SECRET_MAKER, _jpeg, _png
from teams import services


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _old_picture(collection, name="IMG_old.jpg", data=None):
    """Stored the way it was before 219: the file as it came."""
    return get_image_model().objects.create(
        title=name,
        file=ContentFile(data or _jpeg((300, 200), orientation=6), name=name),
        collection=collection,
    )


def _run(*args):
    out, err = StringIO(), StringIO()
    call_command("scrub_originals", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


def _stored(image):
    image.refresh_from_db()
    image.file.open("rb")
    try:
        return image.file.read()
    finally:
        image.file.close()


@pytest.mark.django_db
def test_a_dry_run_lists_and_changes_nothing(site):
    image = _old_picture(Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION))
    before = (image.file.name, _stored(image))
    out, _ = _run("--dry-run")
    assert "含 GPS" in out and f"#{image.pk}" in out
    assert (image.file.name, _stored(image)) == before


@pytest.mark.django_db
def test_the_original_is_rewritten_without_the_camera_notes(site):
    image = _old_picture(Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION))
    old_name = image.file.name
    assert SECRET_MAKER.encode() in _stored(image)

    out, _ = _run()

    stored = _stored(image)
    assert SECRET_MAKER.encode() not in stored
    picture = Image.open(io.BytesIO(stored))
    assert picture.format == "WEBP" and not picture.getexif().get_ifd(0x8825)
    assert picture.size == (200, 300) == (image.width, image.height)
    assert image.file.name != old_name and not default_storage.exists(old_name)
    assert default_storage.exists(image.file.name)
    assert image.file_size == len(stored) and "已重新编码" in out


@pytest.mark.django_db
def test_a_clean_picture_and_the_clubs_own_library_are_left_alone(site):
    submissions = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    clean = _old_picture(submissions, "clean.png", _png())
    official = _old_picture(Collection.get_first_root_node(), "official.jpg")
    names = (clean.file.name, official.file.name)
    out, _ = _run()
    clean.refresh_from_db()
    official.refresh_from_db()
    assert (clean.file.name, official.file.name) == names
    assert SECRET_MAKER.encode() in _stored(official)
    assert "本来就干净" in out
    _run("--all")
    assert SECRET_MAKER.encode() not in _stored(official)


@pytest.mark.django_db
def test_a_team_logo_in_the_shared_collection_is_cleaned_and_moves(site):
    captain = _user("scrub-captain@example.com")
    logo = _old_picture(Collection.get_first_root_node(), "old-logo.jpg")
    team = services.create_team(user=captain, name="旧队标队", logo=logo)

    _run()

    logo.refresh_from_db()
    assert logo.collection.name == TEAM_LOGO_COLLECTION
    assert SECRET_MAKER.encode() not in _stored(logo)
    team.refresh_from_db()
    assert team.logo_id == logo.pk


@pytest.mark.django_db
def test_a_picture_it_cannot_read_is_reported_and_the_rest_carry_on(site):
    submissions = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    broken = _old_picture(submissions, "broken.jpg")
    # The file on the disk went bad after the row was made.
    default_storage.delete(broken.file.name)
    default_storage.save(broken.file.name, ContentFile(b"not a picture any more"))
    good = _old_picture(submissions, "good.jpg")
    out, err = _run()
    assert f"#{broken.pk}" in err
    assert SECRET_MAKER.encode() not in _stored(good) and f"#{good.pk}" in out
