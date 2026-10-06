"""217 复核 08 块的复现（只记录，不修）。

在测试机上跑：
  bash scripts/remote-check.sh run uv run pytest -q -s \
    handoff/rounds/217-second-review/findings/08-repro_test.py

每条 test 都断言「缺陷存在」：绿 = 已复现；修好以后这些断言会红。
"""

import os
import struct
import time

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from content.models import ArticlePage
from core import prerender
from core.fonts import download, services
from core.fonts.css import regenerate_font_css
from core.fonts.forms import FontUploadForm
from core.fonts.processing import FontError, inspect_font
from core.models import FontFace, FontFamily, PrerenderedPage, TypographyRule
from core.tests.fonts_factory import make_font_bytes, sample_chars
from core.tests.test_fonts import media_root  # noqa: F401 — fixture
from core.tests.test_prerender import _article, prerender_root, site_tree  # noqa: F401

GOOGLE_CSS = """
@font-face {
  font-family: 'Noto Sans SC';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/notosanssc/v1/same.0.woff2) format('woff2');
  unicode-range: U+4e00-4e0f;
}
@font-face {
  font-family: 'Noto Sans SC';
  font-style: normal;
  font-weight: 700;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/notosanssc/v1/same.0.woff2) format('woff2');
  unicode-range: U+4e00-4e0f;
}
"""


# --- 08-1 Google 字体：删一个字重把另一个字重的分片也删了 -----------------------


@pytest.mark.django_db
def test_08_1_deleting_unused_google_weight_deletes_used_weights_files(
    media_root, monkeypatch  # noqa: F811
):
    monkeypatch.setattr(download, "fetch_google_css", lambda family, weights: GOOGLE_CSS)
    monkeypatch.setattr(download, "fetch_bytes", lambda url, **kw: b"VARIABLE-WOFF2")
    family = services.create_family(
        name="思源（Google）",
        source=FontFamily.Source.GOOGLE_FONTS,
        source_ref="Noto Sans SC",
        license_type=FontFamily.License.OPEN_SOURCE,
    )
    services.add_google_faces(family, ["400", "700"])
    face400 = FontFace.objects.get(family=family, weight=400)
    face700 = FontFace.objects.get(family=family, weight=700)
    print("\n400 的分片：", face400.slices)
    print("700 的分片：", face700.slices)
    assert face400.slices[0]["path"] == face700.slices[0]["path"]

    # 一级标题用 700；400 没人用，后台允许删。
    services.ensure_typography_rules()
    TypographyRule.objects.filter(region="h1").update(
        mode=TypographyRule.Mode.CUSTOM, family=family, weight=700
    )
    assert services.is_face_in_use(face700)
    assert not services.is_face_in_use(face400)

    services.delete_face(face400)

    face700.refresh_from_db()
    path = face700.slices[0]["path"]
    print("删掉 400 以后，700 的状态：", face700.status, "；分片文件还在吗：",
          default_storage.exists(path))
    from core.models import SiteSettings

    css_url = SiteSettings.load().font_css_path
    css = default_storage.open(css_url.removeprefix("/media/")).read().decode()
    print("当前样式表仍引用：", path in css)
    assert face700.status == FontFace.Status.READY
    assert not default_storage.exists(path)  # 缺陷：正在用的 700 的文件没了


# --- 08-2 旧样式表按「创建时间」删，用了很久的那份一换就删 -------------------------


@pytest.mark.django_db
def test_08_2_long_lived_stylesheet_is_deleted_the_moment_it_is_replaced(
    media_root  # noqa: F811
):
    services.ensure_typography_rules()
    old_url = regenerate_font_css()
    old_name = old_url.removeprefix("/media/")
    old_file = media_root / old_name
    ten_days = time.time() - 10 * 86400
    os.utime(old_file, (ten_days, ten_days))  # 10 天前生成、一直在用

    TypographyRule.objects.filter(region="body").update(line_height="1.8")
    new_url = regenerate_font_css()
    print("\n旧样式表", old_url, "→ 新样式表", new_url)
    print("旧样式表还在吗：", old_file.exists())
    assert new_url != old_url
    assert not old_file.exists()  # 缺陷：设计 13.12.4 要保留一天


