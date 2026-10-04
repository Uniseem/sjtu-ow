"""Members upload their own face (design-details 2.3, v6.11, round 114).

The picture is squared and saved again as WebP and shows at once (v6.73,
round 195: everyone is trusted; until then it waited for a reviewer). An
admin can take a face down, and the person is told why; replaced and
taken-down pictures are deleted.
"""

from io import BytesIO
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from PIL import Image as PILImage

from accounts.models import AvatarSubmission, Feature, FeatureUserRule
from members.tests.test_members import person


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    cache.clear()  # the daily upload limit and the reminder live in the cache


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


@pytest.fixture
def member(site):
    return person("上传者")


@pytest.fixture
def editor(site):
    user = person("头像审核员")
    user.groups.add(Group.objects.get(name="内容编辑"))
    return user


def _picture(size=(600, 400), fmt="PNG", name=None, colour=(200, 60, 40), **save):
    buffer = BytesIO()
    PILImage.new("RGB", size, colour).save(buffer, fmt, **save)
    ext = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp", "GIF": "gif"}[fmt]
    content_type = {"jpg": "image/jpeg", "gif": "image/gif"}.get(ext, f"image/{ext}")
    return SimpleUploadedFile(
        name or f"face.{ext}", buffer.getvalue(), content_type=content_type
    )


def _upload(client, picture=None):
    return client.post(reverse("me_avatar_upload"), {"file": picture or _picture()})


def _image_exists(pk) -> bool:
    from wagtail.images.models import Image

    return Image.objects.filter(pk=pk).exists()


def _stored(submission):
    submission.image.file.open("rb")
    try:
        return PILImage.open(BytesIO(submission.image.file.read()))
    finally:
        submission.image.file.close()


# --- the picture -------------------------------------------------------------------


@pytest.mark.django_db
def test_a_photo_becomes_a_square_webp_of_at_most_512(member):
    from accounts import services

    submission = services.submit_avatar(member, _picture((1200, 800), "JPEG"))
    stored = _stored(submission)
    assert stored.format == "WEBP"
    assert stored.size == (512, 512)
    assert submission.image.collection.name == "用户头像"


@pytest.mark.django_db
def test_a_small_picture_keeps_its_size_but_is_square(member):
    from accounts import services

    submission = services.submit_avatar(member, _picture((300, 200)))
    assert _stored(submission).size == (200, 200)


@pytest.mark.django_db
def test_the_camera_data_is_gone_and_the_picture_stands_up(member):
    """A phone photo held sideways: stored 300×150 with 'turn 90°' in its
    data, top half red, bottom half blue. Turned, it is 150×300 with red on
    one side and blue on the other; cut without turning it would be red on
    both sides of the top row. The location data must not survive."""
    from accounts import services

    picture = PILImage.new("RGB", (300, 150), (220, 30, 30))
    picture.paste((30, 30, 220), (0, 75, 300, 150))
    exif = PILImage.Exif()
    exif[0x0112] = 6  # orientation: turn 90° to show
    exif[0x8825] = {1: "N", 2: (31.0, 1.0, 0.0)}  # a GPS position
    buffer = BytesIO()
    picture.save(buffer, "JPEG", exif=exif.tobytes(), quality=95)
    upload = SimpleUploadedFile("phone.jpg", buffer.getvalue(), "image/jpeg")
    stored = _stored(services.submit_avatar(member, upload)).convert("RGB")
    assert stored.size == (150, 150)
    left, right = stored.getpixel((10, 10)), stored.getpixel((140, 10))
    assert (left[0] > left[2]) != (right[0] > right[2])  # red on one side only
    assert not dict(stored.getexif())


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (lambda: _picture((100, 100)), "至少要 128"),
        (lambda: SimpleUploadedFile("x.png", b"not a picture", "image/png"), "读不出"),
        (lambda: _picture(fmt="GIF", name="face.png"), "只支持"),
    ],
)
def test_pictures_we_cannot_use_are_refused(member, upload, message):
    from accounts import services

    with pytest.raises(services.AvatarUploadError, match=message):
        services.submit_avatar(member, upload())
    assert not AvatarSubmission.objects.exists()


@pytest.mark.django_db
def test_a_huge_picture_is_refused_before_it_is_decoded(member):
    from accounts import services

    with mock.patch("accounts.images.AVATAR_MAX_PIXELS", 200 * 200 - 1):
        with pytest.raises(services.AvatarUploadError, match="4000 万像素"):
            services.submit_avatar(member, _picture((200, 200)))


