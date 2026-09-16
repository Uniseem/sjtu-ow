import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from content.models import ArticlePage
from core import prerender
from core.middleware import OW_FLASH_COOKIE, OW_LOGGED_IN_COOKIE
from core.models import PrerenderedPage


@pytest.fixture
def prerender_root(settings, tmp_path):
    settings.PRERENDER_ENABLED = True
    settings.PRERENDER_ROOT = tmp_path
    prerender.forget_targets()
    return tmp_path


def _user(email="prerender@example.com"):
    return User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname="预渲染用户",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )


def _article(title="预渲染文章", slug="prerender-article"):
    from content.models import ArticleCategory, ArticleIndexPage

    index = ArticleIndexPage.objects.live().first()
    category = ArticleCategory.objects.first()
    owner = User.objects.filter(is_superuser=True).first()
    if owner is None:
        owner = _user("author@example.com")
    page = ArticlePage(
        title=title,
        slug=slug,
        category=category,
        summary="预渲染测试用的摘要。",
        owner=owner,
    )
    index.add_child(instance=page)
    page.save_revision().publish()
    return page


@pytest.fixture
def site_tree(db):
    call_command("init_site", verbosity=0)


# --- generating ---------------------------------------------------------------


@pytest.mark.django_db
def test_generate_writes_html_and_compressed_twins(prerender_root, site_tree):
    record = prerender.generate("/")
    assert record.status == PrerenderedPage.Status.READY
    page = prerender_root / "index.html"
    assert page.exists()
    assert (prerender_root / "index.html.br").exists()
    assert (prerender_root / "index.html.gz").exists()
    assert b"<!DOCTYPE html>" in page.read_bytes()
    assert record.bytes == len(page.read_bytes())


@pytest.mark.django_db
def test_unchanged_content_is_not_rewritten(prerender_root, site_tree):
    prerender.generate("/")
    page = prerender_root / "index.html"
    before = page.stat().st_mtime_ns
    page.write_bytes(page.read_bytes())  # touch without changing content
    record = prerender.generate("/")
    assert record.status == PrerenderedPage.Status.READY
    assert page.stat().st_mtime_ns != before  # our own touch
    marker = page.read_bytes()
    prerender.generate("/")
    assert page.read_bytes() == marker


@pytest.mark.django_db
def test_generate_all_covers_every_public_page(prerender_root, site_tree):
    _article()
    stats = prerender.generate_all()
    assert stats["failed"] == 0
    paths = set(PrerenderedPage.objects.values_list("path", flat=True))
    assert {"/", "/news/", "/about/", "/news/prerender-article/"} <= paths
    assert (prerender_root / "news" / "prerender-article" / "index.html").exists()


@pytest.mark.django_db
def test_generated_pages_carry_nothing_personal(prerender_root, site_tree):
    _article()
    prerender.generate_all()
    for path in prerender_root.rglob("index.html"):
        text = path.read_text(encoding="utf-8")
        assert "csrfmiddlewaretoken" not in text
        assert "sessionid" not in text
        assert "@example.com" not in text
        assert "退出" not in text  # the logged-in account area


@pytest.mark.django_db
def test_a_page_that_is_no_longer_public_is_dropped(prerender_root, site_tree):
    record = prerender.generate("/does-not-exist/")
    assert record.status == PrerenderedPage.Status.FAILED
    assert "不再公开" in record.error
    assert not (prerender_root / "does-not-exist" / "index.html").exists()
    # No leftover row for the admin to worry about.
    assert not PrerenderedPage.objects.filter(path="/does-not-exist/").exists()


@pytest.mark.django_db
def test_a_real_failure_is_recorded(prerender_root, site_tree, monkeypatch):
    def boom(path):
        raise prerender.PrerenderError("渲染出错：boom")

    monkeypatch.setattr(prerender, "render_html", boom)
    record = prerender.generate("/about/")
    assert record.status == PrerenderedPage.Status.FAILED
    assert "boom" in record.error
    assert PrerenderedPage.objects.filter(path="/about/").exists()


@pytest.mark.django_db
def test_clear_all_removes_files_but_keeps_records(prerender_root, site_tree):
    prerender.generate_all()
    assert list(prerender_root.rglob("index.html"))
    prerender.clear_all()
    assert not list(prerender_root.rglob("index.html"))
    assert (
        PrerenderedPage.objects.exclude(status=PrerenderedPage.Status.PENDING).count()
        == 0
    )


# --- events -------------------------------------------------------------------


@pytest.mark.django_db
def test_publishing_queues_the_page_and_the_listings(prerender_root, site_tree):
    _article(slug="event-article")
    queued = set(PrerenderedPage.objects.values_list("path", flat=True))
    assert "/news/event-article/" in queued
    assert "/news/" in queued
    assert "/" in queued


