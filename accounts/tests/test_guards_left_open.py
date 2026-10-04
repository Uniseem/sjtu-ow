"""Round 179 (guard sweep): refusals no test had reached. Each test here goes
red when its guard's condition is replaced by False."""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.utils import timezone

from accounts import services
from accounts.models import AvatarSubmission, User
from accounts.ranks import decode_rank
from accounts.tests.test_avatar_upload import _picture, person


@pytest.fixture
def site(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    call_command("init_site", verbosity=0)


@pytest.fixture
def editor(site):
    user = person("审核员179")
    user.groups.add(Group.objects.get(name="内容编辑"))
    return user


@pytest.mark.django_db
def test_accounts_need_an_email_and_superusers_both_flags():
    agreed = {
        "agreed_terms_at": timezone.now(),
        "agreed_cross_border_at": timezone.now(),
    }
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password=None, nickname="没邮箱", **agreed)
    for flag in ("is_staff", "is_superuser"):
        with pytest.raises(ValueError):
            User.objects.create_superuser(
                email=f"{flag}@example.com",
                password="Correct-Horse-Battery-1",
                nickname=flag[:12],
                **{flag: False},
                **agreed,
            )


@pytest.mark.parametrize("score", [-1, 41, "12", 1.5])
def test_scores_outside_the_table_are_refused(score):
    with pytest.raises(ValueError):
        decode_rank(score)


@pytest.mark.django_db
def test_a_picture_that_vanished_cannot_be_approved(editor):
    submission = services.submit_avatar(person("上传者179"), _picture())
    submission.image.delete()  # say, from the image library
    with pytest.raises(services.AvatarReviewError, match="不见了"):
        services.approve_avatar(submission.pk, editor)
    assert AvatarSubmission.objects.get(pk=submission.pk).status == "pending"


@pytest.mark.django_db
def test_only_the_face_in_use_can_be_taken_down(editor):
    owner = person("换过头像179")
    first = services.approve_avatar(
        services.submit_avatar(owner, _picture()).pk, editor
    )
    services.approve_avatar(
        services.submit_avatar(owner, _picture(colour=(0, 0, 200))).pk, editor
    )
    with pytest.raises(services.AvatarReviewError, match="没在用"):
        services.take_down_avatar(first.pk, editor, "porn")
