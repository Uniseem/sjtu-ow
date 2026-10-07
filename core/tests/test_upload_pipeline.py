"""Every picture that comes in goes through core.uploads.clean_image (219).

217 review 07-1 (a broken EXIF block made every page showing the picture a
500), 07-2 / 02-3 (no pixel limit), 07-3 / 02-1 (the original, GPS and all, was
public), 07-4 (formats Pillow reads but has no MIME type for), 02-4 (no limit
on how many).
"""

import io
import json
import struct

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image, ImageOps, PngImagePlugin
from wagtail.images import get_image_model
from wagtail.models import Collection

from accounts.services import GROUP_SUBMITTER
from accounts.tests.test_onboarding import _user
from content.services import SUBMISSION_IMAGE_COLLECTION
from core import uploads
from core.uploads import UploadError, clean_image

SECRET_MAKER = "SecretPhoneMaker"


def _jpeg(size=(300, 200), *, orientation=1, gps=True) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = SECRET_MAKER
    exif[0x0112] = orientation
    if gps:
        place = exif.get_ifd(0x8825)
        place[1], place[2] = "N", (31.0, 1.0, 2.0)
        place[3], place[4] = "E", (121.0, 2.0, 3.0)
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def _png(size=(120, 90)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 80, 60)).save(buffer, "PNG")
    return buffer.getvalue()


def _broken_exif_png() -> bytes:
    """Decodes fine; only ``exif_transpose`` fails (216, A4; 217, 07-1)."""
    info = PngImagePlugin.PngInfo()
    info.add_text("Raw profile type exif", "\nexif\n    10\nzz-not-hex\n")
    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), "red").save(buffer, "PNG", pnginfo=info)
    return buffer.getvalue()


def _qoi() -> bytes:
    """A one-pixel QOI picture: Pillow opens it, and has no MIME type for it,
    so a file called .png got past the form's type check (07-4)."""
    header = b"qoif" + struct.pack(">IIBB", 1, 1, 3, 0)
    return header + b"\xfe\xc8\x1e\x1e" + b"\x00" * 7 + b"\x01"


def _file(data: bytes, name="photo.jpg") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data)


def _reopen(clean):
    clean.seek(0)
    return Image.open(io.BytesIO(clean.read()))


# --- the function ---------------------------------------------------------------


def test_nothing_the_camera_wrote_survives():
    data = _jpeg()
    assert SECRET_MAKER.encode() in data  # the input really carries it
    clean = clean_image(_file(data))
    clean.seek(0)
    stored = clean.read()
    assert SECRET_MAKER.encode() not in stored and b"Exif" not in stored
    picture = _reopen(clean)
    assert picture.format == "WEBP"
    assert not dict(picture.getexif()) and not picture.getexif().get_ifd(0x8825)


def test_the_picture_is_turned_upright_and_keeps_its_size():
    clean = clean_image(_file(_jpeg((300, 200), orientation=6)))
    assert (clean.width, clean.height) == (200, 300)
    assert _reopen(clean).size == (200, 300)


def test_the_name_is_random_and_not_the_visitors():
    first = clean_image(_file(_png(), "IMG_20261007_0930.png"))
    second = clean_image(_file(_png(), "IMG_20261007_0930.png"))
    assert first.name.endswith(".webp") and "IMG_2026" not in first.name
    assert first.name != second.name


def test_a_long_side_is_shrunk_and_a_small_picture_left_alone():
    big = clean_image(_file(_png((900, 300))), max_side=400)
    assert (big.width, big.height) == (400, 133)
    small = clean_image(_file(_png((120, 90))), max_side=400)
    assert (small.width, small.height) == (120, 90)


def test_a_broken_exif_block_is_a_refusal_and_never_another_error():
    with pytest.raises(UploadError, match="读不出"):
        clean_image(_file(_broken_exif_png(), "broken.png"))


def test_too_many_pixels_is_refused_before_anything_is_decoded(monkeypatch):
    picture = _file(_png((100, 100)))

    def no_decoding(self, *args, **kwargs):
        raise AssertionError("the picture was decoded")

    monkeypatch.setattr(Image.Image, "load", no_decoding)
    with pytest.raises(UploadError, match="太大"):
        clean_image(picture, max_pixels=5_000)


@pytest.mark.parametrize(
    "name, data",
    [
        ("anim.gif", None),
        ("flat.bmp", None),
        ("one.png", _qoi()),
        ("text.png", b"not a picture at all"),
        ("empty.jpg", b""),
    ],
)
def test_only_jpeg_png_and_webp_by_what_the_file_is(name, data):
    if data is None:
        buffer = io.BytesIO()
        Image.new("RGB", (30, 30)).save(buffer, name.rsplit(".", 1)[1].upper())
        data = buffer.getvalue()
    with pytest.raises(UploadError):
        clean_image(_file(data, name))


def test_an_animation_keeps_its_first_frame():
    frames = [Image.new("RGB", (64, 64), color) for color in ((255, 0, 0), (0, 0, 255))]
    buffer = io.BytesIO()
    frames[0].save(
        buffer, "WEBP", save_all=True, append_images=frames[1:], duration=100, loop=0
    )
    clean = clean_image(_file(buffer.getvalue(), "anim.webp"))
    picture = _reopen(clean)
    assert getattr(picture, "n_frames", 1) == 1
    assert ImageOps.exif_transpose(picture).convert("RGB").getpixel((1, 1))[0] > 200


def test_a_cleaned_picture_is_not_cleaned_twice():
    clean = clean_image(_file(_jpeg()))
    assert clean_image(clean) is clean