# --- 08-3 坏字体让上传表单抛 500 -----------------------------------------------


def _with_table_length(data: bytes, tag: bytes, length: int) -> bytes:
    num = struct.unpack(">H", data[4:6])[0]
    out = bytearray(data)
    for i in range(num):
        start = 12 + 16 * i
        if data[start : start + 4] == tag:
            out[start + 12 : start + 16] = struct.pack(">L", length)
            return bytes(out)
    raise AssertionError(tag)


@pytest.mark.parametrize("tag", [b"OS/2", b"name", b"head"])
def test_08_3_truncated_table_escapes_as_non_font_error(tag):
    data = _with_table_length(make_font_bytes(sample_chars(40)), tag, 6)
    try:
        inspect_font(data)
    except FontError as exc:
        print(f"\n{tag!r}: FontError（正常）", exc)
        raise AssertionError("这一种是好好报错的") from exc
    except Exception as exc:  # noqa: BLE001
        print(f"\n{tag!r}: inspect_font 抛出 {type(exc).__name__}: {exc}")
        form = FontUploadForm(
            data={
                "upload-name": "坏字体",
                "upload-license_type": "open_source",
                "upload-license_confirmed": "on",
            },
            files={"upload-file": SimpleUploadedFile("bad.ttf", data)},
            prefix="upload",
        )
        with pytest.raises(Exception) as caught:
            form.is_valid()
        print("    表单 is_valid() 也抛：", type(caught.value).__name__)
        assert not isinstance(caught.value, FontError)


# --- 08-4 生成和下线并发：下线后又把静态文件写回去 --------------------------------


@pytest.mark.django_db
def test_08_4_generate_racing_unpublish_writes_the_file_back(
    prerender_root, site_tree, monkeypatch  # noqa: F811
):
    page = _article(title="将被撤回", slug="racing-unpublish")
    path = page.get_url()
    prerender.generate(path)  # 文章在线时生成过一次
    assert prerender.file_for(path).exists()
    real_render = prerender.render_html

    def render_then_unpublish(p):
        html = real_render(p)  # worker 渲染时文章还在线
        ArticlePage.objects.get(pk=page.pk).unpublish()  # 这时 web 撤回发布并提交
        prerender._remove_now(p)  # web 在提交后立即删（215 的做法）
        return html

    monkeypatch.setattr(prerender, "render_html", render_then_unpublish)
    record = prerender.generate(path)
    live = ArticlePage.objects.get(pk=page.pk).live
    print(f"\n文章 live={live}；静态文件存在={prerender.file_for(path).exists()}；"
          f"记录={record.status}")
    print("全量目标里还有它吗：", path in prerender.page_targets())
    assert not live
    assert prerender.file_for(path).exists()  # 缺陷：撤回的文章又被 Caddy 公开
    assert PrerenderedPage.objects.filter(path=path, status="ready").exists()


# --- 08-5 Wagtail 页面隐私（要登录）以后，静态文件照旧公开 ---------------------------


@pytest.mark.django_db
def test_08_5_view_restriction_leaves_the_static_file_public(
    prerender_root, site_tree, client  # noqa: F811
):
    from wagtail.models import PageViewRestriction

    page = _article(title="将设为仅登录可见", slug="soon-private")
    path = page.get_url()
    prerender.generate(path)
    assert prerender.file_for(path).exists()

    PageViewRestriction.objects.create(
        page=page, restriction_type=PageViewRestriction.LOGIN
    )
    anonymous = client.get(path)
    print(f"\n设了「要登录」后匿名访问 Django：{anonymous.status_code} "
          f"{anonymous.headers.get('Location')}")
    record = prerender.generate(path)
    print(f"重新生成：{record.status} {record.error}")
    print("静态文件还在：", prerender.file_for(path).exists(),
          "；还在全量目标里：", path in prerender.page_targets())
    assert prerender.file_for(path).exists()  # 缺陷：Caddy 照旧给所有人看


