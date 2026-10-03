"""Members upload their own face (design-details 2.3, v6.11, round 114).

The picture is squared and saved again as WebP; it waits for a reviewer and
the person keeps their old face until it is approved. Rejected, withdrawn,
replaced and taken-down pictures are deleted; the person is told why; the
reviewers get one reminder for a batch of uploads.
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
def test_an_upload_waits_for_review_and_changes_nothing_in_public(client, member):
    client.force_login(member)
    response = _upload(client)
    assert response.status_code == 302
    submission = AvatarSubmission.objects.get(user=member)
    assert submission.status == AvatarSubmission.Status.PENDING
    member.refresh_from_db()
    assert member.avatar_id is None
    thumb = submission.image.get_rendition("fill-176x176").url
    assert thumb not in client.get("/members/").content.decode()
    page = client.get(reverse("me_profile")).content.decode()
    assert thumb in page and "审核中" in page


@pytest.mark.django_db
def test_a_new_upload_replaces_the_one_waiting(client, member):
    client.force_login(member)
    _upload(client)
    first = AvatarSubmission.objects.get(user=member)
    _upload(client, _picture(colour=(10, 120, 30)))
    first.refresh_from_db()
    assert first.status == AvatarSubmission.Status.WITHDRAWN
    assert first.image_id is None  # deleted
    assert AvatarSubmission.objects.filter(user=member, status="pending").count() == 1


@pytest.mark.django_db
def test_withdrawing_deletes_the_picture(client, member):
    client.force_login(member)
    _upload(client)
    submission = AvatarSubmission.objects.get(user=member)
    image_id = submission.image_id
    client.post(reverse("me_avatar_withdraw"))
    submission.refresh_from_db()
    assert submission.status == AvatarSubmission.Status.WITHDRAWN
    assert not _image_exists(image_id)


@pytest.mark.django_db
def test_the_default_face_comes_back_at_once(client, member, editor):
    from accounts import services

    services.approve_avatar(services.submit_avatar(member, _picture()).pk, editor)
    member.refresh_from_db()
    uploaded = member.avatar_id
    client.force_login(member)
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


# --- reviewing -----------------------------------------------------------------------


@pytest.mark.django_db
def test_approving_puts_the_face_up_and_regenerates_its_pages(member, editor):
    from accounts import services

    services.approve_avatar(services.submit_avatar(member, _picture()).pk, editor)
    old = member.__class__.objects.get(pk=member.pk).avatar_id
    second = services.submit_avatar(member, _picture(colour=(0, 0, 200)))
    with mock.patch("accounts.signals.refresh_nickname_pages") as refresh:
        services.approve_avatar(second.pk, editor)
    member.refresh_from_db()
    assert member.avatar_id == second.image_id
    assert refresh.call_count == 1
    assert not _image_exists(old)  # the uploaded face it replaced
    second.refresh_from_db()
    assert second.status == AvatarSubmission.Status.APPROVED
    assert second.reviewed_by == editor


@pytest.mark.django_db
def test_approving_keeps_a_scripted_face_it_replaces(editor, site):
    from accounts import services
    from core.tests.test_chapter15_audit import make_user

    user = make_user(8)
    scripted = user.avatar_id
    services.approve_avatar(services.submit_avatar(user, _picture()).pk, editor)
    assert _image_exists(scripted)


@pytest.mark.django_db
def test_rejecting_deletes_the_picture_and_tells_the_person(
    member, editor, django_capture_on_commit_callbacks
):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    image_id = submission.image_id
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        services.reject_avatar(submission.pk, editor, "impersonation", "有社团标志")
    submission.refresh_from_db()
    assert submission.status == AvatarSubmission.Status.REJECTED
    assert submission.reason == "impersonation"
    assert not _image_exists(image_id)
    member.refresh_from_db()
    assert member.avatar_id is None
    sent = [m for m in mail.outbox if member.email in m.to]
    assert len(sent) == 1
    assert "冒充官方" in sent[0].body and "有社团标志" in sent[0].body


@pytest.mark.django_db
def test_taking_down_a_face_in_use(member, editor, django_capture_on_commit_callbacks):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    services.approve_avatar(submission.pk, editor)
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
    assert any("撤下" in m.subject for m in mail.outbox if member.email in m.to)


@pytest.mark.django_db
def test_a_decision_needs_a_reason_and_happens_once(member, editor):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    with pytest.raises(services.AvatarReviewError, match="原因"):
        services.reject_avatar(submission.pk, editor, "")
    services.approve_avatar(submission.pk, editor)
    with pytest.raises(services.AvatarReviewError, match="处理过"):
        services.approve_avatar(submission.pk, editor)


@pytest.mark.django_db
def test_only_reviewers_open_the_review_page(client, member, editor):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    client.force_login(editor)
    page = client.get(reverse("avatar_review"))
    assert page.status_code == 200
    assert submission.image.get_rendition("fill-240x240").url in page.content.decode()

    manager = person("赛事管理员丙")
    manager.groups.add(
        Group.objects.get(name="赛事管理员")
    )  # in the admin, not a reviewer
    client.force_login(manager)
    assert client.get(reverse("avatar_review")).status_code != 200
    client.post(
        reverse("avatar_review_action", args=[submission.pk]), {"action": "approve"}
    )
    submission.refresh_from_db()
    assert submission.status == AvatarSubmission.Status.PENDING


@pytest.mark.django_db
def test_a_reviewer_approves_from_the_page(client, member, editor):
    from accounts import services

    submission = services.submit_avatar(member, _picture())
    client.force_login(editor)
    response = client.post(
        reverse("avatar_review_action", args=[submission.pk]),
        {"action": "approve", "next": "//evil.example.com/"},
    )
    assert response.url == reverse("avatar_review")  # never off the site
    member.refresh_from_db()
    assert member.avatar_id == submission.image_id


@pytest.mark.django_db
def test_the_review_page_costs_the_same_however_many_wait(client, editor):
    from accounts import services
    from core.tests.test_chapter15_audit import assert_no_n_plus_one

    client.force_login(editor)

    def seed(count):
        for index in range(count):
            uploader = person(f"排队{AvatarSubmission.objects.count()}-{index}")
            services.submit_avatar(uploader, _picture())

    assert_no_n_plus_one(client, reverse("avatar_review"), seed)


# --- telling people ------------------------------------------------------------------


@pytest.mark.django_db
def test_reviewers_get_one_reminder_for_a_batch(
    member, editor, django_capture_on_commit_callbacks
):
    from accounts import notifications, services

    with (
        mock.patch("accounts.tasks.notify_avatars_waiting") as task,
        django_capture_on_commit_callbacks(execute=True),
    ):
        services.submit_avatar(member, _picture())
        services.submit_avatar(person("另一个上传者"), _picture())
    assert task.using.call_count == 1  # the second upload rides on the first
    run_after = task.using.call_args.kwargs["run_after"]
    from django.utils import timezone

    assert 9 * 60 < (run_after - timezone.now()).total_seconds() <= 10 * 60
    mail.outbox.clear()
    assert notifications.send_avatars_waiting() == 2
    assert len(mail.outbox) == 1
    letter = mail.outbox[0]
    assert editor.email in letter.to
    assert "上传者" in letter.body and "另一个上传者" in letter.body


@pytest.mark.django_db
def test_the_reminder_lets_the_next_upload_ask_again(
    member, editor, django_capture_on_commit_callbacks
):
    from accounts import notifications, services
    from accounts.tasks import notify_avatars_waiting

    real = notify_avatars_waiting
    with (
        mock.patch("accounts.tasks.notify_avatars_waiting") as task,
        django_capture_on_commit_callbacks(execute=True),
    ):
        services.submit_avatar(member, _picture())
        real.call()  # the reminder goes out
        services.submit_avatar(member, _picture(colour=(1, 2, 3)))
    assert task.using.call_count == 2
    assert cache.get(notifications.WAITING_KEY)


# --- leaving -------------------------------------------------------------------------


@pytest.mark.django_db
def test_deleting_the_account_deletes_every_uploaded_picture(member, editor):
    from accounts import services

    approved = services.submit_avatar(member, _picture())
    services.approve_avatar(approved.pk, editor)
    waiting = services.submit_avatar(member, _picture(colour=(9, 9, 9)))
    ids = [approved.image_id, waiting.image_id]
    services.delete_account(member)
    assert not any(_image_exists(pk) for pk in ids)
    assert not AvatarSubmission.objects.filter(user=member).exists()


@pytest.mark.django_db
def test_the_export_lists_the_uploads(member, editor):
    from accounts import services

    services.reject_avatar(
        services.submit_avatar(member, _picture()).pk, editor, "porn", "不合适"
    )
    uploads = services.personal_data(member)["avatar_uploads"]
    assert uploads[0]["status"] == "未通过"
    assert uploads[0]["reason"] == "色情低俗"
    assert "reviewed_by" not in uploads[0]
