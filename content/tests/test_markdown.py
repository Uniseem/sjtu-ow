"""Bodies and event descriptions in Markdown (design 5.2, v6.70; round 192).

Until v6.70 article and page bodies were StreamFields and tournament
descriptions Draftail rich text; the user found the block editor
uncomfortable and asked for a standard Markdown editor.
"""

import json
from datetime import timedelta
from io import BytesIO

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PILImage
from wagtail.images.models import Image

from accounts.models import User
from accounts.services import GROUP_CONTENT, GROUP_SCRIM
from content import legacy_body
from content.markdown import analyse, plain_text, render
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from content.services import SUBMISSION_IMAGE_COLLECTION

BV = "https://www.bilibili.com/video/BV1xx411c7mD"


def html(source):
    return str(render(source))


# --- the renderer ------------------------------------------------------------


def test_html_is_shown_as_text_and_bad_links_are_not_links():
    out = html(
        '<script>alert(1)</script> <b onclick="x">粗</b>\n\n[点](javascript:alert(1))'
    )
    assert "<script>" not in out and "<b " not in out
    assert "&lt;script&gt;" in out
    assert 'href="javascript' not in out


def test_one_newline_is_a_line_break():
    assert html("第一行\n第二行") == "<p>第一行<br />\n第二行</p>\n"


def test_headings_are_second_and_third_level_only():
    out = html("# 一\n\n## 二\n\n### 三\n\n#### 四\n\n###### 六")
    assert out.count("<h2>") == 2 and out.count("<h3>") == 3
    assert "<h1" not in out and "<h4" not in out and "<h6" not in out


def test_an_image_alone_is_a_figure_with_its_caption():
    out = html("![决赛现场](/media/images/final.jpg)")
    assert out == (
        '<figure><img src="/media/images/final.jpg" alt="决赛现场" loading="lazy">'
        "<figcaption>决赛现场</figcaption></figure>\n"
    )
    two = html("![一](/media/a.png)\n![二](/media/b.png)")
    assert two.count("<figure>") == 2


def test_only_this_sites_images_are_shown(settings):
    settings.SITE_URL = "https://ow.example.com"
    outside = html("![外站](https://evil.example/x.png)")
    assert "<img" not in outside
    assert '<a href="https://evil.example/x.png">外站</a>' in outside
    inline = html("文字 ![外站](https://evil.example/x.png) 文字")
    assert "<img" not in inline
    assert "<img" not in html("![数据](data:image/png;base64,iVBORw0KGgo=)")
    assert "<img" in html("![本站](https://ow.example.com/media/a.png)")
    assert "<img" in html("文字 ![小图](/media/a.png) 文字")


def test_a_bilibili_link_alone_is_the_player():
    for source in (BV, f"<{BV}>", f"[看比赛]({BV})"):
        out = html(source)
        assert (
            '<iframe src="https://player.bilibili.com/player.html?bvid=BV1xx411c7mD"'
            in out
        )
    inline = html(f"比赛录像：{BV} 欢迎观看")
    assert "<iframe" not in inline and f'<a href="{BV}">' in inline
    assert "<iframe" not in html("https://example.com/video/BV1xx411c7mD")


@pytest.mark.django_db
def test_a_short_link_is_looked_up_once(monkeypatch):
    from content import embeds

    calls = []

    def follow(url):
        calls.append(url)
        return BV + "?p=2"

    monkeypatch.setattr(embeds, "follow_b23", follow)
    out = html("https://b23.tv/abcdef")
    assert "bvid=BV1xx411c7mD&amp;page=2" in out
    html("https://b23.tv/abcdef")
    assert len(calls) == 1  # Wagtail keeps the answer


def test_pasted_addresses_become_links_without_the_full_stop():
    out = html("详见 https://ow.example.com/rules. 谢谢，https://a.example/x，再见")
    assert (
        '<a href="https://ow.example.com/rules">https://ow.example.com/rules</a>.'
        in out
    )
    assert '<a href="https://a.example/x">https://a.example/x</a>，' in out


def test_tables_scroll_and_quotes_keep_their_source():
    table = html("| 位置 | 人数 |\n| --- | --- |\n| 坦克 | 1 |")
    assert table.startswith('<div class="c-prose__table"><table>')
    quote = html("> 一起进步。\n> ——社团负责人")
    assert quote == (
        "<blockquote>\n<p>一起进步。</p>\n<footer>——社团负责人</footer>\n</blockquote>\n"
    )
    assert "<footer>" not in html("> 普通的话\n> 第二行")


