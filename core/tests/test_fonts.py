import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.fonts import services
from core.fonts.css import build_css, ordered_rules, regenerate_font_css
from core.fonts.download import DownloadError, fetch_bytes, parse_google_css
from core.fonts.forms import FontUploadForm, variant_warning
from core.fonts.processing import EmbeddingNotAllowed, inspect_font
from core.fonts.slicing import build_slices, format_unicode_range
from core.models import FontFace, FontFamily, SiteSettings, TypographyRule
from core.tests.fonts_factory import make_font_bytes, sample_chars


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _superuser(email="fontadmin@example.com"):
    return User.objects.create_superuser(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname="字体管理员",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


def _staff_user(email="editor@example.com"):
    """A Wagtail admin user who is not a superuser."""
    from django.contrib.auth.models import Permission

    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname="内容编辑",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="wagtailadmin", codename="access_admin"
        )
    )
    return user


def _family(**kwargs):
    kwargs.setdefault("name", "测试字体")
    kwargs.setdefault("source", FontFamily.Source.UPLOAD)
    kwargs.setdefault("license_type", FontFamily.License.OPEN_SOURCE)
    return services.create_family(**kwargs)


def _ready_face(family, weight=400, slices=None):
    return FontFace.objects.create(
        family=family,
        weight=weight,
        status=FontFace.Status.READY,
        progress=100,
        slices=slices
        or [
            {
                "path": "fonts/x/400-000.abc.woff2",
                "unicode_range": "U+4E00",
                "bytes": 10,
            }
        ],
        slice_count=1,
        total_bytes=10,
        glyph_count=1,
    )


# --- slicing -----------------------------------------------------------------


def test_latin_and_common_hanzi_go_to_different_slices():
    chars = [chr(code) for code in range(0x41, 0x5B)] + [
        chr(code) for code in range(0x4E00, 0x4E00 + 250)
    ]
    slices = build_slices(ord(char) for char in chars)
    assert len(slices[0]) == 26
    assert all(code < 0x100 for code in slices[0])
    assert len(slices) >= 3
    assert max(len(group) for group in slices[1:]) <= 200


def test_unicode_range_collapses_runs():
    ranges = format_unicode_range([0x4E00, 0x4E01, 0x4E02, 0x4E05])
    assert ranges == "U+4E00-4E02, U+4E05"
    assert format_unicode_range([]) == ""


# --- inspection --------------------------------------------------------------


def test_inspect_reads_weight_and_characters():
    info = inspect_font(make_font_bytes("ABC的一", weight=700))
    assert info.weight == 700
    assert info.glyph_count == 5
    assert ord("的") in info.codepoints


def test_restricted_fonts_are_rejected():
    with pytest.raises(EmbeddingNotAllowed):
        inspect_font(make_font_bytes("AB", fs_type=2))


def test_upload_form_rejects_restricted_font(media_root):
    form = FontUploadForm(
        data={
            "name": "禁止嵌入字体",
            "license_type": FontFamily.License.OTHER,
            "license_confirmed": "on",
        },
        files={
            "file": SimpleUploadedFile(
                "bad.ttf", make_font_bytes("AB", fs_type=2), "font/ttf"
            )
        },
        prefix=None,
    )
    assert not form.is_valid()
    assert "禁止嵌入" in str(form.errors["file"])


# --- processing --------------------------------------------------------------


@pytest.mark.django_db
def test_processing_slices_font_and_writes_woff2(media_root):
    family = _family()
    face = services.add_face_from_bytes(
        family, make_font_bytes(sample_chars(260)), "test.ttf", weight=400
    )
    assert services.run_face_processing(face.pk) == "done"

    face.refresh_from_db()
    assert face.status == FontFace.Status.READY
    assert face.progress == 100
    assert face.slice_count >= 2
    assert face.total_bytes > 0
    assert face.glyph_count == 260
    for item in face.slices:
        assert default_storage.exists(item["path"])
        with default_storage.open(item["path"], "rb") as handle:
            assert handle.read(4) == b"wOF2"
        assert item["unicode_range"].startswith("U+")
    assert len({item["path"] for item in face.slices}) == face.slice_count


