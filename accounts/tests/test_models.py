import pytest
from django.utils import timezone

from accounts.models import User


@pytest.mark.django_db
def test_create_user_with_email_login():
    user = User.objects.create_user(
        email="Player@example.com",
        password="Correct-Horse-Battery-1",
        nickname="测试昵称",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    assert user.email == "player@example.com"
    assert user.username is None or user.username == ""
    assert user.check_password("Correct-Horse-Battery-1")
    assert User.objects.get(email="player@example.com").nickname == "测试昵称"


@pytest.mark.django_db
def test_create_superuser_sets_agreement_timestamps():
    admin = User.objects.create_superuser(
        email="admin@example.com",
        password="Correct-Horse-Battery-1",
        nickname="管理员",
    )
    assert admin.is_staff
    assert admin.is_superuser
    assert admin.agreed_terms_at is not None
    assert admin.agreed_cross_border_at is not None
