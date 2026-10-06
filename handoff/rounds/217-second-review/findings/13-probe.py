"""217 复核 13 搜索、首页、性能：复现和量查询数的脚本（只读业务代码，不改）。

在测试机上跑：
    bash scripts/remote-check.sh run uv run pytest -q -s -p no:randomly \
        handoff/rounds/217-second-review/findings/13-probe.py

断言「问题存在」的条目：绿 = 复现了。量数的条目只打印，不断言。
"""

import time
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import User
from core.tests.test_chapter15_audit import (  # noqa: F401
    _new_people,
    _publish_article,
    _scrim_seed,
    count_queries,
    site_tree,
)


def _cache_rows():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_cache")
        return cursor.fetchone()[0]


def _cache_keys_like(fragment):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT cache_key FROM django_cache WHERE cache_key LIKE %s",
            [f"%{fragment}%"],
        )
        return [row[0] for row in cursor.fetchall()]


# --- 13-1 DatabaseCache 的 300 条上限按键名字母序删掉别的限流 -----------------


@pytest.mark.django_db
def test_13_1_cull_wipes_the_daily_avatar_limit():
    from core.ratelimit import over_limit

    cache.clear()
    for _ in range(5):
        assert not over_limit("avatar-upload:1", 5, 86400)
    assert over_limit("avatar-upload:1", 5, 86400), "第 6 次本该被拒"
    # 310 位访客（或一个 IPv6 /64 里的 310 个地址）各搜一次。
    for index in range(310):
        over_limit(f"search:2001:db8::{index:x}", 30, 60)
    print(f"\n  缓存表行数：{_cache_rows()}")
    print(f"  avatar-upload 键还在吗：{_cache_keys_like('avatar-upload')}")
    again = over_limit("avatar-upload:1", 5, 86400)
    print(f"  第 7 次上传头像被拒吗：{again}")
    assert not again  # 复现：每天 5 次的限额被清零


@pytest.mark.django_db
def test_13_1_cull_wipes_allauth_login_failed_lockout(client):
    from django.urls import reverse

    victim = _new_people(1)[0]
    url = reverse("account_login")
    attacker = {"HTTP_X_REAL_IP": "203.0.113.9"}

    def attempt():
        response = client.post(
            url, {"login": victim.email, "password": "wrong-guess"}, **attacker
        )
        form = response.context["form"] if response.context else None
        return " ".join(form.non_field_errors()) if form is not None else ""

    errors = [attempt() for _ in range(6)]
    print(f"\n  第 1 次：{errors[0]}\n  第 6 次：{errors[5]}")
    locked_message = errors[5]
    assert locked_message != errors[0], "allauth 的 5/300s/key 没有锁住第 6 次"
    print(f"  login_failed 键：{len(_cache_keys_like('allauth:rl:login_failed'))} 个")
    # 别的访客（这里用 IPv6 地址轮换）各搜一次，只为让缓存表超过 300 条。
    for index in range(320):
        client.get("/search/?q=x", HTTP_X_REAL_IP=f"2001:db8::{index:x}")
    print(f"  缓存表行数：{_cache_rows()}")
    print(f"  login_failed 键：{len(_cache_keys_like('allauth:rl:login_failed'))} 个")
    seventh = attempt()
    print(f"  第 7 次：{seventh}")
    assert seventh != locked_message  # 复现：锁定被清掉，又能接着猜密码


# --- 13-2 站内搜索等的按 IP 限流对 IPv6 按整个地址算 ----------------------------


@pytest.mark.django_db
def test_13_2_one_ipv6_slash_64_never_hits_the_search_limit(client):
    cache.clear()
    same = [
        client.get("/search/?q=x", HTTP_X_REAL_IP="2001:db8::1").status_code
        for _ in range(31)
    ]
    rotated = [
        client.get("/search/?q=x", HTTP_X_REAL_IP=f"2001:db8::{index + 2:x}").status_code
        for index in range(100)
    ]
    print(f"\n  同一地址 31 次：最后一次 {same[-1]}")
    print(f"  同一 /64 换 100 个地址：429 的次数 {rotated.count(429)}")
    assert same[-1] == 429 and 429 not in rotated


