"""217 复核 11 后台：复现脚本（只读业务代码，不改任何东西）。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s \
        handoff/rounds/217-second-review/findings/11-repro_test.py

每条测试断言的是「现在的（有问题的）行为」，绿 = 已复现。
"""

import json
import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Revision

from accounts.services import GROUP_SUBMITTER
from accounts.tests.test_onboarding import _user
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage

AUTOSAVE = {"HTTP_X_AUTOSAVE": "1", "HTTP_ACCEPT": "application/json"}


@pytest.fixture
def site(db):
    call_command("init_site", verbosity=0)


def _live_article(author, category, title):
    news = ArticleIndexPage.objects.get(slug="news")
    page = ArticlePage(
        title=title,
        slug=f"r217-{ArticlePage.objects.count()}",
        category=category,
        author=author,
        owner=author,
        summary="摘要",
        body="正文",
        live=False,
    )
    news.add_child(instance=page)
    page.save_revision(user=author).publish()
    return ArticlePage.objects.get(pk=page.pk)


def _save(client, url, data):
    response = client.post(url, data, **AUTOSAVE)
    return json.loads(response.content)


def _opened_revision(client, url) -> int:
    html = client.get(url).content.decode()
    return int(re.search(r'name="latest_revision" value="(\d+)"', html).group(1))


# --- 11-1：删分类的计数，一篇文章只算一个分类 ----------------------------------------


@pytest.mark.django_db
def test_11_1a_live_category_counts_zero_and_delete_500s(site):
    from content.services import category_in_use

    editor = _user("r217a@example.com", "内容编辑")
    old = ArticleCategory.objects.create(name="线上217", slug="live-217")
    new = ArticleCategory.objects.create(name="草稿217", slug="draft-217")
    page = _live_article(editor, old, "线上文章217")
    client = Client(raise_request_exception=False)
    client.force_login(editor)
    edit = reverse("backoffice:article_edit", args=[page.pk])
    answer = _save(
        client,
        edit,
        {"title": page.title, "category": new.pk, "summary": "摘要", "body": "正文"},
    )
    assert answer["ok"]
    page.refresh_from_db()
    print("页面行的分类:", page.category_id, "旧分类:", old.pk, "page.live:", page.live)
    print("category_in_use(旧)=", category_in_use(old), "(新)=", category_in_use(new))
    assert page.category_id == old.pk and page.live
    assert category_in_use(old) == 0  # 线上那篇明明在用

    listing = client.get(reverse("backoffice:categories")).content.decode()
    delete_url = reverse("backoffice:category_delete", args=[old.pk])
    print("列表里给了删除按钮:", delete_url in listing)
    assert delete_url in listing
    response = client.post(delete_url)
    print("删除旧分类:", response.status_code)
    assert response.status_code == 500  # ProtectedError
    assert ArticleCategory.objects.filter(pk=old.pk).exists()


@pytest.mark.django_db
def test_11_1b_scheduled_revision_category_silently_deletable(site):
    """已发布文章（行=Y），排了一次定时更新（修订=Z），后来另一个人的草稿选了 X：
    Z 和 X 只有一个被算上；没算上的那个能删掉，删了以后对应修订打不开。"""
    from content.services import category_in_use

    editor = _user("r217b@example.com", "内容编辑")
    other = _user("r217c@example.com", "内容编辑")
    live = ArticleCategory.objects.create(name="Y217", slug="y-217")
    sched = ArticleCategory.objects.create(name="Z217", slug="z-217")
    later = ArticleCategory.objects.create(name="X217", slug="x-217")
    page = _live_article(editor, live, "定时217")

    draft = page.get_latest_revision_as_object()
    draft.category = sched
    scheduled = draft.save_revision(user=editor)
    Revision.objects.filter(pk=scheduled.pk).update(
        approved_go_live_at=timezone.now() + timedelta(days=1)
    )
    page = ArticlePage.objects.get(pk=page.pk)
    draft = page.get_latest_revision_as_object()
    draft.category = later
    draft.save_revision(user=other)

    counts = {
        "Y(行)": category_in_use(live),
        "Z(定时修订)": category_in_use(sched),
        "X(最新草稿)": category_in_use(later),
    }
    print("计数:", counts)
    assert counts["Y(行)"] == 0
    assert counts["Z(定时修订)"] + counts["X(最新草稿)"] == 1  # 少算了一个

    lost = sched if counts["Z(定时修订)"] == 0 else later
    client = Client(raise_request_exception=False)
    client.force_login(editor)
    response = client.post(reverse("backoffice:category_delete", args=[lost.pk]))
    print("删除没算上的分类", lost.name, ":", response.status_code)
    assert not ArticleCategory.objects.filter(pk=lost.pk).exists()
    revision = (
        Revision.objects.get(pk=scheduled.pk)
        if lost == sched
        else ArticlePage.objects.get(pk=page.pk).latest_revision
    )
    with pytest.raises(Exception) as caught:
        revision.as_object()
    print("那条修订打不开:", type(caught.value).__name__, caught.value)