@pytest.mark.django_db
def test_processing_failure_is_reported(media_root):
    family = _family()
    face = FontFace.objects.create(family=family, weight=400)
    face.original_file.save("broken.ttf", ContentFile(b"not a font"))
    assert services.run_face_processing(face.pk) == "failed"
    face.refresh_from_db()
    assert face.status == FontFace.Status.FAILED
    assert "无法解析" in face.error


@pytest.mark.django_db
def test_only_one_font_is_processed_at_a_time(media_root):
    family = _family()
    busy = FontFace.objects.create(
        family=family, weight=700, status=FontFace.Status.PROCESSING
    )
    assert busy.status == FontFace.Status.PROCESSING
    waiting = services.add_face_from_bytes(
        family, make_font_bytes("ABC"), "test.ttf", weight=400
    )
    assert services.run_face_processing(waiting.pk) == "requeue"
    waiting.refresh_from_db()
    assert waiting.status == FontFace.Status.PENDING


@pytest.mark.django_db
def test_reprocess_clears_old_slice_files(media_root):
    family = _family()
    face = services.add_face_from_bytes(
        family, make_font_bytes(sample_chars(260)), "test.ttf", weight=400
    )
    services.run_face_processing(face.pk)
    face.refresh_from_db()
    first = [item["path"] for item in face.slices]
    services.run_face_processing(face.pk)
    face.refresh_from_db()
    assert [item["path"] for item in face.slices] == first
    for path in first:
        assert default_storage.exists(path)


# --- typography and stylesheet ----------------------------------------------


@pytest.mark.django_db
def test_defaults_generate_a_system_font_stylesheet(media_root):
    services.ensure_typography_rules()
    css = build_css(ordered_rules())
    assert "@font-face" not in css
    assert "--font-body: var(--font-fallback);" in css
    assert "--font-code: var(--font-mono-fallback);" in css


@pytest.mark.django_db
def test_custom_region_writes_font_face_and_variables(media_root):
    family = _family(name="思源宋体")
    face = services.add_face_from_bytes(
        family, make_font_bytes(sample_chars(260)), "test.ttf", weight=400
    )
    services.run_face_processing(face.pk)
    services.ensure_typography_rules()
    rule = TypographyRule.objects.get(region="h1")
    rule.mode = TypographyRule.Mode.CUSTOM
    rule.family = family
    rule.weight = 400
    rule.size_rem = "2.25"
    rule.line_height = "1.30"
    rule.full_clean()
    rule.save()

    css = build_css(ordered_rules())
    assert f'font-family: "{family.css_name}"' in css
    assert "unicode-range:" in css
    assert "font-display: swap;" in css
    assert f'--font-h1: "{family.css_name}", var(--font-fallback);' in css
    assert "--font-h1-weight: 400;" in css
    assert "--font-h1-size: 2.25rem;" in css
    assert "line-height: 1.3;" in css

    url = regenerate_font_css()
    assert url.startswith("/media/fonts/css/fonts.")
    assert SiteSettings.load().font_css_path == url


@pytest.mark.django_db
def test_inherit_region_pulls_its_weight_from_the_body_font(media_root):
    family = _family()
    _ready_face(family, weight=400)
    _ready_face(
        family,
        weight=700,
        slices=[
            {
                "path": "fonts/x/700-000.def.woff2",
                "unicode_range": "U+4E00",
                "bytes": 20,
            }
        ],
    )
    services.ensure_typography_rules()
    body = TypographyRule.objects.get(region="body")
    body.mode = TypographyRule.Mode.CUSTOM
    body.family = family
    body.weight = 400
    body.save()

    css = build_css(ordered_rules())
    assert "font-weight: 400;" in css
    assert "font-weight: 700;" in css  # h1 inherits the body font at 700
    assert css.count("@font-face") == 2
    assert services.enabled_variants() == [(family.pk, 400), (family.pk, 700)]


