"""Round 117: the admin's words and menus (handoff/rounds/115-admin-review/
findings.md #22, #26, #27 and part four).

Wagtail's missing Chinese filled in by the project, one language and time
zone, no upgrade notice, tick-and-cross columns, the static pages list,
the menu order and who sees reports and help, the separate 用户 menu, the
page tree that showed other people's drafts, and the stock workflow nobody
could approve.
"""

import gettext
import importlib
import io
import re

import pytest
from allauth.account.models import EmailAddress
from django.apps import apps as django_apps
from django.conf import settings as django_settings
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from wagtail.models import (
    Collection,
    GroupApprovalTask,
    Page,
    Workflow,
    WorkflowPage,
    WorkflowTask,
)

from accounts.models import Feature, FeatureUserRule, User
from accounts.services import GROUP_SUBMITTER
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from core.models import PrerenderedPage
from core.translations import build_mo, compiled, parse_po, po_files
from members.models import MemberGroup

PASSWORD = "Correct-Horse-Battery-1"


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _user(email, *groups, superuser=False):
    user = User.objects.create_user(
        email=email,
        password=PASSWORD,
        nickname=email.split("@")[0][:12],
        is_superuser=superuser,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    # 投稿者 is kept in step with a verified email (content.signals), so the
    # roles that are also submitters need one, or they silently lose it.
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    for name in groups:
        user.groups.add(Group.objects.get(name=name))
    assert set(user.groups.values_list("name", flat=True)) >= set(groups)
    return user


def _menu(client):
    """The back office's top bar: the section links, in the order shown."""
    html = client.get("/admin/").content.decode()
    nav = re.search(r'<nav class="b-nav"[^>]*>(.*?)</nav>', html, re.S)
    if nav is None:
        return []
    return re.findall(r'class="b-nav__link"[^>]*>([^<]+)</a>', nav.group(1))


# --- translations -------------------------------------------------------


def test_the_committed_mo_files_match_the_po_files():
    files = po_files(django_settings.LOCALE_PATHS)
    assert {path.name for path in files} == {"django.po", "djangojs.po"}
    for po_path in files:
        mo_path = po_path.with_suffix(".mo")
        assert mo_path.read_bytes() == compiled(po_path), (
            f"{mo_path} 和 .po 不一致：运行 manage.py compile_translations"
        )


def test_the_compiler_writes_what_python_gettext_reads():
    po = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=1; plural=0;\\n"\n'
        "\n"
        "# a comment\n"
        'msgid "Save"\n'
        'msgstr "保存"\n'
        "\n"
        'msgctxt "verb"\n'
        'msgid "Lock"\n'
        'msgstr "锁定"\n'
        "\n"
        'msgid "%(n)s page"\n'
        'msgid_plural "%(n)s pages"\n'
        'msgstr[0] "%(n)s 个页面"\n'
        "\n"
        'msgid ""\n'
        '"Two "\n'
        '"\\"lines\\""\n'
        'msgstr "两行"\n'
        "\n"
        'msgid "Untranslated"\n'
        'msgstr ""\n'
    )
    catalog = parse_po(po)
    assert "Untranslated" not in catalog
    reader = gettext.GNUTranslations(io.BytesIO(build_mo(catalog)))
    assert reader.gettext("Save") == "保存"
    assert reader.pgettext("verb", "Lock") == "锁定"
    assert reader.gettext("Lock") == "Lock"
    assert reader.ngettext("%(n)s page", "%(n)s pages", 5) == "%(n)s 个页面"
    assert reader.gettext('Two "lines"') == "两行"
    assert build_mo(catalog) == build_mo(dict(reversed(catalog.items())))


@pytest.mark.parametrize(
    "po, reason",
    [
        ('"orphan line"\nmsgstr "x"\n', "续行前没有关键字"),
        ('msgid "Save"\nmsgstr "保存"\nmsgstr "存"\n', "出现两次"),
        ('msgctxt "verb"\nmsgstr "锁定"\n', "没有 msgid"),
    ],
)
def test_a_broken_po_file_is_refused_not_half_read(po, reason):
    """Round 179: a mistake in a hand-edited .po stops compile_translations."""
    with pytest.raises(ValueError, match=reason):
        parse_po(po)