@pytest.mark.django_db
def test_unpublishing_deletes_the_static_file(prerender_root, site_tree):
    page = _article(slug="unpublish-me")
    prerender.generate("/news/unpublish-me/")
    target = prerender_root / "news" / "unpublish-me" / "index.html"
    assert target.exists()

    page.unpublish()
    prerender.drop("/news/unpublish-me/")
    assert not target.exists()
    assert not PrerenderedPage.objects.filter(path="/news/unpublish-me/").exists()


@pytest.mark.django_db
def test_slug_change_drops_the_old_address(prerender_root, site_tree):
    page = _article(slug="old-slug")
    prerender.generate("/news/old-slug/")
    old = prerender_root / "news" / "old-slug" / "index.html"
    assert old.exists()

    page.slug = "new-slug"
    page.save()
    page.save_revision().publish()
    prerender.drop("/news/old-slug/")
    prerender.generate("/news/new-slug/")
    assert not old.exists()
    assert (prerender_root / "news" / "new-slug" / "index.html").exists()


@pytest.mark.django_db
def test_requests_within_thirty_seconds_are_merged(prerender_root, site_tree):
    PrerenderedPage.objects.all().delete()  # init_site 发布页面时已经排过一次
    assert prerender.request_page("/", kind="home") is True
    assert prerender.request_page("/", kind="home") is False
    record = PrerenderedPage.objects.get(path="/")
    record.requested_at = None
    record.save(update_fields=["requested_at"])
    assert prerender.request_page("/", kind="home") is True


@pytest.mark.django_db
def test_nothing_happens_when_prerendering_is_off(settings, tmp_path, site_tree):
    settings.PRERENDER_ENABLED = False
    settings.PRERENDER_ROOT = tmp_path
    assert prerender.request_page("/") is False
    prerender.request_all()
    prerender.request_removal("/")
    assert not list(tmp_path.rglob("*"))


# --- the state fragment -------------------------------------------------------


@pytest.mark.django_db
def test_state_fragment_returns_anonymous_slots(client, site_tree):
    response = client.get(reverse("state_fragment") + "?slots=account,messages")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="slot-account"' in html
    assert 'hx-swap-oob="true"' in html
    assert "登录" in html
    assert response["Cache-Control"] == "private, no-store"
    assert "Cookie" in response["Vary"]
    assert "csrftoken" in response.cookies


@pytest.mark.django_db
def test_state_fragment_returns_the_nickname_when_logged_in(client, site_tree):
    client.force_login(_user())
    response = client.get(reverse("state_fragment") + "?slots=account")
    html = response.content.decode()
    assert "个人中心" in html
    assert "退出" in html


@pytest.mark.django_db
def test_state_fragment_clears_a_stale_hint_cookie(client, site_tree):
    client.cookies[OW_LOGGED_IN_COOKIE] = "1"
    response = client.get(reverse("state_fragment") + "?slots=account")
    assert response.cookies[OW_LOGGED_IN_COOKIE]["max-age"] == 0


@pytest.mark.django_db
def test_state_fragment_ignores_unknown_slots(client, site_tree):
    response = client.get(reverse("state_fragment") + "?slots=account,nope")
    html = response.content.decode()
    assert 'id="slot-account"' in html
    assert "nope" not in html


@pytest.mark.django_db
def test_state_fragment_is_rate_limited(client, site_tree):
    from core.views import STATE_RATE_LIMIT

    url = reverse("state_fragment") + "?slots=account"
    for _ in range(STATE_RATE_LIMIT):
        assert client.get(url).status_code == 200
    limited = client.get(url)
    assert limited.status_code == 429
    assert limited["Retry-After"] == "60"


@pytest.mark.django_db
def test_flash_cookie_is_set_and_cleared(client, site_tree):
    user = _user("flash@example.com")
    client.force_login(user)
    response = client.post(
        reverse("me_profile"),
        {"nickname": "新昵称", "is_sjtu": "true"},
        follow=False,
    )
    assert response.status_code == 302  # 保存成功后跳转，提示留到下一个请求
    assert response.cookies.get(OW_FLASH_COOKIE)

    client.cookies[OW_FLASH_COOKIE] = "1"
    fragment = client.get(reverse("state_fragment") + "?slots=messages")
    assert fragment.cookies[OW_FLASH_COOKIE]["max-age"] == 0


# --- the fallback -------------------------------------------------------------


@pytest.mark.django_db
def test_a_missing_page_queues_itself(client, prerender_root, site_tree):
    PrerenderedPage.objects.all().delete()
    prerender.forget_targets()
    response = client.get("/about/")
    assert response.status_code == 200
    assert PrerenderedPage.objects.filter(path="/about/").exists()