@pytest.mark.django_db
def test_the_daily_count_by_who_is_uploading(monkeypatch):
    call_command("init_site", verbosity=0)
    monkeypatch.setattr(uploads, "UPLOADS_PER_DAY", 3)
    monkeypatch.setattr(uploads, "EDITOR_UPLOADS_PER_DAY", 5)
    member = _user("member219@example.com", GROUP_SUBMITTER)
    editor = _user("editor219@example.com", "内容编辑")
    root = _user("root219@example.com")
    root.is_superuser = True
    root.save()
    assert [uploads.over_daily_limit(member) for _ in range(4)] == [
        False,
        False,
        False,
        True,
    ]
    assert [uploads.over_daily_limit(editor) for _ in range(6)] == [False] * 5 + [True]
    assert not any(uploads.over_daily_limit(root) for _ in range(50))


# --- the doors ------------------------------------------------------------------


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _stored_bytes(image) -> bytes:
    image.file.open("rb")
    try:
        return image.file.read()
    finally:
        image.file.close()


def _assert_clean_original(image):
    stored = _stored_bytes(image)
    assert SECRET_MAKER.encode() not in stored and b"Exif" not in stored
    picture = Image.open(io.BytesIO(stored))
    assert picture.format == "WEBP" and not picture.getexif().get_ifd(0x8825)
    assert "IMG_" not in image.file.name


@pytest.mark.django_db
def test_the_back_office_upload_stores_a_clean_original(site, client):
    member = _user("door1-219@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    client.post(
        reverse("backoffice:image_upload"),
        {"collection": collection.pk, "files": [_file(_jpeg(), "IMG_0001.jpg")]},
    )
    image = get_image_model().objects.get()
    assert image.title == "IMG_0001"  # what the person called it stays the title
    _assert_clean_original(image)


@pytest.mark.django_db
def test_the_dialog_upload_stores_a_clean_original(site, client):
    member = _user("door2-219@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    response = client.post(
        reverse("backoffice:image_chooser_upload"),
        {"collection": collection.pk, "file": _file(_jpeg(), "IMG_0002.jpg")},
    )
    assert response.status_code == 200
    _assert_clean_original(get_image_model().objects.get())


@pytest.mark.django_db
def test_the_markdown_editors_picture_button_stores_a_clean_original(site, client):
    author = _user("door3-219@example.com", GROUP_SUBMITTER)
    client.force_login(author)
    response = client.post(
        reverse("content_markdown_image"),
        {"image": _file(_jpeg(), "IMG_0003.jpg")},
    )
    assert response.status_code == 200 and json.loads(response.content)["url"]
    _assert_clean_original(get_image_model().objects.get())


@pytest.mark.django_db
def test_wagtails_own_image_form_is_the_safe_one(site, client):
    """/wagtail/images/ is the superusers' fallback, and shares the form."""
    from wagtail.images.forms import get_image_form

    root = _user("door4-219@example.com")
    root.is_superuser = True
    root.is_staff = True
    root.save()
    form = get_image_form(get_image_model())(
        data={"title": "wagtail", "collection": Collection.get_first_root_node().pk},
        files={"file": _file(_jpeg(), "IMG_0004.jpg")},
        user=root,
        instance=get_image_model()(uploaded_by_user=root),
    )
    assert form.is_valid(), form.errors
    _assert_clean_original(form.save())


@pytest.mark.django_db
@pytest.mark.parametrize(
    "data, name, message",
    [
        (_broken_exif_png(), "broken.png", "读不出"),
        (_qoi(), "one.png", "one.png"),
    ],
)
def test_a_bad_file_is_a_message_in_the_back_office_never_a_500(
    site, client, data, name, message
):
    member = _user("bad219@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    response = client.post(
        reverse("backoffice:image_upload"),
        {"collection": collection.pk, "files": [_file(data, name)]},
        follow=True,
    )
    assert response.status_code == 200
    # The page names the file and says why; for QOI the wording is Wagtail's
    # own, which refuses it before ours would.
    assert message in response.content.decode()
    assert not get_image_model().objects.exists()


@pytest.mark.django_db
def test_wagtails_pixel_limit_is_ours(settings):
    assert settings.WAGTAILIMAGES_MAX_IMAGE_PIXELS == uploads.MAX_PIXELS
    assert settings.WAGTAILIMAGES_IMAGE_FORM_BASE == "core.image_forms.SafeImageForm"


@pytest.mark.django_db
def test_editing_a_picture_without_a_new_file_does_not_touch_the_file(site, client):
    member = _user("edit219@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    client.post(
        reverse("backoffice:image_upload"),
        {"collection": collection.pk, "files": [_file(_jpeg(), "IMG_0005.jpg")]},
    )
    image = get_image_model().objects.get()
    before = (image.file.name, _stored_bytes(image))
    client.post(
        reverse("backoffice:image_edit", args=[image.pk]),
        {"title": "改过的标题", "collection": collection.pk},
    )
    image.refresh_from_db()
    assert image.title == "改过的标题"
    assert (image.file.name, _stored_bytes(image)) == before


@pytest.mark.django_db
def test_a_person_over_the_days_pictures_is_told_so(site, client, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOADS_PER_DAY", 2)
    member = _user("many219@example.com", GROUP_SUBMITTER)
    client.force_login(member)
    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    answers = [
        client.post(
            reverse("backoffice:image_chooser_upload"),
            {"collection": collection.pk, "file": _file(_jpeg(), f"p{n}.jpg")},
        )
        for n in range(3)
    ]
    assert [a.status_code for a in answers][:2] == [200, 200]
    assert (
        answers[2].status_code == 400 or uploads.TOO_MANY in answers[2].content.decode()
    )
    assert get_image_model().objects.count() == 2