@pytest.mark.django_db
def test_missing_inherited_weight_only_warns(media_root):
    from core.fonts.forms import synthetic_weight_warnings

    family = _family()
    _ready_face(family, weight=400)
    services.ensure_typography_rules()
    body = TypographyRule.objects.get(region="body")
    body.mode = TypographyRule.Mode.CUSTOM
    body.family = family
    body.weight = 400
    body.save()

    warnings = synthetic_weight_warnings(
        TypographyRule.objects.select_related("family")
    )
    assert any("一级标题" in message and "700" in message for message in warnings)
    css = build_css(ordered_rules())
    assert css.count("@font-face") == 1  # no 700 file exists, so none is linked


@pytest.mark.django_db
def test_system_regions_do_not_pin_weight(media_root):
    services.ensure_typography_rules()
    css = build_css(ordered_rules())
    assert ".font-nav {" not in css


@pytest.mark.django_db
def test_region_rejects_weight_without_ready_face(media_root):
    family = _family()
    _ready_face(family, weight=400)
    services.ensure_typography_rules()
    rule = TypographyRule.objects.get(region="body")
    rule.mode = TypographyRule.Mode.CUSTOM
    rule.family = family
    rule.weight = 900
    with pytest.raises(ValidationError) as exc:
        rule.full_clean()
    assert "字重" in str(exc.value)


@pytest.mark.django_db
def test_body_region_cannot_inherit(media_root):
    services.ensure_typography_rules()
    rule = TypographyRule.objects.get(region="body")
    rule.mode = TypographyRule.Mode.INHERIT
    with pytest.raises(ValidationError):
        rule.full_clean()


@pytest.mark.django_db
def test_variant_warning_counts_font_weight_pairs(media_root):
    services.ensure_typography_rules()
    families = []
    for index in range(7):
        family = _family(name=f"字体{index}")
        _ready_face(family)
        families.append(family)
    rules = list(TypographyRule.objects.all())
    for rule, family in zip(rules, families, strict=False):
        rule.mode = TypographyRule.Mode.CUSTOM
        rule.family = family
        rule.weight = 400
        rule.save()
    assert "超过建议的 6 组" in variant_warning(TypographyRule.objects.all())


# --- deletion guard ----------------------------------------------------------


@pytest.mark.django_db
def test_font_in_use_cannot_be_deleted(media_root):
    family = _family()
    _ready_face(family)
    services.ensure_typography_rules()
    rule = TypographyRule.objects.get(region="h1")
    rule.mode = TypographyRule.Mode.CUSTOM
    rule.family = family
    rule.save()
    with pytest.raises(services.FontInUse) as exc:
        services.delete_family(family)
    assert "一级标题" in str(exc.value)
    assert FontFamily.objects.filter(pk=family.pk).exists()


@pytest.mark.django_db
def test_unused_font_deletes_its_files(media_root):
    family = _family()
    face = services.add_face_from_bytes(
        family, make_font_bytes(sample_chars(260)), "test.ttf", weight=400
    )
    services.run_face_processing(face.pk)
    face.refresh_from_db()
    paths = [item["path"] for item in face.slices]
    original = face.original_file.name
    services.delete_family(family)
    assert not FontFamily.objects.filter(pk=family.pk).exists()
    for path in paths:
        assert not default_storage.exists(path)
    assert not default_storage.exists(original)


# --- downloads ---------------------------------------------------------------


def test_download_rejects_non_https_and_internal_hosts():
    with pytest.raises(DownloadError):
        fetch_bytes("http://example.com/font.ttf")
    with pytest.raises(DownloadError):
        fetch_bytes("https://localhost/font.ttf")
    with pytest.raises(DownloadError):
        fetch_bytes("https://127.0.0.1/font.ttf")