@pytest.mark.django_db
def test_the_admin_has_no_wagtail_english_left(site, client):
    """Wagtail's own admin, kept under /wagtail/ for superusers (v7.0)."""
    client.force_login(_user("root117@example.com", superuser=True))
    home = client.get("/wagtail/").content.decode()
    # v6.67 (round 189): the dashboard's page search, site summary and the
    # help menu (快捷键) are gone; nothing English came back with the change.
    assert "Search all pages" not in home
    assert "Shortcuts" not in home
    assert "账号" in home
    assert "帐号" not in home
    root = Page.objects.get(depth=1)
    explorer = client.get(f"/wagtail/pages/{root.pk}/").content.decode()
    assert "Exploring" not in explorer
    assert "正在浏览" in explorer
    account = client.get("/wagtail/account/").content.decode()
    assert "Theme preferences" not in account
    assert "主题偏好" in account
    catalog = client.get("/wagtail/jsi18n/").content.decode()
    assert "\\u63d2\\u5165\\u5757" in catalog or "插入块" in catalog


@pytest.mark.django_db
def test_admin_tabs_name_the_site_not_wagtail(site, client):
    client.force_login(_user("tab117@example.com", superuser=True))
    html = client.get("/admin/").content.decode()
    assert "<title>首页 · 管理后台</title>" in html
    assert "img/favicon.svg" in html
    fallback = client.get("/wagtail/").content.decode()
    assert "- SJTU OW 底层后台</title>" in fallback
    assert "- Wagtail</title>" not in fallback
    assert "img/favicon.svg" in fallback


@pytest.mark.django_db
def test_one_language_one_time_zone_and_no_upgrade_notice(site, client):
    client.force_login(_user("lang117@example.com", superuser=True))
    account = client.get("/wagtail/account/").content.decode()
    assert "preferred_language" not in account
    assert "current_time_zone" not in account
    home = client.get("/wagtail/").content.decode()
    assert "w-upgrade" not in home


@pytest.mark.django_db
def test_the_locale_shows_in_chinese(site, client):
    client.force_login(_user("locale117@example.com", superuser=True))
    report = client.get("/wagtail/reports/page-types-usage/").content.decode()
    assert "Page types usage" not in report
    assert "页面类型使用情况" in report
    assert "Simplified Chinese" not in report
    assert "简体中文" in report


# --- list columns ------------------------------------------------------


@pytest.mark.django_db
def test_yes_no_columns_say_it_in_words(site, client):
    """Round 117's point, in the back office (v7.0): no bare True or False."""
    client.force_login(_user("bool117@example.com", superuser=True))
    bare = re.compile(r"<td[^>]*>\s*(True|False)\s*</td>")
    categories = client.get(reverse("backoffice:categories")).content.decode()
    assert not bare.search(categories)
    assert '<td data-label="开放投稿">是</td>' in categories
    MemberGroup.objects.create(name="管理组117", is_visible=False)
    groups = client.get(reverse("backoffice:member_groups")).content.decode()
    assert "管理组117" in groups
    assert not bare.search(groups)
    assert '<td data-label="显示">不显示</td>' in groups
    member = _user("ruled117@example.com")
    FeatureUserRule.objects.create(
        user=member, feature=Feature.TEAM_CREATE, allowed=False
    )
    rules = client.get(reverse("backoffice:user_edit", args=[member.pk]))
    assert not bare.search(rules.content.decode())
    assert "单独禁止" in rules.content.decode()


@pytest.mark.django_db
def test_the_static_pages_list_speaks_chinese_filters_and_pages(site, client):
    client.force_login(_user("static117@example.com", superuser=True))
    PrerenderedPage.objects.create(path="/news/a/", kind="article", status="ready")
    PrerenderedPage.objects.create(
        path="/teams/", kind="team_index", status="failed", error="坏了"
    )
    for number in range(60):
        PrerenderedPage.objects.create(
            path=f"/x/{number:02d}/", kind="team", status="pending"
        )
    url = reverse("core_prerender_index")
    first = client.get(url).content.decode()
    assert '<td data-label="类型">文章</td>' in first
    assert ">article</td>" not in first
    assert '<span class="c-pager__pos"><strong>1</strong> / 2</span>' in first
    assert '生成失败<span class="c-tabs__count">1</span>' in first
    failed = client.get(url + "?status=failed").content.decode()
    assert "/teams/" in failed
    assert "/x/00/" not in failed
    assert "战队列表" in failed
    second = client.get(url + "?page=2").content.decode()
    assert "/x/59/" in second
    assert "/news/a/" not in second


# --- menus -------------------------------------------------------------


SECTION_TABS = re.compile(r'<nav class="b-tabs"[^>]*>(.*?)</nav>', re.S)
PLACE = re.compile(r'<body class="b-body"[^>]*data-section="(\w*)" data-tab="(\w*)"')


def _tops(client):
    return _menu(client)