@pytest.mark.django_db
def test_the_form_refuses_big_files_and_other_types():
    from accounts.forms import AvatarForm

    big = SimpleUploadedFile("big.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")
    assert "5MB" in str(AvatarForm(files={"file": big}).errors)
    gif = _picture(fmt="GIF")
    assert "只支持" in str(AvatarForm(files={"file": gif}).errors)


# --- uploading -----------------------------------------------------------------------


@pytest.mark.django_db
def test_an_upload_shows_at_once(client, member):
    """v6.73: no review; the new face is up and its pages are regenerated."""
    client.force_login(member)
    with mock.patch("accounts.signals.refresh_nickname_pages") as refresh:
        response = _upload(client)
    assert response.status_code == 302
    submission = AvatarSubmission.objects.get(user=member)
    assert submission.status == AvatarSubmission.Status.APPROVED
    assert submission.reviewed_by is None and submission.reviewed_at is not None
    member.refresh_from_db()
    assert member.avatar_id == submission.image_id
    assert refresh.call_count == 1
    page = client.get(reverse("me_profile")).content.decode()
    assert "审核" not in page


@pytest.mark.django_db
def test_a_new_upload_replaces_the_face_and_deletes_the_old_upload(client, member):
    client.force_login(member)
    _upload(client)
    first = AvatarSubmission.objects.get(user=member)
    _upload(client, _picture(colour=(10, 120, 30)))
    member.refresh_from_db()
    second = AvatarSubmission.objects.exclude(pk=first.pk).get(user=member)
    assert member.avatar_id == second.image_id
    assert not _image_exists(first.image_id)  # theirs, so deleted


@pytest.mark.django_db
def test_the_default_face_comes_back_at_once(client, member):
    client.force_login(member)
    _upload(client)
    member.refresh_from_db()
    uploaded = member.avatar_id
    client.post(reverse("me_avatar_remove"))
    member.refresh_from_db()
    assert member.avatar_id is None
    assert not _image_exists(uploaded)  # theirs, so deleted


@pytest.mark.django_db
def test_a_face_put_there_by_script_is_not_deleted(client, site):
    from core.tests.test_chapter15_audit import make_user

    user = make_user(7)  # the demo puts faces on like this
    scripted = user.avatar_id
    client.force_login(user)
    client.post(reverse("me_avatar_remove"))
    user.refresh_from_db()
    assert user.avatar_id is None
    assert _image_exists(scripted)


@pytest.mark.django_db
def test_an_upload_keeps_a_scripted_face_it_replaces(client, site):
    from core.tests.test_chapter15_audit import make_user

    user = make_user(8)
    scripted = user.avatar_id
    client.force_login(user)
    _upload(client)
    assert _image_exists(scripted)


@pytest.mark.django_db
def test_someone_barred_from_uploading_can_still_go_back_to_default(client, member):
    FeatureUserRule.objects.create(
        user=member, feature=Feature.AVATAR_UPLOAD, allowed=False
    )
    client.force_login(member)
    page = client.get(reverse("me_profile")).content.decode()
    assert 'type="file"' not in page
    assert "暂时无法使用此功能" in page
    response = _upload(client)
    assert response.status_code == 200
    assert "暂时无法使用此功能" in response.content.decode()
    assert not AvatarSubmission.objects.exists()


@pytest.mark.django_db
def test_five_uploads_a_day(client, member):
    client.force_login(member)
    for _ in range(5):
        assert _upload(client).status_code == 302
    response = _upload(client)
    assert response.status_code == 200
    assert "明天再来" in response.content.decode()


@pytest.mark.django_db
def test_uploading_needs_a_post(client, member):
    client.force_login(member)
    assert client.get(reverse("me_avatar_upload")).status_code == 405


@pytest.mark.django_db
def test_nobody_is_mailed_about_an_upload(client, member, editor):
    """Until v6.73 the reviewers got a reminder for each batch."""
    mail.outbox.clear()
    client.force_login(member)
    _upload(client)
    assert mail.outbox == []


# --- taking down ---------------------------------------------------------------------