def test_plain_text_is_what_a_reader_sees():
    text = plain_text("## 标题\n\n**粗** 和 [链接](https://example.com/secret) &lt;")
    assert text == "标题\n粗 和 链接 &lt;".replace("&lt;", "<")
    assert "secret" not in text and "**" not in text


def test_word_counts_leave_out_markup_and_addresses():
    """Design-details 6.3: what the reader sees, images and videos aside."""
    from content.article_meta import facts

    result = facts(
        f"**五个字啊啊** [看](https://example.com/abc/def)\n\n![图注](/media/a.png)\n\n{BV}"
    )
    assert result.words == 5 + 1 + 2  # the caption counts, the address not
    assert (result.images, result.videos) == (1, 1)
    assert analyse("").html == ""


def test_what_the_renderer_emits_has_its_styles(settings):
    """The classes are written in Python, where nothing else would notice a
    renamed rule; the admin preview copies the public prose."""
    site = (settings.BASE_DIR / "assets" / "css" / "input.css").read_text(
        encoding="utf-8"
    )
    for rule in (".c-prose__table {", ".c-prose__video {", ".c-prose pre {"):
        assert rule in site, rule
    editor = (settings.BASE_DIR / "static" / "css" / "markdown-editor.css").read_text(
        encoding="utf-8"
    )
    for rule in (
        ".md-field .EasyMDEContainer .CodeMirror {",
        ".md-field .md-preview h2 {",
        ".md-field .md-preview blockquote footer {",
        ".md-help {",
    ):
        assert rule in editor, rule
    # The widget brings it, after EasyMDE's own sheet (v7.0).
    from content.widgets import MarkdownEditor

    css = MarkdownEditor().media._css["all"]
    assert css == ["vendor/easymde/easymde.min.css", "css/markdown-editor.css"]


# --- where the body is read -------------------------------------------------


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)
    return ArticleIndexPage.objects.get(slug="news")


def _person(email, nickname, *groups, **extra):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
        **extra,
    )
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    return User.objects.get(pk=user.pk)


def _article(news, body, **fields):
    author = fields.pop("author", None) or _person("writer@example.com", "写手")
    page = ArticlePage(
        title=fields.pop("title", "测试文章"),
        slug=fields.pop("slug", "md-article"),
        category=ArticleCategory.objects.get(slug="guide"),
        author=author,
        owner=author,
        summary="摘要",
        body=body,
    )
    news.add_child(instance=page)
    page.save_revision().publish()
    return ArticlePage.objects.get(pk=page.pk)


@pytest.mark.django_db
def test_the_article_page_shows_the_markdown(client, site):
    article = _article(site, "开头 **加粗**\n\n## 第一节\n\n- 甲\n- 乙\n\n<i>不收</i>")
    page = client.get(article.url).content.decode("utf-8")
    body = page[page.index('<div class="c-prose">') :]
    assert "<strong>加粗</strong>" in body
    assert '<h2 id="h-1">第一节</h2>' in body
    assert "<li>甲</li>" in body
    assert "&lt;i&gt;不收&lt;/i&gt;" in body


@pytest.mark.django_db
def test_search_matches_the_words_not_the_markup(client, site):
    _article(site, "看 [这篇攻略](https://example.com/hiddenword) 里的 **龙刃** 时机")
    hits = client.get("/search/", {"q": "hiddenword"}).content.decode("utf-8")
    assert "测试文章" not in hits
    found = client.get("/search/", {"q": "龙刃"}).content.decode("utf-8")
    assert "测试文章" in found and "**" not in found


@pytest.mark.django_db
def test_review_gets_the_body_as_written(site):
    from moderation.integrations import page_text

    article = _article(site, "正文里有 [链接](https://spam.example/)")
    assert "https://spam.example/" in page_text(article)


@pytest.mark.django_db
def test_event_pages_show_their_descriptions_as_markdown(client, site):
    from scrims.tests.test_scrims import make_scrim
    from tournaments.models import Tournament, TournamentStatus

    now = timezone.now()
    tournament = Tournament.objects.create(
        registration_mode="team",
        title="说明赛",
        description="## 赛制\n\n**双败**淘汰",
        registration_opens_at=now - timedelta(days=1),
        registration_closes_at=now + timedelta(days=1),
        roster_min=2,
        roster_max=3,
        status=TournamentStatus.PUBLISHED,
        published_at=now,
    )
    page = client.get(tournament.get_absolute_url()).content.decode("utf-8")
    assert "<h2>赛制</h2>" in page and "<strong>双败</strong>" in page
    scrim = make_scrim(description="带上**耳机**\n八点开始")
    page = client.get(f"/scrims/{scrim.pk}/").content.decode("utf-8")
    assert "带上<strong>耳机</strong><br />" in page