# --- 13-3 状态片段的编号参数：上标数字、超长数字是 500 ------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "slot",
    [
        "team-join:²",
        "scrim-actions:²",
        "tournament-actions:²",
        "article-comments:99999999999999999999",
        "team-join:99999999999999999999",
    ],
)
def test_13_3_state_fragment_slot_arguments(client, slot):
    client.raise_request_exception = False
    response = client.get(f"/_fragments/state/?slots={slot}")
    print(f"\n  {slot} → {response.status_code}")


# --- 13-4 搜索摘录：casefold 改了长度后位置对不上 -----------------------------------


def test_13_4_excerpt_misses_the_hit_after_length_changing_folds():
    from search.services import excerpt

    text = "ß" * 60 + "龙刃" + "。" * 200
    shown = excerpt(text, ["龙刃"])
    print(f"\n  摘录：{shown!r}")
    assert "龙刃" not in shown  # 复现：命中的词不在摘录里


# --- 13-5 搜索的赛事与内战：赛事全排在前面，21 场赛事命中时内战一条都不出 ------------


@pytest.mark.django_db
def test_13_5_events_list_tournaments_first_and_all_old_scrims():
    from scrims.models import Scrim, ScrimStatus
    from search.services import search_events
    from tournaments.models import Tournament, TournamentStatus

    now = timezone.now()
    for index in range(21):
        Tournament.objects.create(
            title=f"秋季赛{index}",
            registration_opens_at=now - timedelta(days=1),
            registration_closes_at=now + timedelta(days=7),
            status=TournamentStatus.PUBLISHED,
            published_at=now,
        )
    newest = Scrim.objects.create(
        title="秋季内战（刚改过）",
        starts_at=now + timedelta(days=1),
        status=ScrimStatus.PUBLISHED,
    )
    old = Scrim.objects.create(
        title="去年的内战",
        starts_at=now - timedelta(days=400),
        status=ScrimStatus.FINISHED,
    )
    group = search_events(["秋季"])
    titles = [hit.title for hit in group.hits]
    print(f"\n  命中 {len(titles)} 条，截断={group.truncated}，内战在里面吗：{newest.title in titles}")
    old_hits = [hit.title for hit in search_events(["去年"]).hits]
    print(f"  400 天前结束的内战：{old_hits}")
    from scrims.services import public_scrims

    print(f"  它在内战列表里吗：{public_scrims().filter(pk=old.pk).exists()}")
    assert newest.title not in titles and old_hits == ["去年的内战"]


# --- 量数：查询数随数据量 -------------------------------------------------------------


@pytest.mark.django_db
def test_measure_sitemap(site_tree, client):
    from scrims.models import Scrim, ScrimStatus
    from teams import services as team_services
    from tournaments.models import Tournament, TournamentStatus

    def seed(count):
        now = timezone.now()
        for person in _new_people(count):
            _publish_article(person)
            team_services.create_team(user=person, name=f"地图队{person.pk}")
            Tournament.objects.create(
                title=f"地图赛{person.pk}",
                registration_opens_at=now - timedelta(days=1),
                registration_closes_at=now + timedelta(days=7),
                status=TournamentStatus.PUBLISHED,
                published_at=now,
            )
            Scrim.objects.create(
                title=f"地图内战{person.pk}",
                starts_at=now + timedelta(days=1),
                status=ScrimStatus.PUBLISHED,
            )

    seed(3)
    few = count_queries(client, "/sitemap.xml")
    seed(7)
    many = count_queries(client, "/sitemap.xml")
    print(f"\n  /sitemap.xml 3 份 → {few} 次 | 10 份 → {many} 次")


@pytest.mark.django_db
def test_measure_search_events_and_members(site_tree, client):
    from scrims.models import Scrim, ScrimStatus
    from tournaments.models import Tournament, TournamentStatus

    def seed(count):
        now = timezone.now()
        for person in _new_people(count):
            Tournament.objects.create(
                title=f"审计赛{person.pk}",
                registration_opens_at=now - timedelta(days=1),
                registration_closes_at=now + timedelta(days=7),
                status=TournamentStatus.PUBLISHED,
                published_at=now,
            )
            Scrim.objects.create(
                title=f"审计内战{person.pk}",
                starts_at=now + timedelta(days=1),
                status=ScrimStatus.PUBLISHED,
            )

    seed(3)
    cache.clear()
    few = count_queries(client, "/search/?q=审计")
    seed(7)
    cache.clear()
    many = count_queries(client, "/search/?q=审计")
    print(f"\n  /search/?q=审计（赛事、内战、成员）3 份 → {few} 次 | 10 份 → {many} 次")