def _strip(client, url):
    """(section, [tab labels], current tab label) of a back-office page: the
    section the view says it is in, and the strip it draws."""
    html = client.get(url, follow=True).content.decode()
    place = PLACE.search(html)
    if place is None:
        return None, [], None
    found = SECTION_TABS.search(html)
    if found is None:
        return place.group(1), [], None
    labels = [
        re.sub(r"<span.*?</span>", "", label).strip()
        for label in re.findall(r"<a [^>]*>(.*?)</a>", found.group(1))
    ]
    current = re.search(r'<a [^>]*aria-current="page"[^>]*>(.*?)</a>', found.group(1))
    current = (
        re.sub(r"<span.*?</span>", "", current.group(1)).strip() if current else None
    )
    return place.group(1), labels, current


@pytest.mark.django_db
def test_the_top_bar_is_eight_sections(site, client):
    """docs/admin.md 3–4 (v7.0): the eight sections of v6.71, as the site's
    own top bar instead of Wagtail's sidebar."""
    client.force_login(_user("menu193@example.com", superuser=True))
    assert _tops(client) == [
        "首页",
        "内容",
        "活动",
        "成员",
        "审核",
        "数据",
        "设置",
        "手册",
    ]


@pytest.mark.django_db
def test_each_section_has_its_tabs_in_order(site, client):
    client.force_login(_user("tabs193@example.com", superuser=True))
    assert _strip(client, reverse("backoffice:images")) == (
        "content",
        ["文章", "分类", "网站页面", "图片"],
        "图片",
    )
    assert _strip(client, "/admin/tournaments/") == ("events", ["赛事", "内战"], "赛事")
    assert _strip(client, "/admin/teams/") == (
        "members",
        ["用户与权限", "战队", "成员分组"],
        "战队",
    )
    assert _strip(client, "/admin/comments/") == (
        "review",
        ["报名", "内容", "头像", "评论"],
        "评论",
    )
    assert _strip(client, "/admin/settings/fonts/") == (
        "settings",
        ["全站设置", "字体库", "排版设置", "静态页面", "操作记录"],
        "字体库",
    )
    for url, key in (
        ("/admin/", "home"),
        ("/admin/activity/", "data"),
        ("/admin/manual/", "manual"),
    ):
        assert _strip(client, url) == (key, [], None), url
    users = client.get("/admin/users/").content.decode()
    subtabs = re.search(r'<nav class="b-subtabs"[^>]*>(.*?)</nav>', users, re.S).group(
        1
    )
    assert re.findall(r">([^<>]+)</a>", subtabs) == ["用户", "角色"]
    assert 'aria-current="page">用户</a>' in subtabs


@pytest.mark.django_db
def test_each_role_sees_only_its_sections_and_tabs(site, client):
    """Who sees what is still each page's own permission (14.1)."""
    from scrims.tests.test_scrims import make_scrim

    scrim = make_scrim()
    cases = (
        (
            ("内容编辑", GROUP_SUBMITTER),
            ["首页", "内容", "成员", "审核", "数据", "手册"],
            {
                reverse("backoffice:images"): (
                    "content",
                    ["文章", "分类", "网站页面", "图片"],
                ),
                "/admin/moderation/": ("review", ["内容", "头像", "评论"]),
                reverse("backoffice:member_groups"): ("members", []),
            },
        ),
        (
            ("赛事管理员", GROUP_SUBMITTER),
            ["首页", "内容", "活动", "审核", "数据", "手册"],
            {
                reverse("backoffice:images"): ("content", ["文章", "图片"]),
                "/admin/tournaments/": ("events", []),
                "/admin/registrations/": ("review", []),
            },
        ),
        (
            ("内战管理员", GROUP_SUBMITTER),
            ["首页", "内容", "活动", "数据", "手册"],
            {"/admin/scrims/": ("events", [])},
        ),
        (("认证作者", GROUP_SUBMITTER), ["首页", "内容", "手册"], {}),
        (
            (GROUP_SUBMITTER,),
            ["首页", "内容"],
            {reverse("backoffice:images"): ("content", ["文章", "图片"])},
        ),
    )
    assert scrim.pk
    for number, (groups, wanted, pages) in enumerate(cases):
        client.force_login(_user(f"role{number}-193@example.com", *groups))
        assert _tops(client) == wanted, groups
        for url, (key, tabs) in pages.items():
            assert _strip(client, url)[:2] == (key, tabs), (groups, url)
        client.logout()


