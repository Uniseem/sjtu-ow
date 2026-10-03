"""The 默认封面 pool (design 13.2.5, v6.7, round 109): objects without a
cover take an official picture the club uploaded, drifting slowly; an empty
pool falls back to the drawn placeholders."""

from io import BytesIO
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.template import Context, Template
from django.utils import timezone
from PIL import Image as PILImage

from core.covers import DEFAULT_COVER_COLLECTION


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _pool():
    from wagtail.models import Collection

    return Collection.objects.get(name=DEFAULT_COVER_COLLECTION)


def _picture(collection, name="wallpaper"):
    from wagtail.images.models import Image

    buffer = BytesIO()
    PILImage.new("RGB", (320, 180), (40, 90, 160)).save(buffer, "PNG")
    return Image.objects.create(
        title=name,
        width=320,
        height=180,
        collection=collection,
        file=ContentFile(buffer.getvalue(), name=f"{name}.png"),
    )


def _article(slug="pool-article", cover=None):
    from content.models import ArticleCategory, ArticleIndexPage
    from content.tests.test_content import _article as make
    from members.tests.test_members import person

    news = ArticleIndexPage.objects.get(slug="news")
    return make(
        news,
        ArticleCategory.objects.get(slug="guide"),
        person(f"作者{slug}"),
        title=f"文章 {slug}",
        slug=slug,
        cover=cover,
    )


def _tag(obj, spec="fill-960x540-c50", extra=""):
    template = Template("{% load ow %}{% cover_fallback obj spec " + extra + " %}")
    return template.render(Context({"obj": obj, "spec": spec}))


# --- the pool itself -------------------------------------------------------------


@pytest.mark.django_db
def test_init_site_makes_the_pool(site):
    assert _pool().name == DEFAULT_COVER_COLLECTION


@pytest.mark.django_db
def test_an_empty_pool_falls_back_to_the_drawn_placeholder(site):
    from core import placeholders

    article = _article()
    html = _tag(article)
    assert placeholders.static_path(article).split("/")[-1].split(".")[0] in html
    assert "c-drift" not in html
    assert 'width="960" height="540"' in html


@pytest.mark.django_db
def test_each_object_keeps_its_own_pool_picture(site):
    """(ID + offset) mod size, as the placeholders: same object, same picture;
    an article and a tournament with the same id do not collide."""
    from core import covers
    from tournaments.models import Tournament

    pictures = [_picture(_pool(), f"p{i}") for i in range(3)]
    article = _article()
    expected = pictures[article.pk % 3]
    html = _tag(article)
    assert expected.get_rendition("fill-960x540-c50").url in html
    assert _tag(article) == html  # every time
    now = timezone.now()
    tournament = Tournament(
        pk=article.pk,
        title="同号赛事",
        registration_opens_at=now,
        registration_closes_at=now,
    )
    assert covers.pick(tournament, pictures) == pictures[(article.pk + 13) % 3]


@pytest.mark.django_db
def test_pool_pictures_drift_and_keep_the_spots_class_and_size(site):
    _picture(_pool())
    article = _article()
    html = _tag(article, "fill-2400x1200-c50", '"c-cover__img"')
    variant = article.pk % 4 + 1
    assert f'class="c-cover__img c-drift c-drift--{variant}"' in html
    assert 'width="2400" height="1200"' in html
    assert "loading" not in html  # a first-screen picture
    assert 'loading="lazy"' in _tag(article, extra="lazy=True")


@pytest.mark.django_db
def test_pictures_elsewhere_are_not_in_the_pool(site):
    from wagtail.models import Collection

    _picture(Collection.get_first_root_node(), "not-a-cover")
    assert "c-drift" not in _tag(_article())


# --- on the pages ------------------------------------------------------------------