def test_google_css_parsing():
    css = """
    /* [1] */
    @font-face {
      font-family: 'Noto Serif SC';
      font-style: normal;
      font-weight: 700;
      font-display: swap;
      src: url(https://fonts.gstatic.com/s/notoserifsc/v1/slice1.woff2) format('woff2');
      unicode-range: U+4E00-4E05, U+4E07;
    }
    """
    faces = parse_google_css(css)
    assert faces == [
        {
            "weight": 700,
            "style": "normal",
            "url": "https://fonts.gstatic.com/s/notoserifsc/v1/slice1.woff2",
            "unicode_range": "U+4E00-4E05, U+4E07",
        }
    ]


def test_google_css_rejects_foreign_hosts():
    css = """
    @font-face {
      font-family: 'X';
      font-weight: 400;
      src: url(https://evil.example.com/x.woff2) format('woff2');
    }
    """
    with pytest.raises(DownloadError):
        parse_google_css(css)


# --- admin -------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_pages_are_superuser_only(client, media_root):
    services.ensure_typography_rules()
    client.force_login(_staff_user())
    for name in ("core_font_index", "core_font_add", "core_typography"):
        # Wagtail turns PermissionDenied inside the admin into a redirect home.
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url == "/admin/"

    client.force_login(_superuser())
    for name in ("core_font_index", "core_font_add", "core_typography"):
        assert client.get(reverse(name)).status_code == 200


@pytest.mark.django_db
def test_admin_uploads_and_shows_font(client, media_root):
    client.force_login(_superuser())
    response = client.post(
        reverse("core_font_add"),
        {
            "submit_upload": "1",
            "upload-name": "验收字体",
            "upload-weight": "400",
            "upload-style": "normal",
            "upload-license_type": FontFamily.License.OPEN_SOURCE,
            "upload-license_note": "SIL OFL 1.1",
            "upload-license_confirmed": "on",
            "upload-file": SimpleUploadedFile(
                "test.ttf", make_font_bytes(sample_chars(260)), "font/ttf"
            ),
        },
        follow=True,
    )
    assert response.status_code == 200
    family = FontFamily.objects.get(name="验收字体")
    assert family.css_name == "sjtu-font-1"
    face = family.faces.get()
    assert face.status == FontFace.Status.PENDING
    assert "正在后台处理" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_typography_form_saves_and_regenerates(client, media_root):
    services.ensure_typography_rules()
    client.force_login(_superuser())
    response = client.get(reverse("core_typography"))
    assert response.status_code == 200

    rules = sorted(TypographyRule.objects.all(), key=lambda rule: rule.pk)
    data = {
        "form-TOTAL_FORMS": str(len(rules)),
        "form-INITIAL_FORMS": str(len(rules)),
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    for index, rule in enumerate(rules):
        data[f"form-{index}-id"] = str(rule.pk)
        data[f"form-{index}-mode"] = rule.mode
        data[f"form-{index}-family"] = ""
        data[f"form-{index}-weight"] = str(rule.weight)
        data[f"form-{index}-size_rem"] = ""
        data[f"form-{index}-line_height"] = "1.70" if rule.region == "body" else ""
        data[f"form-{index}-letter_spacing_em"] = ""
    response = client.post(reverse("core_typography"), data, follow=True)
    assert response.status_code == 200
    assert TypographyRule.objects.get(region="body").line_height is not None

    css_path = SiteSettings.load().font_css_path
    stored = css_path.replace("/media/", "")
    with default_storage.open(stored) as handle:
        assert "line-height: 1.7;" in handle.read().decode("utf-8")


@pytest.mark.django_db
def test_front_end_links_the_generated_stylesheet(client, media_root):
    call_command("init_site", verbosity=0)
    response = client.get("/")
    html = response.content.decode("utf-8")
    assert "/media/fonts/css/fonts." in html