@pytest.mark.django_db
def test_every_page_says_where_it_is(site, client):
    """The view declares its section and tab (docs/admin.md 4); the top bar
    lights that one section, whatever the address looks like."""
    from scrims.tests.test_scrims import make_scrim

    client.force_login(_user("light193@example.com", superuser=True))
    news = ArticleIndexPage.objects.get(slug="news")
    article = ArticlePage(
        title="高亮193",
        slug="light-193",
        category=ArticleCategory.objects.first(),
        author=User.objects.get(email="light193@example.com"),
        body="正文",
    )
    news.add_child(instance=article)
    about = Page.objects.get(slug="about")
    scrim = make_scrim()
    for url, (key, tab) in {
        reverse("backoffice:article_edit", args=[article.pk]): ("content", "articles"),
        reverse("backoffice:article_new"): ("content", "articles"),
        reverse("backoffice:page_edit", args=[about.pk]): ("content", "pages"),
        reverse("backoffice:pages"): ("content", "pages"),
        f"/admin/announce/scrim/{scrim.pk}/": ("events", "scrims"),
        reverse("backoffice:site_settings"): ("settings", "site"),
        reverse("backoffice:log"): ("settings", "log"),
    }.items():
        html = client.get(url).content.decode()
        assert f'data-section="{key}" data-tab="{tab}"' in html, url
        lit = re.findall(r'class="b-nav__link"[^>]*aria-current="page">([^<]+)<', html)
        assert len(lit) == 1, url


def test_every_back_office_address_goes_through_the_door():
    """Every view under /admin/ is wrapped by ``placed``: signed-out visitors
    go to sign in, people without access_admin get a 403, and the page knows
    its section. A view added without it would be open to anyone."""
    from django.urls import get_resolver

    from backoffice.nav import BY_KEY

    admin = next(p for p in get_resolver().url_patterns if str(p.pattern) == "admin/")

    def walk(patterns, prefix=""):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern.url_patterns, prefix + str(pattern.pattern))
            else:
                yield prefix + str(pattern.pattern), pattern.callback

    found = list(walk(admin.url_patterns))
    assert len(found) > 60
    for route, view in found:
        if route == "announce/<str:kind>/<id:pk>/":
            continue  # places itself by kind (backoffice.views.events.announce)
        place = getattr(view, "backoffice_place", None)
        assert place is not None, route
        assert place.section in BY_KEY, route
        assert place.tab in {tab.key for tab in BY_KEY[place.section].tabs}, route


@pytest.mark.django_db
def test_review_tabs_count_what_waits(site, client):
    """Only registrations wait for anyone (v6.72–v6.73)."""
    from tournaments.tests.test_review_admin import registration as make_registration

    client.force_login(_user("count193@example.com", superuser=True))
    html = client.get("/admin/comments/").content.decode()
    strip = SECTION_TABS.search(html).group(1)
    assert "c-tabs__count" not in strip
    make_registration.__wrapped__(None)
    strip = SECTION_TABS.search(client.get("/admin/comments/").content.decode()).group(
        1
    )
    assert re.search(r'>报名<span class="c-tabs__count">1</span></a>', strip)
    assert strip.count("c-tabs__count") == 1
    other = SECTION_TABS.search(
        client.get("/admin/tournaments/").content.decode()
    ).group(1)
    assert "c-tabs__count" not in other  # counted on 审核 only


@pytest.mark.django_db
def test_wagtails_unused_entries_stay_out_of_every_menu(site, client):
    """文档, 报告, 帮助 and the settings the club never touches (14.1)."""
    for number, (groups, superuser) in enumerate(((("内容编辑",), False), ((), True))):
        client.force_login(
            _user(f"hidden{number}-193@example.com", *groups, superuser=superuser)
        )
        tops = set(_tops(client))
        assert not tops & {"文档", "报告", "帮助", "社区", "页面", "用户"}, tops
        html = client.get("/admin/settings/fonts/").content.decode()
        found = SECTION_TABS.search(html)
        labels = found.group(1) if found else ""
        for gone in ("站点", "重定向", "工作流任务", ">工作流<"):
            assert gone not in labels
        client.logout()


# --- page tree ---------------------------------------------------------