@pytest.mark.django_db
def test_measure_member_groups(client):
    from allauth.account.models import EmailAddress

    from members.models import MemberGroup, MemberGroupMembership

    people = []
    for index in range(10):
        user = User.objects.create_user(
            email=f"g{index}@example.com",
            password="x-Long-Password-1",
            nickname=f"组员{index}",
            agreed_terms_at=timezone.now(),
            agreed_cross_border_at=timezone.now(),
        )
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        people.append(user)

    def groups(count):
        start = MemberGroup.objects.count()
        for index in range(count):
            group = MemberGroup.objects.create(name=f"分组{start + index}")
            MemberGroupMembership.objects.create(group=group, user=people[start + index])

    groups(1)
    few = count_queries(client, "/members/")
    groups(5)
    many = count_queries(client, "/members/")
    print(f"\n  /members/ 1 个分组 → {few} 次 | 6 个分组 → {many} 次")


@pytest.mark.django_db
def test_measure_state_fragment_with_agenda(site_tree, client):
    me = _new_people(1)[0]
    client.force_login(me)
    seed = _scrim_seed(me)
    url = "/_fragments/state/?slots=account,messages,my-agenda"
    seed(3)
    cache.clear()
    client.get(url)
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    few = len(captured)
    writes = [
        q["sql"].split()[0]
        for q in captured.captured_queries
        if q["sql"].split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "BEGIN"}
    ]
    seed(7)
    many = count_queries(client, url)
    print(f"\n  状态片段（含我的安排）3 条 → {few} 次 | 10 条 → {many} 次；状态码 {response.status_code}")
    print(f"  每次片段里的写语句：{writes}")
    print(f"  全部语句：{[q['sql'][:70] for q in captured.captured_queries]}")


# --- 量时间：成员页和搜索到设计规模 -------------------------------------------------


def _bulk_members(count, start):
    from allauth.account.models import EmailAddress

    now = timezone.now()
    users = User.objects.bulk_create(
        [
            User(
                email=f"bulk{start + index}@example.com",
                nickname=f"成员{start + index}",
                password="!",
                agreed_terms_at=now,
                agreed_cross_border_at=now,
                main_role=["tank", "damage", "support"][index % 3],
                motto="一起上分",
            )
            for index in range(count)
        ]
    )
    EmailAddress.objects.bulk_create(
        [
            EmailAddress(user=user, email=user.email, verified=True, primary=True)
            for user in users
        ]
    )


def _timed(client, url, runs=3):
    client.get(url)
    best = None
    for _ in range(runs):
        started = time.perf_counter()
        response = client.get(url)
        spent = time.perf_counter() - started
        best = spent if best is None else min(best, spent)
    return best, len(response.content), response.status_code


@pytest.mark.django_db
def test_measure_member_page_at_scale(client):
    done = 0
    for total in (500, 2000, 5000):
        _bulk_members(total - done, done)
        done = total
        for url in ("/members/", "/members/?role=tank"):
            spent, size, status = _timed(client, url)
            print(
                f"\n  {total} 人 {url:24} {status} 最快 {spent * 1000:.0f} ms，"
                f"HTML {size / 1024:.0f} KB"
            )


@pytest.mark.django_db
def test_measure_search_at_scale(site_tree, client):
    from content.models import ArticlePage

    author = _new_people(1)[0]
    body = "这是一段正常长度的文章正文，讲比赛复盘和英雄理解。" * 120  # 约 3000 字
    for count in (100, 300):
        while ArticlePage.objects.count() < count:
            page = _publish_article(author)
            page.body = body
            page.save_revision().publish()
        cache.clear()
        spent, size, status = _timed(client, "/search/?q=没有这个词")
        cache.clear()
        print(f"\n  {count} 篇文章，搜不到的词：{status} 最快 {spent * 1000:.0f} ms")
