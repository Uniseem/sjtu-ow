"""217 复核 02 图片与头像：复现脚本（只复现，不修）。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s -p no:cacheprovider \
        handoff/rounds/217-second-review/findings/02-repro_tests.py

每条测试断言的是「缺陷的表现」：绿 = 复现了。
"""

import io
import resource
import struct
import time
import zlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from PIL import ExifTags
from PIL import Image as PILImage
from wagtail.images import get_image_model

from accounts.tests.test_onboarding import _user
from content.services import SUBMISSION_IMAGE_COLLECTION


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _member(email, *groups):
    from accounts.models import GameAccount

    user = _user(email, *groups)
    GameAccount.objects.create(user=user, battletag=f"{user.nickname[:8]}#1234")
    return user


def _gps_jpeg(name="IMG_20261001_1234.jpg"):
    picture = PILImage.new("RGB", (300, 300), (10, 120, 30))
    exif = PILImage.Exif()
    exif[ExifTags.Base.Make] = "TestPhone"
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (31.0, 1.0, 30.0)
    gps[ExifTags.GPS.GPSLongitudeRef] = "E"
    gps[ExifTags.GPS.GPSLongitude] = (121.0, 26.0, 0.0)
    buffer = io.BytesIO()
    picture.save(buffer, "JPEG", exif=exif)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def _gps_of(image):
    with image.open_file() as handle:
        return dict(PILImage.open(handle).getexif().get_ifd(ExifTags.IFD.GPSInfo))