# --- 11-2：212 的 D3 防护被「覆盖同一条修订」绕过 -----------------------------------


@pytest.mark.django_db
def test_11_2_stale_guard_misses_overwritten_revision(site):
    writer = _user("r217d@example.com", GROUP_SUBMITTER)
    category = ArticleCategory.objects.get(slug="guide")
    page = _live_article(writer, category, "一起改217")
    edit = reverse("backoffice:article_edit", args=[page.pk])
    first = Client()
    first.force_login(_user("r217e@example.com", "内容编辑"))
    second = Client()
    second.force_login(_user("r217f@example.com", "内容编辑"))

    def fields(**changes):
        data = {
            "title": "一起改217",
            "category": category.pk,
            "summary": "摘要",
            "body": "正文",
            "comments_enabled": "on",
        }
        data.update(changes)
        return data

    base = _opened_revision(first, edit)
    answer = _save(first, edit, fields(body="甲第一段", latest_revision=base))
    mine = answer["values"]["latest_revision"]
    print("甲第一次存：", answer["ok"], "修订", base, "->", mine)

    seen = _opened_revision(second, edit)  # 乙这时打开，看到的正文是「甲第一段」
    answer = _save(first, edit, fields(body="甲第一段\n\n甲第二段", latest_revision=mine))
    print(
        "甲接着写：",
        answer["ok"],
        "修订号还是",
        answer["values"]["latest_revision"],
        "乙打开时的号",
        seen,
    )
    assert answer["values"]["latest_revision"] == seen  # 覆盖的是同一条

    answer = _save(
        second, edit, fields(title="乙改的标题", body="甲第一段", latest_revision=seen)
    )
    print("乙改标题：ok=", answer["ok"], "saved=", answer["saved"])
    draft = ArticlePage.objects.get(pk=page.pk).get_latest_revision_as_object()
    print("现在的草稿：标题", draft.title, "正文", repr(draft.body))
    assert answer["ok"]  # 没被当成「别人改过」
    assert draft.body == "甲第一段"  # 甲的第二段没了


# --- 11-3：给「投稿者」组关掉投稿 -> 无限递归 ----------------------------------------


@pytest.mark.django_db
def test_11_3_restricting_submit_on_the_submitter_group_recurses(site):
    root = _user("r217root@example.com")
    root.is_superuser = True
    root.is_staff = True
    root.save()
    _user("r217member@example.com")  # 验证过邮箱，自动在投稿者组
    group = Group.objects.get(name=GROUP_SUBMITTER)
    client = Client()
    client.force_login(root)
    url = reverse("backoffice:role_restriction_add", args=[group.pk])
    roles = client.get(reverse("backoffice:roles")).content.decode()
    print("角色页给投稿者组提供了「对这组关掉」:", url in roles)
    with pytest.raises(RecursionError):
        client.post(url, {"feature": "article_submit", "note": "试"})
    print("POST 抛出 RecursionError")


# --- 11-4：选图控件拿非数字重画 -> 500 ------------------------------------------------


@pytest.mark.django_db
def test_11_4_image_picker_rerender_with_garbage_500s(site):
    member = _user("r217g@example.com")  # 投稿者
    client = Client(raise_request_exception=False)
    client.force_login(member)
    response = client.post(
        reverse("backoffice:article_new"), {"title": "坏封面217", "cover": "abc"}
    )
    print("投稿者写文章 cover=abc（不带 X-Autosave）:", response.status_code)
    assert response.status_code == 500

    root = _user("r217root2@example.com")
    root.is_superuser = True
    root.save()
    client.force_login(root)
    for name, url, data in (
        ("新建赛事", reverse("tournaments:add"), {"title": "t", "cover": "abc"}),
        ("全站设置", reverse("backoffice:site_settings"), {"hero_image": "abc"}),
    ):
        response = client.post(url, data)
        print(name, "图片字段=abc:", response.status_code)


# --- 11-5：投稿者在「关联赛事」下拉里看到草稿赛事 ------------------------------------


@pytest.mark.django_db
def test_11_5_plain_member_sees_draft_tournament_titles(site):
    from tournaments.models import Tournament, TournamentStatus

    Tournament.objects.create(title="还没公布的秘密杯217", status=TournamentStatus.DRAFT)
    member = _user("r217h@example.com")
    client = Client()
    client.force_login(member)
    html = client.get(reverse("backoffice:article_new")).content.decode()
    print("投稿者写文章页里有草稿赛事名:", "还没公布的秘密杯217" in html)
    assert "还没公布的秘密杯217" in html
