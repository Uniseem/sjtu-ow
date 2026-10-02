"""Round 097: a member's own page, basic version (design 6.4, details 4.6).

The user, 2026-10-03: 「要求成员可以点击进去，每个人都有一个个人主页，你先做好点
进去的基础页面，具体的设计我们后面再讨论」. Only what design-details 1.8 calls
public; rendered live and out of search engines for now.
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount
from accounts.ranks import encode_rank
from content.models import ArticleCategory
from content.tests.test_content import _article, _tree
from members.models import MemberGroup, MemberGroupMembership
from members.tests.test_members import _main, person
from teams import services as team_services
from teams.models import LeaveReason, TeamAlumnus

DIAMOND_3 = encode_rank("diamond", 3)


def _page(client, user):
    return client.get(reverse("member_detail", args=[user.pk]))


# --- who has a page ---------------------------------------------------------------


@pytest.mark.django_db
def test_only_the_people_on_the_showcase_have_a_page(client):
    shown = person("有主页")
    unverified = person("没验证", verified=False)
    gone = person("已停用", active=False)

    assert _page(client, shown).status_code == 200
    assert _page(client, unverified).status_code == 404
    assert _page(client, gone).status_code == 404
    assert client.get("/members/987654/").status_code == 404


@pytest.mark.django_db
def test_the_page_stays_out_of_search_engines(client):
    html = _page(client, person("不收录")).content.decode()
    assert '<meta name="robots" content="noindex">' in html


# --- what it shows -------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_shows_what_is_public_and_nothing_else(client):
    user = person("全都有")
    user.motto, user.main_role, user.is_sjtu = "推车不停", "damage", True
    user.save()
    GameAccount.objects.create(
        user=user, battletag="全都有#4321", rank_damage=DIAMOND_3
    )
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="98765432")
    group = MemberGroup.objects.create(name="社团干部")
    MemberGroupMembership.objects.create(group=group, user=user, title="社长、主播")

    main = _main(client, reverse("member_detail", args=[user.pk]))

    assert "<h1>全都有</h1>" in main
    assert "“推车不停”" in main
    assert 'class="c-role c-role--main"' in main and "钻石" in main
    assert "社团干部" in main
    for title in ("社长", "主播"):
        assert f'<dd class="c-tag">{title}</dd>' in main
    # design-details 1.8: never the game ID, the email, contacts or school.
    assert "全都有#4321" not in main
    assert user.email not in main
    assert "98765432" not in main
    assert "交大" not in main


@pytest.mark.django_db
def test_a_hidden_rank_stays_hidden(client):
    user = person("不公开")
    user.main_role, user.show_rank = "damage", False
    user.save()
    GameAccount.objects.create(user=user, battletag="不公开#1", rank_damage=DIAMOND_3)

    main = _main(client, reverse("member_detail", args=[user.pk]))

    assert 'class="c-role c-role--main"' in main
    assert "钻石" not in main


@pytest.mark.django_db
def test_current_teams_and_the_ones_left(client):
    user = person("队员甲")
    captain = person("队长乙")
    now = team_services.create_team(user=captain, name="现在的队")
    GameAccount.objects.create(user=user, battletag="队员甲#1")
    application = team_services.apply_to_team(team=now, user=user, roles={"tank": True})
    team_services.approve_application(application=application, actor=captain)
    old = team_services.create_team(user=person("老队长"), name="以前的队")
    TeamAlumnus.objects.create(
        team=old,
        user=user,
        role="member",
        joined_at=timezone.make_aware(timezone.datetime(2025, 9, 1)),
        left_at=timezone.make_aware(timezone.datetime(2026, 3, 1)),
        reason=LeaveReason.LEFT,
    )

    main = _main(client, reverse("member_detail", args=[user.pk]))

    teams = main[main.index("data-member-teams") : main.index("data-member-alumni")]
    assert now.get_absolute_url() in teams and "以前的队" not in teams
    alumni = main[main.index("data-member-alumni") :]
    assert old.get_absolute_url() in alumni
    assert "2025.09" in alumni and "2026.03" in alumni
    # How someone left is for the team's captain, not the public (details 5.4).
    assert "退出" not in alumni and "移除" not in alumni


@pytest.mark.django_db
def test_the_articles_they_wrote(client):
    _home, news = _tree()
    author = person("写文章的")
    category = ArticleCategory.objects.get(slug="guide")
    shown = _article(news, category, author, title="公开的攻略", slug="shown")
    _article(news, category, author, title="还是草稿", slug="draft", live=False)

    main = _main(client, reverse("member_detail", args=[author.pk]))

    articles = main[main.index("data-member-articles") :]
    assert shown.url in articles and "公开的攻略" in articles
    assert "还是草稿" not in articles
    assert '共 <span class="font-numeric">1</span> 篇' in articles


@pytest.mark.django_db
def test_the_page_costs_a_bounded_number_of_queries(
    client, django_assert_max_num_queries
):
    user = person("查询数")
    group = MemberGroup.objects.create(name="组")
    MemberGroupMembership.objects.create(group=group, user=user, title="甲")
    for index in range(3):
        captain = person(f"队长{index}")
        team = team_services.create_team(user=captain, name=f"队{index}")
        TeamAlumnus.objects.create(
            team=team,
            user=user,
            role="member",
            joined_at=timezone.now(),
            left_at=timezone.now(),
            reason=LeaveReason.LEFT,
        )
    with django_assert_max_num_queries(25):
        assert _page(client, user).status_code == 200


# --- the ways in ------------------------------------------------------------------


@pytest.mark.django_db
def test_every_card_on_the_showcase_opens_the_page(client):
    user = person("点得进")
    group = MemberGroup.objects.create(name="分组")
    MemberGroupMembership.objects.create(group=group, user=user, title="")
    url = reverse("member_detail", args=[user.pk])

    main = _main(client)

    assert f'<a href="{url}" class="c-person__name c-stretch"' in main
    assert f'<a href="{url}" class="c-roster__name c-stretch"' in main


@pytest.mark.django_db
def test_the_team_page_and_the_byline_lead_to_it(client):
    _home, news = _tree()
    captain = person("队长丙")
    team = team_services.create_team(user=captain, name="有链接的队")
    left = person("走了的")
    TeamAlumnus.objects.create(
        team=team,
        user=left,
        role="member",
        joined_at=timezone.now(),
        left_at=timezone.now(),
        reason=LeaveReason.LEFT,
    )
    team_html = client.get(team.get_absolute_url()).content.decode()
    assert reverse("member_detail", args=[captain.pk]) in team_html
    assert reverse("member_detail", args=[left.pk]) in team_html

    guide = ArticleCategory.objects.get(slug="guide")
    article = _article(news, guide, captain, title="署名", slug="by")
    article_html = client.get(article.url).content.decode()
    assert f'<a href="{reverse("member_detail", args=[captain.pk])}">队长丙</a>' in (
        article_html
    )


@pytest.mark.django_db
def test_someone_without_a_page_is_not_linked(client):
    """A deactivated person stays on a team's alumni list as a name only."""
    captain = person("队长丁")
    team = team_services.create_team(user=captain, name="留名的队")
    gone = person("停用了", active=False)
    TeamAlumnus.objects.create(
        team=team,
        user=gone,
        role="member",
        joined_at=timezone.now(),
        left_at=timezone.now(),
        reason=LeaveReason.LEFT,
    )

    html = client.get(team.get_absolute_url()).content.decode()

    assert "停用了" in html
    assert reverse("member_detail", args=[gone.pk]) not in html