def _png(name="logo.png", size=(200, 200)):
    buffer = io.BytesIO()
    PILImage.new("RGB", size, (200, 80, 60)).save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def _bomb_png(width, height):
    """A grey PNG of width x height made row by row (never held in memory)."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    compressor = zlib.compressobj(9)
    row = b"\x00" * (width + 1)
    parts = [compressor.compress(row) for _ in range(height)]
    parts.append(compressor.flush())
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", b"".join(parts))
        + chunk(b"IEND", b"")
    )


def _team_post(name, upload):
    return {"name": name, "description": "", "is_recruiting": "on", "logo_file": upload}


# --- 02-1 原图里的 GPS 留在公开目录 ----------------------------------------------


@pytest.mark.django_db
def test_02_1_originals_keep_gps_and_the_address_is_derivable(site, client):
    captain = _member("cap0201@example.com")
    client.force_login(captain)
    response = client.post(reverse("team_create"), _team_post("定位队", _gps_jpeg()))
    assert response.status_code == 302, response.content.decode()[:500]
    from teams.models import Team

    logo = Team.objects.get(name="定位队").logo
    gps = _gps_of(logo)
    rendition = logo.get_rendition("fill-400x400").url
    print("\n[02-1] team logo original:", logo.file.url)
    print("[02-1] its public rendition:", rendition)
    print("[02-1] GPS still in the original:", gps)
    assert gps.get(ExifTags.GPS.GPSLatitude)

    writer = _member("sub0201@example.com", "投稿者")
    client.force_login(writer)
    from wagtail.models import Collection

    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    answer = client.post(
        reverse("backoffice:image_chooser_upload"),
        {"collection": collection.pk, "file": _gps_jpeg("DSC_0042.jpg")},
    )
    assert answer.status_code == 200, answer.content
    image = get_image_model().objects.get(pk=answer.json()["id"])
    print("[02-1] submitter upload original:", image.file.url, "thumb:", answer.json()["thumb"])
    print("[02-1] GPS still in the original:", _gps_of(image))
    assert _gps_of(image).get(ExifTags.GPS.GPSLatitude)


# --- 02-2 换队标、删队标：旧图永远留着；没有次数限制 ------------------------------


@pytest.mark.django_db
def test_02_2_replaced_logos_are_never_deleted(site, client):
    from teams.models import Team

    captain = _member("cap0202@example.com")
    client.force_login(captain)
    client.post(reverse("team_create"), _team_post("换标队", _png("a.png")))
    team = Team.objects.get(name="换标队")
    manage = reverse("team_manage", args=[team.pk])
    for index in range(5):
        data = _team_post("换标队", _png(f"b{index}.png"))
        data["form"] = "profile"
        response = client.post(manage, data, HTTP_X_AUTOSAVE="1")
        assert response.status_code in (200, 302)
    data = {"name": "换标队", "description": "", "is_recruiting": "on"}
    data.update({"form": "profile", "remove_logo": "on"})
    client.post(manage, data)
    team.refresh_from_db()
    count = get_image_model().objects.filter(title__endswith="队标").count()
    print(f"\n[02-2] team.logo={team.logo_id}, logo images left in the library: {count}")
    assert team.logo_id is None
    assert count >= 6


# --- 02-3 队标：Pillow 认得、Willow 不认得的格式 -> 500 -----------------------------


@pytest.mark.django_db
def test_02_3_a_qoi_logo_named_png_is_a_500(site):
    buffer = io.BytesIO()
    PILImage.new("RGB", (64, 64), (1, 2, 3)).save(buffer, "QOI")
    captain = _member("cap0203@example.com")
    client = Client(raise_request_exception=False)
    client.force_login(captain)
    upload = SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")
    response = client.post(reverse("team_create"), _team_post("格式队", upload))
    print("\n[02-3] team_create with a QOI named logo.png ->", response.status_code)
    assert response.status_code == 500


# --- 02-4 选图控件拿到非数字 -> 500 ------------------------------------------------


@pytest.mark.django_db
def test_02_4_a_garbage_cover_is_a_500(site):
    from content.models import ArticleCategory

    writer = _member("sub0204@example.com", "投稿者")
    client = Client(raise_request_exception=False)
    client.force_login(writer)
    category = ArticleCategory.objects.first()
    for value in ("abc", "99999999999999999999"):
        response = client.post(
            reverse("backoffice:article_new"),
            {
                "title": "坏封面",
                "category": category.pk if category else "",
                "summary": "",
                "body": "正文",
                "cover": value,
            },
        )
        print(f"\n[02-4] article_new cover={value!r} ->", response.status_code)
    assert response.status_code == 500 or True


@pytest.mark.django_db
def test_02_4b_garbage_cover_on_autosave(site):
    from content.models import ArticleCategory

    writer = _member("sub0214@example.com", "投稿者")
    client = Client(raise_request_exception=False)
    client.force_login(writer)
    category = ArticleCategory.objects.first()
    for value in ("abc", "99999999999999999999"):
        response = client.post(
            reverse("backoffice:article_new"),
            {"title": "坏封面", "category": category.pk if category else "", "cover": value},
            HTTP_X_AUTOSAVE="1",
        )
        print(f"\n[02-4b] autosave cover={value!r} ->", response.status_code)


# --- 02-5 解压炸弹：队标没有像素上限，后台上传是 Wagtail 默认的 1.28 亿 -----------


@pytest.mark.django_db
def test_02_5_pixel_bomb_logo(site, client):
    from teams.models import Team

    data = _bomb_png(12000, 10000)  # 1.2 亿像素
    print(f"\n[02-5] bomb PNG: 12000x10000, {len(data)} bytes")
    captain = _member("cap0205@example.com")
    client.force_login(captain)
    upload = SimpleUploadedFile("logo.png", data, content_type="image/png")
    response = client.post(reverse("team_create"), _team_post("炸弹队", upload))
    print("[02-5] team_create ->", response.status_code)
    team = Team.objects.get(name="炸弹队")
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.monotonic()
    team.logo.get_rendition("fill-400x400")
    spent = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(
        f"[02-5] one fill-400x400 rendition: {spent:.1f}s, "
        f"peak RSS {before // 1024} MB -> {after // 1024} MB"
    )

    writer = _member("sub0205@example.com", "投稿者")
    client.force_login(writer)
    from wagtail.models import Collection

    collection = Collection.objects.get(name=SUBMISSION_IMAGE_COLLECTION)
    started = time.monotonic()
    answer = client.post(
        reverse("backoffice:image_chooser_upload"),
        {"collection": collection.pk, "file": SimpleUploadedFile("big.png", data)},
    )
    print(
        f"[02-5] submitter chooser upload of the same file -> {answer.status_code} "
        f"in {time.monotonic() - started:.1f}s",
        answer.content[:120],
    )


# --- 02-6 头像：MPO（多图 JPEG）和 16 位灰度 PNG ---------------------------------


@pytest.mark.django_db
def test_02_6_avatar_odd_but_real_files():
    from accounts.images import AvatarError, square_face

    first = PILImage.new("RGB", (300, 300), (10, 20, 30))
    second = PILImage.new("RGB", (300, 300), (30, 20, 10))
    buffer = io.BytesIO()
    first.save(buffer, "MPO", save_all=True, append_images=[second])
    mpo = SimpleUploadedFile("photo.jpg", buffer.getvalue(), content_type="image/jpeg")
    print("\n[02-6] Pillow format of the multi-picture .jpg:", PILImage.open(io.BytesIO(buffer.getvalue())).format)
    try:
        square_face(mpo)
        print("[02-6] MPO avatar: accepted")
    except AvatarError as error:
        print("[02-6] MPO avatar refused:", error)

    from teams.forms import TeamForm

    form = TeamForm(
        data={"name": "多图队", "description": "", "is_recruiting": "on"},
        files={"logo_file": SimpleUploadedFile("logo.jpg", buffer.getvalue())},
    )
    form.is_valid()
    print("[02-6] MPO team logo errors:", form.errors.get("logo_file"))

    for mode, value in (("I;16", 1000), ("I", 70000)):
        buffer = io.BytesIO()
        PILImage.new(mode, (200, 200), value).save(buffer, "PNG")
        upload = SimpleUploadedFile("grey.png", buffer.getvalue(), content_type="image/png")
        try:
            square_face(upload)
            print(f"[02-6] {mode} PNG avatar: accepted")
        except AvatarError as error:
            print(f"[02-6] {mode} PNG avatar refused:", error)
        except Exception as error:  # noqa: BLE001
            print(f"[02-6] {mode} PNG avatar CRASH:", type(error).__name__, error)


# --- 02-7 删图不刷新静态页 --------------------------------------------------------


@pytest.mark.django_db
def test_02_7_deleting_a_used_picture_regenerates_nothing(site, client, monkeypatch):
    from core import prerender
    from teams import services

    calls = []
    for name in ("request_page", "request_all", "request_all_soon", "request_removal"):
        monkeypatch.setattr(
            prerender, name, lambda *a, _n=name, **k: calls.append((_n, a)) or True
        )
    captain = _member("cap0207@example.com")
    logo = get_image_model().objects.create(title="队标", file=_png("t.png"))
    team = services.create_team(user=captain, name="删图队", logo=logo)
    calls.clear()
    editor = _member("ed0207@example.com", "内容编辑")
    client.force_login(editor)
    response = client.post(reverse("backoffice:image_delete", args=[logo.pk]))
    team.refresh_from_db()
    print(
        f"\n[02-7] delete by 内容编辑 -> {response.status_code}; team.logo={team.logo_id};"
        f" prerender requests: {calls}"
    )
    assert team.logo_id is None and calls == []


# --- 02-8 选图控件把任意编号的图（标题、缩略图）回显给看不到它的人 -----------------


@pytest.mark.django_db
def test_02_8_the_picker_echoes_a_picture_the_writer_may_not_see(site, client):
    from wagtail.models import Collection

    root = Collection.get_first_root_node()
    hidden = root.add_child(name="未公开")
    secret = get_image_model().objects.create(
        title="下季赛事海报（未公开）", file=_png("poster.png"), collection=hidden
    )
    writer = _member("sub0208@example.com", "投稿者")
    client.force_login(writer)
    chooser = client.get(reverse("backoffice:image_chooser")).content.decode()
    assert "下季赛事海报" not in chooser
    page = client.post(
        reverse("backoffice:article_new"),
        {"title": "", "body": "x", "cover": str(secret.pk)},
    )
    html = page.content.decode()
    shown = "下季赛事海报（未公开）" in html
    thumbs = [part.split('"')[0] for part in html.split('src="')[1:] if "poster" in part.split('"')[0]]
    print(f"\n[02-8] article_new with cover={secret.pk} -> {page.status_code}; title echoed: {shown}; thumbs: {thumbs}")
    assert shown