@pytest.mark.django_db
def test_the_new_scrim_letter_carries_plain_words():
    from scrims.notifications import new_scrim_letter
    from scrims.tests.test_scrims import make_scrim

    scrim = make_scrim(
        description="**周五**见，[规则](https://ow.example.com/r)",
        signup_closes_at=timezone.now() + timedelta(hours=12),
    )
    letter = new_scrim_letter(scrim)
    assert letter.paragraphs == ["周五见，规则"]


# --- the editor ---------------------------------------------------------------


@pytest.mark.django_db
def test_every_body_and_description_gets_the_editor(client, site):
    from scrims.tests.test_scrims import make_scrim
    from tournaments.models import Tournament

    root = _person("root@example.com", "站长", is_superuser=True, is_staff=True)
    client.force_login(root)
    article = _article(site, "正文")
    now = timezone.now()
    tournament = Tournament.objects.create(
        registration_mode="team",
        title="编辑器赛",
        registration_opens_at=now,
        registration_closes_at=now + timedelta(days=1),
        roster_min=2,
        roster_max=3,
    )
    scrim = make_scrim()
    from content.models import StandardPage

    terms = StandardPage.objects.get(slug="terms")
    for url in (
        reverse("backoffice:article_edit", args=[article.pk]),
        reverse("backoffice:article_new"),
        reverse("backoffice:page_edit", args=[terms.pk]),
        reverse("backoffice:index_intro"),
        reverse("tournaments:edit", args=[tournament.pk]),
        reverse("scrims:edit", args=[scrim.pk]),
    ):
        page = client.get(url).content.decode("utf-8")
        assert "data-markdown-editor" in page, url
        assert "vendor/easymde/easymde.min.js" in page, url
        assert "js/markdown-editor.js" in page, url
        assert reverse("content_markdown_preview") in page, url
        # Nothing from other sites: no Font Awesome, no CDN.
        assert "bootstrapcdn" not in page and "fontawesome" not in page.lower()


def test_the_editor_script_loads_nothing_from_elsewhere(settings):
    script = (settings.BASE_DIR / "static" / "js" / "markdown-editor.js").read_text(
        encoding="utf-8"
    )
    assert "autoDownloadFontAwesome: false" in script
    assert "spellChecker: false" in script
    assert "previewRender: renderPreview" in script


@pytest.mark.django_db
def test_the_preview_is_the_public_rendering(client, site):
    writer = _person("pv@example.com", "预览者", GROUP_CONTENT)
    url = reverse("content_markdown_preview")
    source = "## 标题\n\n<script>x</script>\n\n" + BV
    assert client.post(url, {"text": source}).status_code != 200  # not signed in
    client.force_login(writer)
    response = client.post(url, {"text": source})
    assert response.status_code == 200
    assert response.content.decode("utf-8") == html(source)
    assert client.get(url).status_code == 405