@pytest.mark.django_db
def test_articles_without_a_cover_show_a_pool_picture_on_the_list_and_page(
    client, site
):
    from wagtail.models import Collection

    picture = _picture(_pool())
    plain = _article("plain")
    own = _picture(Collection.get_first_root_node(), "own-cover")
    covered = _article("covered", cover=own)
    card = picture.get_rendition("fill-960x540-c50").url
    listing = client.get("/news/").content.decode()
    assert f'<img src="{card}" width="960" height="540" class="c-drift' in listing
    head = picture.get_rendition("fill-2400x1200-c50").url
    page = client.get(plain.url).content.decode()
    assert (
        f'<img src="{head}" width="2400" height="1200" class="c-cover__img c-drift'
        in page
    )
    # An uploaded cover is shown as it is: no drift.
    own = client.get(covered.url).content.decode()
    assert "c-cover__img c-drift" not in own


@pytest.mark.django_db
def test_scrim_banners_take_a_pool_picture(client, site):
    from scrims.models import Scrim, ScrimStatus

    _picture(_pool())
    scrim = Scrim.objects.create(
        title="图库内战", starts_at=timezone.now(), status=ScrimStatus.PUBLISHED
    )
    html = client.get(f"/scrims/{scrim.pk}/").content.decode()
    assert "c-stage__img c-drift" in html


def test_no_template_reaches_for_the_placeholder_directly():
    """Every cover spot goes through cover_fallback, so the pool reaches all."""
    root = Path(settings.BASE_DIR)
    skip = {".venv", "node_modules", "prerendered", "staticfiles", "handoff", "media"}
    found = [
        p.as_posix()
        for p in root.rglob("*.html")
        if not skip & set(p.relative_to(root).parts)
        and "|cover_placeholder" in p.read_text(encoding="utf-8")
    ]
    assert found == []


@pytest.mark.django_db
def test_a_long_list_looks_at_the_pool_once(client, site):
    """Design 15.1: the pool and its thumbnails come once per page."""
    from core.tests.test_chapter15_audit import assert_no_n_plus_one

    # More pictures than cards, so each card gets its own: with only a few,
    # the thumbnail lookups stop growing at the pool's size and hide a miss.
    for i in range(12):
        _picture(_pool(), f"p{i}")
    counter = iter(range(1000))

    def seed(count):
        for _ in range(count):
            _article(f"many-{next(counter)}")

    assert_no_n_plus_one(client, "/news/", seed)


# --- keeping the static pages right ------------------------------------------


@pytest.mark.django_db
def test_changes_to_the_pool_regenerate_the_site(site):
    from wagtail.models import Collection

    with mock.patch("core.prerender.request_all_soon") as regenerate:
        picture = _picture(_pool())
        assert regenerate.call_count == 1  # came in
        picture.title = "改名"
        picture.save()
        assert regenerate.call_count == 2  # changed
        picture.collection = Collection.get_first_root_node()
        picture.save()
        assert regenerate.call_count == 3  # left
        other = _picture(Collection.get_first_root_node(), "elsewhere")
        assert regenerate.call_count == 3  # not a cover
        other.delete()
        assert regenerate.call_count == 3
        _picture(_pool(), "going").delete()
        assert regenerate.call_count == 5  # came in, then went


@pytest.mark.django_db
def test_a_batch_of_uploads_regenerates_once(
    settings, tmp_path, django_capture_on_commit_callbacks
):
    from django.core.cache import cache

    from core import prerender

    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    cache.delete(prerender.ALL_PENDING_KEY)
    with mock.patch("core.tasks.prerender_all") as task:
        with django_capture_on_commit_callbacks(execute=True):
            assert prerender.request_all_soon() is True
            assert prerender.request_all_soon() is False
            assert prerender.request_all_soon() is False
    assert task.using.call_count == 1


# --- the motion ---------------------------------------------------------------------


def test_the_drift_moves_only_scale_and_translate():
    """So a card's hover zoom (transform) still adds on top of it."""
    css = (Path(settings.BASE_DIR) / "assets" / "css" / "input.css").read_text(
        encoding="utf-8"
    )
    for n in range(1, 5):
        start = css.index(f"  @keyframes ow-drift-{n} {{")
        body = css[start : css.index("\n  }\n", start)]
        assert "scale:" in body and "translate:" in body
        assert "transform" not in body
    assert (
        ".c-drift {\n    animation: ow-drift-1 26s ease-in-out infinite alternate;"
        in css
    )
    for n in range(2, 5):
        assert f".c-drift--{n} {{\n    animation-name: ow-drift-{n};" in css
