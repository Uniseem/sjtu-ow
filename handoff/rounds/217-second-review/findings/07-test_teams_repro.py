"""217 复核 07（战队与成员）的复现脚本。只读复现，不改业务代码。

在测试机上跑：
  bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider \
      handoff/rounds/217-second-review/findings/07-test_teams_repro.py

每条测试把实际看到的状态码 / 数字打印出来（-s），断言写的是「现在的（有缺陷的）行为」，
所以绿 = 缺陷复现了。
"""

from __future__ import annotations

import resource
import struct
import time
import zlib
from io import BytesIO

import pytest
from allauth.account.models import EmailAddress
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from PIL import Image, PngImagePlugin

from accounts.models import GameAccount, User
from teams import services
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


def _png_with_broken_exif() -> bytes:
    """Same file as accounts/tests/test_216_account_and_core.py (216, A4):
    decodes and loads fine, only ImageOps.exif_transpose raises ValueError."""
    info = PngImagePlugin.PngInfo()
    info.add_text("Raw profile type exif", "\nexif\n    10\nzz-not-hex\n")
    buffer = BytesIO()
    Image.new("RGB", (300, 300), "red").save(buffer, "PNG", pnginfo=info)
    return buffer.getvalue()


def _huge_png(side: int) -> bytes:
    """A side x side black RGB PNG written row by row (little memory here)."""

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    packer = zlib.compressobj(9)
    row = b"\x00" + b"\x00" * (side * 3)
    body = b"".join(packer.compress(row) for _ in range(side)) + packer.flush()
    header = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", body)
        + chunk(b"IEND", b"")
    )


def _status(client, path):
    try:
        return client.get(path).status_code
    except Exception as exc:  # noqa: BLE001
        return f"exception {type(exc).__name__}: {exc}"


@pytest.mark.django_db
def test_07_1_broken_exif_logo_breaks_every_page_showing_it():
    captain = _member("cap@example.com", "队长甲")
    client = Client(raise_request_exception=False)
    client.force_login(captain)
    response = client.post(
        "/teams/new/",
        {
            "name": "坏图战队",
            "description": "x",
            "is_recruiting": "on",
            "logo_file": SimpleUploadedFile(
                "logo.png", _png_with_broken_exif(), "image/png"
            ),
        },
    )
    print("\n[07-1] POST /teams/new/ ->", response.status_code, response.get("Location"))
    team = Team.objects.get(name="坏图战队")
    assert team.logo_id is not None
    paths = [
        f"/teams/{team.pk}/",
        "/teams/",
        "/teams/?recruiting=1",
        f"/teams/{team.pk}/manage/",
        f"/members/{captain.pk}/",
        "/",
    ]
    seen = {path: _status(client, path) for path in paths}
    anonymous = Client(raise_request_exception=False)
    seen["(访客) /teams/"] = _status(anonymous, "/teams/")
    seen[f"(访客) /teams/{team.pk}/"] = _status(anonymous, f"/teams/{team.pk}/")
    for path, status in seen.items():
        print(f"[07-1] GET {path} -> {status}")
    from core import prerender

    for path in ("/teams/", f"/teams/{team.pk}/"):
        try:
            prerender.render_html(path)
            print(f"[07-1] prerender {path} -> ok")
        except Exception as exc:  # noqa: BLE001
            print(f"[07-1] prerender {path} -> {type(exc).__name__}: {exc}")
    assert seen[f"/teams/{team.pk}/"] == 500
    assert seen["/teams/"] == 500


@pytest.mark.django_db
def test_07_2_logo_has_no_pixel_limit():
    captain = _member("big@example.com", "大图队长")
    client = Client(raise_request_exception=False)
    client.force_login(captain)
    data = _huge_png(12000)  # 144M pixels
    print(f"\n[07-2] 12000x12000 PNG 文件大小 {len(data)} 字节")
    response = client.post(
        "/teams/new/",
        {
            "name": "大图战队",
            "is_recruiting": "on",
            "logo_file": SimpleUploadedFile("logo.png", data, "image/png"),
        },
    )
    print("[07-2] POST /teams/new/ ->", response.status_code)
    team = Team.objects.get(name="大图战队")
    print("[07-2] 队标尺寸", team.logo.width, "x", team.logo.height)
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.monotonic()
    status = _status(client, f"/teams/{team.pk}/")
    took = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(
        f"[07-2] GET /teams/{team.pk}/ -> {status}，用时 {took:.1f} 秒，"
        f"进程峰值内存 {before // 1024} MB -> {after // 1024} MB"
    )
    assert team.logo.width * team.logo.height > 40_000_000


@pytest.mark.django_db
def test_07_3_unrecognised_format_named_png_is_a_500():
    captain = _member("qoi@example.com", "格式队长")
    client = Client(raise_request_exception=False)
    client.force_login(captain)
    buffer = BytesIO()
    Image.new("RGB", (64, 64), "blue").save(buffer, "QOI")
    response = client.post(
        "/teams/new/",
        {
            "name": "格式战队",
            "is_recruiting": "on",
            "logo_file": SimpleUploadedFile("logo.png", buffer.getvalue(), "image/png"),
        },
    )
    print("\n[07-3] POST /teams/new/ (QOI 内容, 名字 logo.png) ->", response.status_code)
    assert response.status_code == 500


@pytest.mark.django_db
def test_07_4_non_ascii_case_names_slip_past_the_form_check():
    captain = _member("fw@example.com", "全角队长")
    other = _member("fw2@example.com", "全角队长二")
    services.create_team(user=captain, name="ＯＷ精英")
    print("\n[07-4] name_taken('ＯＷ精英') 完全同名 ->", services.name_taken("ＯＷ精英"))
    print("[07-4] name_taken('ｏｗ精英') ->", services.name_taken("ｏｗ精英"))
    services.create_team(user=other, name="ｏｗ精英")
    print("[07-4] 「ｏｗ精英」也建成了：", Team.objects.filter(name="ｏｗ精英").exists())
    from teams.forms import TeamForm

    form = TeamForm(data={"name": "ＯＷ精英", "is_recruiting": "on"})
    print("[07-4] 前台建队表单对完全同名 'ＯＷ精英' is_valid ->", form.is_valid())
    assert services.name_taken("ＯＷ精英") is False


@pytest.mark.django_db
def test_07_5_apply_limit_counts_invalid_forms():
    captain = _member("ap@example.com", "申请队长")
    team = services.create_team(user=captain, name="申请战队")
    applicant = _member("ap2@example.com", "申请人")
    client = Client(raise_request_exception=False)
    client.force_login(applicant)
    for _ in range(20):
        client.post(f"/teams/{team.pk}/apply/", {"message": "忘了勾位置"})
    response = client.post(
        f"/teams/{team.pk}/apply/", {"role_tank": "on", "message": "这次勾了"}
    )
    text = response.content.decode()
    refused = "今天的入队申请太多了" in text
    print(
        "\n[07-5] 20 次没勾位置（表单无效）后第一次有效申请：被限流 ->",
        refused,
        "；申请条数",
        team.applications.count(),
    )
    assert refused
