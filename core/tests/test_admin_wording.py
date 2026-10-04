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
import json
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
    """The admin sidebar as 「菜单 / 子菜单」 paths, in the order shown."""
    html = client.get("/admin/").content.decode()
    props = re.search(
        r'<script id="wagtail-sidebar-props" type="application/json">(.*?)</script>',
        html,
        re.S,
    )
    found = []

    def walk(node, trail):
        if isinstance(node, dict):
            kind = node.get("_type", "")
            args = node.get("_args") or []
            if kind in (
                "wagtail.sidebar.LinkMenuItem",
                "wagtail.sidebar.PageExplorerMenuItem",
            ):
                found.append(" / ".join(trail + [args[0].get("label", "")]))
                return
            if kind == "wagtail.sidebar.SubMenuItem":
                walk(args[1], trail + [args[0].get("label", "")])
                return
            for value in node.values():
                walk(value, trail)
        elif isinstance(node, list):
            for value in node:
                walk(value, trail)

    walk(json.loads(props.group(1)), [])
    return found


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


@pytest.mark.django_db
def test_the_admin_has_no_wagtail_english_left(site, client):
    client.force_login(_user("root117@example.com", superuser=True))
    home = client.get("/admin/").content.decode()
    assert "Search all pages" not in home
    assert "搜索全部页面" in home
    assert re.search(r"\d+ 个页面", home)
    assert "Shortcuts" not in home
    assert "快捷键" in home
    assert "账号" in home
    assert "帐号" not in home
    root = Page.objects.get(depth=1)
    explorer = client.get(f"/admin/pages/{root.pk}/").content.decode()
    assert "Exploring" not in explorer
    assert "正在浏览" in explorer
    listing = client.get("/admin/snippets/content/articlecategory/").content.decode()
    assert "in ascending order" not in listing
    assert "升序排列" in listing
    account = client.get("/admin/account/").content.decode()
    assert "Theme preferences" not in account
    assert "主题偏好" in account
    catalog = client.get("/admin/jsi18n/").content.decode()
    assert "\\u63d2\\u5165\\u5757" in catalog or "插入块" in catalog


@pytest.mark.django_db
def test_admin_tabs_name_the_site_not_wagtail(site, client):
    client.force_login(_user("tab117@example.com", superuser=True))
    html = client.get("/admin/").content.decode()
    assert "- SJTU OW 后台</title>" in html
    assert "- Wagtail</title>" not in html
    assert "img/favicon.svg" in html


@pytest.mark.django_db
def test_one_language_one_time_zone_and_no_upgrade_notice(site, client):
    client.force_login(_user("lang117@example.com", superuser=True))
    account = client.get("/admin/account/").content.decode()
    assert "preferred_language" not in account
    assert "current_time_zone" not in account
    home = client.get("/admin/").content.decode()
    assert "w-upgrade" not in home


@pytest.mark.django_db
def test_the_locale_shows_in_chinese(site, client):
    client.force_login(_user("locale117@example.com", superuser=True))
    report = client.get("/admin/reports/page-types-usage/").content.decode()
    assert "Page types usage" not in report
    assert "页面类型使用情况" in report
    assert "Simplified Chinese" not in report
    assert "简体中文" in report


# --- list columns ------------------------------------------------------


@pytest.mark.django_db
def test_yes_no_columns_are_ticks_not_true_and_false(site, client):
    client.force_login(_user("bool117@example.com", superuser=True))
    bare = re.compile(r"<td[^>]*>\s*(True|False)\s*</td>")
    categories = client.get("/admin/snippets/content/articlecategory/").content.decode()
    assert not bare.search(categories)
    assert "w-text-positive-100" in categories
    MemberGroup.objects.create(name="管理组117", is_visible=False)
    groups = client.get("/admin/snippets/members/membergroup/").content.decode()
    assert "管理组117" in groups
    assert not bare.search(groups)
    assert "w-text-text-error" in groups
    member = _user("ruled117@example.com")
    FeatureUserRule.objects.create(
        user=member, feature=Feature.TEAM_CREATE, allowed=False
    )
    rules = client.get(reverse("feature_user_rules:index")).content.decode()
    assert not bare.search(rules)
    assert "单独禁止" in rules


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
    assert "<td>文章</td>" in first
    assert "<td>article</td>" not in first
    assert "第 1 / 2 页" in first
    assert "生成失败（1）" in first
    failed = client.get(url + "?status=failed").content.decode()
    assert "/teams/" in failed
    assert "/x/00/" not in failed
    assert "战队列表" in failed
    second = client.get(url + "?page=2").content.decode()
    assert "/x/59/" in second
    assert "/news/a/" not in second


# --- menus -------------------------------------------------------------


@pytest.mark.django_db
def test_the_menu_follows_the_design_order(site, client):
    client.force_login(_user("menu117@example.com", superuser=True))
    menu = _menu(client)
    tops = list(dict.fromkeys(item.split(" / ")[0] for item in menu))
    wanted = [
        "页面",
        "图片",
        "社区",
        "成员分组",
        "文章分类",
        "用户",
        "报告",
        "设置",
        "帮助",
    ]
    assert [top for top in tops if top in wanted] == wanted
    community = [item.split(" / ")[1] for item in menu if item.startswith("社区 / ")]
    assert community == [
        "赛事",
        "报名审核",
        "内战活动",
        "战队",
        "内容审核",
        "头像审核",
        "评论",
        "活动数据",
    ]
    assert "用户 / 用户" in menu
    assert "用户 / 用户组" in menu
    assert any(item.startswith("用户 / 功能权限 / ") for item in menu)
    assert not any(
        item.startswith(("设置 / 用户", "设置 / 组", "设置 / 功能权限"))
        for item in menu
    )


@pytest.mark.django_db
def test_reports_and_help_are_for_superusers_and_content_editors(site, client):
    for number, (groups, shown) in enumerate(
        (
            (("内容编辑",), True),
            (("赛事管理员", GROUP_SUBMITTER), False),
            (("内战管理员", GROUP_SUBMITTER), False),
            (("认证作者", GROUP_SUBMITTER), False),
        )
    ):
        user = _user(f"role{number}-117@example.com", *groups)
        client.force_login(user)
        tops = {item.split(" / ")[0] for item in _menu(client)}
        assert ("报告" in tops) is shown, groups
        assert ("帮助" in tops) is shown, groups
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
        body=[("paragraph", "<p>正文</p>")],
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
        response = client.get(f"/admin/pages/{news.pk}/")
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
        body=[("paragraph", "<p>正文</p>")],
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