# --- 08-8 重新处理时，先处理完的字重把另一个字重踢出线上样式表 -------------------------


def _current_css():
    from core.models import SiteSettings

    url = SiteSettings.load().font_css_path
    return default_storage.open(url.removeprefix("/media/")).read().decode()


def _uploaded_family_with(weights):
    family = services.create_family(
        name="上传字体",
        source=FontFamily.Source.UPLOAD,
        license_type=FontFamily.License.OPEN_SOURCE,
    )
    for weight in weights:
        services.add_face_from_bytes(
            family,
            make_font_bytes(sample_chars(30), weight=weight),
            f"f{weight}.ttf",
            weight=weight,
        )
    for face in FontFace.objects.filter(family=family):
        assert services.run_face_processing(face.pk) == "done"
    return family


FACE_700 = "  font-weight: 700;\n  font-style: normal;"


@pytest.mark.django_db
def test_08_8_reprocess_drops_the_other_weight_from_the_live_stylesheet(
    media_root  # noqa: F811
):
    family = _uploaded_family_with([400, 700])
    services.ensure_typography_rules()
    TypographyRule.objects.filter(region="body").update(
        mode=TypographyRule.Mode.CUSTOM, family=family, weight=400
    )
    TypographyRule.objects.filter(region="h1").update(
        mode=TypographyRule.Mode.CUSTOM, family=family, weight=700
    )
    regenerate_font_css()
    before = _current_css().count(FACE_700)

    services.reprocess_family(family)  # 后台点「重新处理」：两个字重都回到 PENDING
    face400 = FontFace.objects.get(family=family, weight=400)
    services.run_face_processing(face400.pk)  # worker 先做完 400，重写样式表
    after = _current_css().count(FACE_700)
    print(f"\n700 的 @font-face 块：重新处理前 {before} 个，400 处理完后 {after} 个；"
          f"700 此时状态 {FontFace.objects.get(family=family, weight=700).status}")
    assert before > 0
    assert after == 0  # 缺陷：一级标题在 700 处理完之前用不上自己的字体


# --- 08-9 删字体先删文件、后删记录；记录删不掉时文件已经没了 ---------------------------


@pytest.mark.django_db
def test_08_9_delete_family_removes_files_then_fails_on_protect(
    media_root  # noqa: F811
):
    from django.db.models import ProtectedError

    from core import autosave
    from core.fonts.forms import TypographyRuleForm

    family = _uploaded_family_with([700])
    services.ensure_typography_rules()
    TypographyRule.objects.filter(region="h2").update(
        mode=TypographyRule.Mode.CUSTOM, family=family, weight=700
    )
    rule = TypographyRule.objects.get(region="h2")

    # 自动保存（13.17）：改「字体来源」为系统字体的同时，字间距框里正打着「-」。
    form = TypographyRuleForm(
        data={
            "mode": "system",
            "family": str(family.pk),
            "weight": "700",
            "size_rem": "",
            "line_height": "",
            "letter_spacing_em": "-",
        },
        instance=rule,
    )
    saved = autosave.save_valid_fields(form)
    rule.refresh_from_db()
    print(f"\n自动保存存下 {saved}；h2 现在 mode={rule.mode} family_id={rule.family_id}")
    assert rule.mode == "system" and rule.family_id == family.pk

    face = FontFace.objects.get(family=family)
    paths = [item["path"] for item in face.slices]
    with pytest.raises(ProtectedError):
        services.delete_family(family)  # 后台「删除」：没有区域在用它，允许删
    face.refresh_from_db()
    left = [default_storage.exists(path) for path in paths]
    print(f"删除抛 ProtectedError（页面 500）；字体仍在库里={FontFamily.objects.filter(pk=family.pk).exists()}，"
          f"字重状态={face.status}，分片文件还在={left}，原文件还在="
          f"{default_storage.exists(face.original_file.name)}")
    assert not any(left)  # 缺陷：记录还说「可用」，文件已经删了