@pytest.mark.django_db
def test_taking_down_a_face_in_use(member, editor, django_capture_on_commit_callbacks):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    image_id = submission.image_id
    mail.outbox.clear()
    with (
        mock.patch("accounts.signals.refresh_nickname_pages") as refresh,
        django_capture_on_commit_callbacks(execute=True),
    ):
        services.take_down_avatar(submission.pk, editor, "porn")
    member.refresh_from_db()
    assert member.avatar_id is None
    assert refresh.call_count == 1  # its pages lose the face too
    assert not _image_exists(image_id)
    submission.refresh_from_db()
    assert submission.status == AvatarSubmission.Status.TAKEN_DOWN
    assert submission.reviewed_by == editor
    letters = [m for m in mail.outbox if member.email in m.to]
    assert any("撤下" in m.subject for m in letters)
    assert "审核通过后" not in letters[0].body


@pytest.mark.django_db
def test_taking_down_needs_a_reason_and_happens_once(member, editor):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    with pytest.raises(services.AvatarReviewError, match="原因"):
        services.take_down_avatar(submission.pk, editor, "")
    services.take_down_avatar(submission.pk, editor, "porn")
    with pytest.raises(services.AvatarReviewError, match="处理过"):
        services.take_down_avatar(submission.pk, editor, "porn")


@pytest.mark.django_db
def test_the_page_lists_the_faces_in_use_newest_first(client, member, editor):
    from accounts import services

    older = services.submit_avatar(person("先传的人"), _picture())
    newer = services.submit_avatar(member, _picture(colour=(0, 0, 200)))
    client.force_login(editor)
    page = client.get(reverse("avatar_review"))
    assert page.status_code == 200
    html = page.content.decode()
    first = newer.image.get_rendition("fill-240x240").url
    second = older.image.get_rendition("fill-240x240").url
    assert html.index(first) < html.index(second)
    assert "通过" not in html.replace("未通过", "").replace("已通过", "")


@pytest.mark.django_db
def test_only_reviewers_open_the_page_and_take_down(client, member, editor):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    manager = person("赛事管理员丙")
    manager.groups.add(Group.objects.get(name="赛事管理员"))  # in the admin
    client.force_login(manager)
    assert client.get(reverse("avatar_review")).status_code != 200
    client.post(
        reverse("avatar_review_action", args=[submission.pk]),
        {"action": "take_down", "reason": "porn"},
    )
    submission.refresh_from_db()
    assert submission.status == AvatarSubmission.Status.APPROVED


@pytest.mark.django_db
def test_a_reviewer_takes_down_from_the_page(client, member, editor):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    client.force_login(editor)
    response = client.post(
        reverse("avatar_review_action", args=[submission.pk]),
        {"action": "take_down", "reason": "porn", "next": "//evil.example.com/"},
    )
    assert response.url == reverse("avatar_review")  # never off the site
    member.refresh_from_db()
    assert member.avatar_id is None
    for gone in ("approve", "reject"):
        client.post(
            reverse("avatar_review_action", args=[submission.pk]), {"action": gone}
        )


@pytest.mark.django_db
def test_the_review_page_costs_the_same_however_many_there_are(client, editor):
    from accounts import services
    from core.tests.test_chapter15_audit import assert_no_n_plus_one

    client.force_login(editor)

    def seed(count):
        for index in range(count):
            uploader = person(f"头像{AvatarSubmission.objects.count()}-{index}")
            services.submit_avatar(uploader, _picture())

    assert_no_n_plus_one(client, reverse("avatar_review"), seed)


# --- leaving -------------------------------------------------------------------------


@pytest.mark.django_db
def test_deleting_the_account_deletes_every_uploaded_picture(member, editor):
    from accounts import services

    first = services.submit_avatar(member, _picture())
    taken = services.submit_avatar(member, _picture(colour=(9, 9, 9)))
    services.take_down_avatar(taken.pk, editor, "porn")
    current = services.submit_avatar(member, _picture(colour=(1, 9, 1)))
    ids = [first.image_id, current.image_id]
    services.delete_account(member)
    assert not any(_image_exists(pk) for pk in ids if pk)
    assert not AvatarSubmission.objects.filter(user=member).exists()


@pytest.mark.django_db
def test_the_export_lists_the_uploads(member, editor):
    from accounts import services

    services.take_down_avatar(
        services.submit_avatar(member, _picture()).pk, editor, "porn", "不合适"
    )
    uploads = services.personal_data(member)["avatar_uploads"]
    assert uploads[0]["status"] == "已撤下"
    assert uploads[0]["reason"] == "色情低俗"
    assert "reviewed_by" not in uploads[0]