@pytest.mark.django_db
def test_staff_who_are_also_submitters_do_not_see_others_drafts(site, client):
    news = ArticleIndexPage.objects.get(slug="news")
    author = _user("drafter117@example.com", GROUP_SUBMITTER)
    draft = ArticlePage(
        title="别人的草稿117",
        slug="someone-draft-117",
        category=ArticleCategory.objects.filter(allow_submission=True).first(),
        author=author,
        owner=author,
        summary="摘要",
        body="正文",
    )
    news.add_child(instance=draft)
    draft.save_revision(user=author)
    draft.unpublish()
    for number, (groups, sees) in enumerate(
        (
            (("赛事管理员", GROUP_SUBMITTER), False),
            (("内战管理员", GROUP_SUBMITTER), False),
            (("认证作者", GROUP_SUBMITTER), False),
            (("内容编辑",), True),
        )
    ):
        user = _user(f"tree{number}-117@example.com", *groups)
        client.force_login(user)
        response = client.get(reverse("backoffice:articles"))
        assert response.status_code == 200, groups
        listing = response.content.decode()
        assert ("别人的草稿117" in listing) is sees, groups
        client.logout()


@pytest.mark.django_db
def test_both_page_tree_filters_hide_others_drafts(site, rf):
    """The listing hides a draft through two layers (the explorer hook and
    Wagtail's explorable pages); each must hold on its own."""
    from wagtail.permission_policies.pages import PagePermissionPolicy

    from content.wagtail_hooks import filter_submitter_explorer

    news = ArticleIndexPage.objects.get(slug="news")
    author = _user("layers-author117@example.com", GROUP_SUBMITTER)
    draft = ArticlePage(
        title="分层草稿117",
        slug="layered-draft-117",
        category=ArticleCategory.objects.filter(allow_submission=True).first(),
        author=author,
        owner=author,
        summary="摘要",
        body="正文",
    )
    news.add_child(instance=draft)
    draft.save_revision(user=author)
    draft.unpublish()
    manager = _user("layers-manager117@example.com", "赛事管理员", GROUP_SUBMITTER)
    request = rf.get("/admin/pages/")
    request.user = manager
    shown = filter_submitter_explorer(news, news.get_children(), request)
    assert not shown.filter(pk=draft.pk).exists()
    explorable = PagePermissionPolicy().explorable_instances(manager)
    assert not explorable.filter(pk=draft.pk).exists()
    assert explorable.filter(pk=news.pk).exists()


# --- the stock workflow ------------------------------------------------


def _stock_workflow(*approver_groups, on_root=True):
    """What Wagtail's own migration leaves: 「Moderators approval」 on the
    root page, its task asking the stock Moderators group."""
    workflow = Workflow.objects.create(name="Moderators approval", active=True)
    task = GroupApprovalTask.objects.create(name="Moderators approval", active=True)
    for name in approver_groups:
        task.groups.add(Group.objects.get_or_create(name=name)[0])
    WorkflowTask.objects.create(workflow=workflow, task=task, sort_order=0)
    if on_root:
        WorkflowPage.objects.create(workflow=workflow, page=Page.objects.get(depth=1))
    return workflow, task


@pytest.mark.django_db
def test_init_site_retires_the_workflow_nobody_can_approve(site):
    # Tests skip migrations, so the stock workflow is built here; init_site
    # deletes its Moderators group and should then switch it off.
    stock, _task = _stock_workflow("Moderators")
    call_command("init_site", verbosity=0)
    stock.refresh_from_db()
    assert not stock.active
    assert not WorkflowPage.objects.filter(workflow=stock).exists()
    assert Page.objects.get(depth=1).title == "根目录"
    assert Collection.objects.get(depth=1).name == "根目录"


@pytest.mark.django_db
def test_a_stock_workflow_with_approvers_is_left_alone(site):
    from content.services import retire_wagtail_stock_workflow

    workflow, task = _stock_workflow("内容编辑")
    retire_wagtail_stock_workflow()
    workflow.refresh_from_db()
    assert workflow.active
    task.groups.clear()
    assert retire_wagtail_stock_workflow()
    workflow.refresh_from_db()
    task.refresh_from_db()
    assert not workflow.active
    assert not task.active
    assert not WorkflowPage.objects.filter(workflow=workflow).exists()


@pytest.mark.django_db
def test_the_migration_retires_it_on_existing_sites(site):
    migration = importlib.import_module("content.migrations.0006_retire_stock_workflow")
    workflow, task = _stock_workflow()
    kept, _kept_task = _stock_workflow("内容编辑", on_root=False)
    Page.objects.filter(depth=1).update(title="Root", draft_title="Root")
    migration.forwards(django_apps, None)
    kept.refresh_from_db()
    assert kept.active
    workflow.refresh_from_db()
    assert not workflow.active
    assert not WorkflowPage.objects.filter(workflow=workflow).exists()
    assert not GroupApprovalTask.objects.get(pk=task.pk).active
    assert Page.objects.get(depth=1).title == "根目录"
