"""217 复核 07 的第二组复现：状态片段的编号、队标原图带 EXIF。

  bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider \
      handoff/rounds/217-second-review/findings/07-test_teams_repro2.py
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pytest
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from PIL import Image

from accounts.models import GameAccount, User
from teams.models import Team


def _member(email, nickname):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    GameAccount.objects.create(user=user, battletag=f"{nickname}#1234")
    return user


@pytest.mark.django_db
@pytest.mark.parametrize("slot", ["team-join:²", "scrim-actions:²", "tournament-actions:²"])
def test_07_6_superscript_digit_in_a_slot_is_a_500(slot):
    client = Client(raise_request_exception=False)
    response = client.get("/_fragments/state/", {"slots": slot})
    print(f"\n[07-6] GET /_fragments/state/?slots={slot} -> {response.status_code}")
    if slot.startswith("team-join"):
        assert response.status_code == 500


@pytest.mark.django_db
def test_07_7_logo_original_keeps_gps_exif_and_its_name_is_public():
    captain = _member("gps@example.com", "定位队长")
    picture = Image.new("RGB", (300, 300), "green")
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x0110] = "PhoneModel X"  # Model
    gps = {1: "N", 2: (31.0, 1.0, 30.0), 3: "E", 4: (121.0, 26.0, 10.0)}
    exif[0x8825] = gps
    buffer = BytesIO()
    picture.save(buffer, "JPEG", exif=exif.tobytes())
    client = Client(raise_request_exception=False)
    client.force_login(captain)
    response = client.post(
        "/teams/new/",
        {
            "name": "定位战队",
            "is_recruiting": "on",
            "logo_file": SimpleUploadedFile("IMG_20261007_0930.jpg", buffer.getvalue()),
        },
    )
    print("\n[07-7] POST /teams/new/ ->", response.status_code)
    team = Team.objects.get(name="定位战队")
    page = Client().get(f"/teams/{team.pk}/").content.decode()
    shown = re.findall(r'src="([^"]*/media/images/[^"]+)"', page)
    print("[07-7] 页面上的队标缩略图地址：", shown[:2])
    original = Path(settings.MEDIA_ROOT) / team.logo.file.name
    print("[07-7] 原图存放：", team.logo.file.name, "（Caddy /media/* 原样公开）")
    with Image.open(original) as stored:
        kept = stored.getexif()
        print("[07-7] 原图里的 EXIF：Make", kept.get(0x010F), "Model", kept.get(0x0110),
              "GPS", dict(kept.get_ifd(0x8825)))
        assert kept.get_ifd(0x8825)