def _png(name="shot.png"):
    buffer = BytesIO()
    PILImage.new("RGB", (2400, 1200), color=(200, 40, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_an_upload_lands_in_the_submission_collection(client, site, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from allauth.account.models import EmailAddress

    from content.permissions import is_submitter_only

    writer = _person("up@example.com", "投稿人")
    EmailAddress.objects.create(
        user=writer, email=writer.email, verified=True, primary=True
    )
    writer = User.objects.get(pk=writer.pk)
    assert is_submitter_only(writer)  # verified members write through 投稿者
    client.force_login(writer)
    response = client.post(reverse("content_markdown_image"), {"image": _png()})
    assert response.status_code == 200, response.content
    image = Image.objects.get(title="shot")
    assert image.collection.name == SUBMISSION_IMAGE_COLLECTION
    assert image.uploaded_by_user == writer
    url = json.loads(response.content)["url"]
    assert url.startswith(settings.MEDIA_URL) and "max-1600x1600" in url
    assert image.get_rendition("max-1600x1600").width == 1600


@pytest.mark.django_db
def test_managers_upload_even_outside_the_submitters(client, site, settings, tmp_path):
    """User 10-04: everyone who writes can add pictures. These managers have
    no verified address, so they are not in 投稿者."""
    from accounts.services import GROUP_TOURNAMENT
    from content.permissions import is_submitter_only

    settings.MEDIA_ROOT = tmp_path
    for number, group in enumerate((GROUP_SCRIM, GROUP_TOURNAMENT)):
        manager = _person(f"m{number}@example.com", f"管理员{number}", group)
        assert not manager.groups.filter(name="投稿者").exists()
        assert not is_submitter_only(manager)
        client.force_login(manager)
        upload = _png(f"event-{number}.png")
        response = client.post(reverse("content_markdown_image"), {"image": upload})
        assert response.status_code == 200, (group, response.content)
        image = Image.objects.get(title=f"event-{number}")
        assert image.collection.name == SUBMISSION_IMAGE_COLLECTION


@pytest.mark.django_db
def test_uploads_need_the_right_to_add_images(client, site, settings, tmp_path):
    """Someone in the admin with no image rights at all (a group made by hand
    with only admin access) is turned away."""
    from django.contrib.auth.models import Permission

    settings.MEDIA_ROOT = tmp_path
    bare = Group.objects.create(name="只能进后台")
    bare.permissions.add(Permission.objects.get(codename="access_admin"))
    person = _person("bare@example.com", "无图权限", "只能进后台")
    client.force_login(person)
    response = client.post(reverse("content_markdown_image"), {"image": _png()})
    assert response.status_code == 403
    assert "权限" in json.loads(response.content)["error"]
    assert not Image.objects.filter(title="shot").exists()


@pytest.mark.django_db
def test_a_file_that_is_not_an_image_is_refused(client, site, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    editor = _person("ed@example.com", "编辑", GROUP_CONTENT)
    client.force_login(editor)
    url = reverse("content_markdown_image")
    fake = SimpleUploadedFile("note.png", b"not an image", content_type="image/png")
    response = client.post(url, {"image": fake})
    assert response.status_code == 400 and json.loads(response.content)["error"]
    assert client.post(url, {}).status_code == 400
    assert not Image.objects.filter(title="note").exists()


# --- what was written before v6.70 -------------------------------------------


def test_old_rich_text_turns_into_the_same_markdown_page():
    old = (
        '<p>开头<b>加粗</b>、<i>斜体</i>和<a href="https://example.com/a">链接</a>。</p>'
        "<h2>一节</h2><h3>小节</h3>"
        "<ul><li>甲</li><li>乙</li></ul><ol><li>一</li><li>二</li></ol>"
        "<p>1. 不是列表 * 也不是强调</p><hr/>"
        "<p>第一行<br/>第二行</p>"
    )
    markdown = legacy_body.from_html(old)
    out = html(markdown)
    for piece in (
        "<strong>加粗</strong>",
        "<em>斜体</em>",
        '<a href="https://example.com/a">链接</a>',
        "<h2>一节</h2>",
        "<h3>小节</h3>",
        "<li>甲</li>\n<li>乙</li>",
        "<ol>\n<li>一</li>",
        "<p>1. 不是列表 * 也不是强调</p>",
        "<hr />",
        "第一行<br />",
    ):
        assert piece in out, piece


def test_old_blocks_turn_into_markdown():
    raw = json.dumps(
        [
            {"type": "paragraph", "value": "<p>正文</p>"},
            {"type": "image", "value": {"image": 7, "caption": "现场"}},
            {"type": "quote", "value": {"text": "说过的话", "attribution": "某人"}},
            {"type": "video", "value": BV},
            {"type": "paragraph", "value": '<p><a linktype="page" id="3">站内</a></p>'},
        ]
    )
    markdown = legacy_body.from_stream(
        raw,
        link_for=lambda attrs: f"/page-{attrs['id']}/",
        image_for=lambda attrs: f"/media/original_images/{attrs['id']}.jpg",
    )
    assert markdown == (
        "正文\n\n![现场](/media/original_images/7.jpg)\n\n> 说过的话\n> ——某人\n\n"
        f"{BV}\n\n[站内](/page-3/)"
    )
    out = html(markdown)
    assert "<figcaption>现场</figcaption>" in out
    assert "<footer>——某人</footer>" in out
    assert "<iframe" in out
    assert legacy_body.from_stream("已经是 Markdown") == "已经是 Markdown"
    assert legacy_body.from_stream("[]") == ""