@pytest.mark.django_db
def test_logged_in_requests_do_not_queue_pages(client, prerender_root, site_tree):
    PrerenderedPage.objects.all().delete()
    client.force_login(_user("skip@example.com"))
    client.get("/about/")
    assert not PrerenderedPage.objects.filter(path="/about/").exists()


# --- admin --------------------------------------------------------------------


@pytest.mark.django_db
def test_prerender_admin_is_superuser_only(client, prerender_root, site_tree):
    client.force_login(_user("notadmin@example.com"))
    assert client.get(reverse("core_prerender_index")).status_code == 302

    admin = User.objects.create_superuser(
        email="admin-prerender@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    prerender.generate("/")
    response = client.get(reverse("core_prerender_index"))
    assert response.status_code == 200
    assert "静态页面" in response.content.decode()


@pytest.mark.django_db
def test_admin_can_clear_everything(client, prerender_root, site_tree):
    admin = User.objects.create_superuser(
        email="admin-clear@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    prerender.generate_all()
    assert list(prerender_root.rglob("index.html"))
    client.post(reverse("core_prerender_clear"), follow=True)
    assert not list(prerender_root.rglob("index.html"))


@pytest.mark.django_db
def test_live_rendered_pages_tell_the_script_to_skip(client, site_tree):
    anonymous = client.get("/about/").content.decode()
    assert 'data-state-filled="0"' in anonymous

    client.force_login(_user("filled@example.com"))
    signed_in = client.get("/about/").content.decode()
    assert 'data-state-filled="1"' in signed_in


@pytest.mark.django_db
def test_generating_does_not_queue_itself_again(prerender_root, site_tree):
    PrerenderedPage.objects.all().delete()
    prerender.generate("/about/")
    record = PrerenderedPage.objects.get(path="/about/")
    # The generator's own request must not leave a pending request behind.
    assert record.requested_at is None
    assert record.status == PrerenderedPage.Status.READY


@pytest.mark.django_db
def test_unicode_paths_are_allowed(prerender_root, site_tree):
    assert prerender.looks_prerenderable("/news/中文标题/") is True
    assert prerender.looks_prerenderable("/news/../etc/") is False
    assert prerender.looks_prerenderable("/news//x/") is False
    assert prerender.looks_prerenderable("/news/\x00/") is False


# --- the three safety gates (design 13.13.4, 15.2) -----------------------------


@pytest.mark.django_db
def test_a_response_that_sets_a_cookie_is_never_frozen(prerender_root, monkeypatch):
    """Design 15.2: a prerendered page carries no personal data.

    A response that sets a cookie is personalised by definition, and freezing
    it would serve one visitor's cookie to everyone. Round 039 found this
    gate had no test: removing it turned nothing red, because the pages the
    other tests render happen not to set cookies.
    """
    from django.http import HttpResponse
    from django.test import Client

    def cookie_page(self, path, **kwargs):
        response = HttpResponse("<html><body>看起来很普通</body></html>")
        response["Content-Type"] = "text/html; charset=utf-8"
        response.set_cookie("sessionid", "somebody-elses-session")
        return response

    monkeypatch.setattr(Client, "get", cookie_page)

    with pytest.raises(prerender.PrerenderError) as caught:
        prerender.render_html("/")

    assert "Cookie" in str(caught.value)
    assert "sessionid" in str(caught.value)


@pytest.mark.django_db
def test_a_page_leaking_a_secret_marker_is_never_frozen(prerender_root, monkeypatch):
    """The second gate: the body must not contain anything personal."""
    from django.http import HttpResponse
    from django.test import Client

    marker = sorted(prerender.SECRET_MARKERS)[0]

    def leaky_page(self, path, **kwargs):
        response = HttpResponse(f"<html><body>{marker}</body></html>")
        response["Content-Type"] = "text/html; charset=utf-8"
        return response

    monkeypatch.setattr(Client, "get", leaky_page)

    with pytest.raises(prerender.PrerenderError):
        prerender.render_html("/")


@pytest.mark.django_db
def test_a_clean_public_page_is_frozen(prerender_root, monkeypatch):
    """The gates must not refuse an ordinary page — or they would be useless."""
    from django.http import HttpResponse
    from django.test import Client

    def plain_page(self, path, **kwargs):
        response = HttpResponse("<html><body>公开内容</body></html>")
        response["Content-Type"] = "text/html; charset=utf-8"
        return response

    monkeypatch.setattr(Client, "get", plain_page)

    html = prerender.render_html("/")

    assert "公开内容" in html.decode()
