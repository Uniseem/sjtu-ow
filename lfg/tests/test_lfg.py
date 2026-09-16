from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Feature, FeatureUserRule, GameAccount, User
from core.models import GameMode, SiteSettings
from core.services import ensure_game_modes
from lfg import services
from lfg.models import LfgPost, LfgStatus


def _user(email, nickname, with_game_account=True):
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    if with_game_account:
        GameAccount.objects.create(user=user, battletag=f"{nickname}#1234")
    return user


@pytest.fixture
def modes(db):
    return ensure_game_modes()


@pytest.fixture
def driver(db):
    return _user("driver@example.com", "车主甲")


@pytest.fixture
def post(driver, modes):
    return services.create_post(
        user=driver,
        game_account=driver.game_accounts.first(),
        mode=modes[0],
        roles={"tank": True},
        start_at=timezone.now() + timedelta(minutes=30),
        note="来个坦克",
    )


# --- posting -------------------------------------------------------------------


@pytest.mark.django_db
def test_expiry_follows_the_start_time(post):
    assert post.expires_at == post.start_at + timedelta(hours=2)


@pytest.mark.django_db
def test_changing_the_time_recalculates_expiry(post, driver, modes):
    later = timezone.now() + timedelta(days=1)
    services.update_post(
        post=post,
        user=driver,
        game_account=driver.game_accounts.first(),
        mode=modes[1],
        roles={"damage": True},
        start_at=later,
        note="",
    )
    post.refresh_from_db()
    assert post.expires_at == post.start_at + timedelta(hours=2)
    assert post.mode == modes[1]
    assert post.role_tank is False


@pytest.mark.django_db
def test_start_time_window(driver, modes):
    with pytest.raises(services.LfgError):
        services.create_post(
            user=driver,
            game_account=driver.game_accounts.first(),
            mode=modes[0],
            roles={"tank": True},
            start_at=timezone.now() - timedelta(hours=1),
        )
    with pytest.raises(services.LfgError):
        services.create_post(
            user=driver,
            game_account=driver.game_accounts.first(),
            mode=modes[0],
            roles={"tank": True},
            start_at=timezone.now() + timedelta(days=8),
        )


@pytest.mark.django_db
def test_active_post_limit(driver, modes):
    site = SiteSettings.load()
    site.lfg_max_active_posts = 1
    site.save()
    services.create_post(
        user=driver,
        game_account=driver.game_accounts.first(),
        mode=modes[0],
        roles={"tank": True},
        start_at=timezone.now(),
    )
    allowed, reason = services.can_post(driver)
    assert not allowed and "最多" in reason


@pytest.mark.django_db
def test_posting_needs_a_game_account_and_the_feature(modes):
    without = _user("nogame-lfg@example.com", "没ID", with_game_account=False)
    allowed, reason = services.can_post(without)
    assert not allowed and "游戏 ID" in reason

    blocked = _user("blocked-lfg@example.com", "被禁用")
    FeatureUserRule.objects.create(
        user=blocked, feature=Feature.LFG_POST, allowed=False
    )
    allowed, reason = services.can_post(blocked)
    assert not allowed and "无法使用" in reason


@pytest.mark.django_db
def test_roles_are_required(driver, modes):
    with pytest.raises(services.LfgError) as exc:
        services.create_post(
            user=driver,
            game_account=driver.game_accounts.first(),
            mode=modes[0],
            roles={},
            start_at=timezone.now(),
        )
    assert "位置" in str(exc.value)


@pytest.mark.django_db
def test_someone_elses_game_id_is_refused(driver, modes):
    other = _user("other-lfg@example.com", "别人")
    with pytest.raises(services.LfgError):
        services.create_post(
            user=driver,
            game_account=other.game_accounts.first(),
            mode=modes[0],
            roles={"tank": True},
            start_at=timezone.now(),
        )


# --- status --------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_toggles_full_and_closes(post, driver):
    services.set_status(post=post, user=driver, status=LfgStatus.FULL)
    post.refresh_from_db()
    assert post.status == LfgStatus.FULL
    services.set_status(post=post, user=driver, status=LfgStatus.OPEN)
    post.refresh_from_db()
    assert post.status == LfgStatus.OPEN
    services.set_status(post=post, user=driver, status=LfgStatus.CLOSED)
    post.refresh_from_db()
    assert post.status == LfgStatus.CLOSED


@pytest.mark.django_db
def test_closed_posts_stay_closed(post, driver):
    services.set_status(post=post, user=driver, status=LfgStatus.CLOSED)
    with pytest.raises(services.LfgError) as exc:
        services.set_status(post=post, user=driver, status=LfgStatus.OPEN)
    assert "不能重新打开" in str(exc.value)


@pytest.mark.django_db
def test_other_users_cannot_touch_a_post(post):
    stranger = _user("stranger-lfg@example.com", "路人")
    with pytest.raises(services.LfgError):
        services.set_status(post=post, user=stranger, status=LfgStatus.CLOSED)
    with pytest.raises(services.LfgError):
        services.update_post(
            post=post,
            user=stranger,
            game_account=stranger.game_accounts.first(),
            mode=post.mode,
            roles={"tank": True},
            start_at=timezone.now(),
        )


# --- the board -----------------------------------------------------------------


@pytest.mark.django_db
def test_expired_posts_disappear(post):
    assert services.active_posts().count() == 1
    LfgPost.objects.filter(pk=post.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )
    assert services.active_posts().count() == 0


@pytest.mark.django_db
def test_closed_and_deactivated_owners_disappear(post, driver):
    services.set_status(post=post, user=driver, status=LfgStatus.CLOSED)
    assert services.active_posts().count() == 0

    LfgPost.objects.filter(pk=post.pk).update(status=LfgStatus.OPEN)
    assert services.active_posts().count() == 1
    driver.is_active = False
    driver.save()
    assert services.active_posts().count() == 0


@pytest.mark.django_db
def test_full_posts_sort_last(driver, modes):
    soon = timezone.now() + timedelta(minutes=5)
    full = services.create_post(
        user=driver,
        game_account=driver.game_accounts.first(),
        mode=modes[0],
        roles={"tank": True},
        start_at=soon,
    )
    services.set_status(post=full, user=driver, status=LfgStatus.FULL)
    other = _user("second-driver@example.com", "车主乙")
    later = services.create_post(
        user=other,
        game_account=other.game_accounts.first(),
        mode=modes[0],
        roles={"damage": True},
        start_at=soon + timedelta(hours=1),
    )
    assert list(services.active_posts()) == [later, full]


@pytest.mark.django_db
def test_filters(driver, modes):
    now = timezone.now()
    services.create_post(
        user=driver,
        game_account=driver.game_accounts.first(),
        mode=modes[0],
        roles={"tank": True},
        start_at=now,
    )
    other = _user("filter-driver@example.com", "车主丙")
    services.create_post(
        user=other,
        game_account=other.game_accounts.first(),
        mode=modes[1],
        roles={"support": True},
        start_at=now,
    )
    assert services.filtered_posts(mode_id=modes[0].pk).count() == 1
    assert services.filtered_posts(roles=["support"]).count() == 1
    assert services.filtered_posts(roles=["tank", "support"]).count() == 2
    assert services.filtered_posts(open_only=True).count() == 2


@pytest.mark.django_db
def test_board_needs_login(client, post):
    shell = client.get(reverse("lfg_index"))
    assert shell.status_code == 200
    assert "车主甲" not in shell.content.decode()

    html = client.get(reverse("lfg_list")).content.decode()
    assert "登录后查看" in html
    assert "车主甲" not in html


@pytest.mark.django_db
def test_board_shows_posts_to_members(client, post, driver):
    client.force_login(driver)
    html = client.get(reverse("lfg_list")).content.decode()
    assert "车主甲#1234" in html
    assert "来个坦克" in html
    assert 'data-copy="车主甲#1234"' in html


@pytest.mark.django_db
def test_shell_has_no_post_data(client, post):
    html = client.get(reverse("lfg_index")).content.decode()
    assert "hx-get" in html
    assert "every 30s" in html
    assert "车主甲#1234" not in html


@pytest.mark.django_db
def test_note_goes_to_the_review_queue(driver, modes, settings):
    from moderation.models import ModerationItem

    settings.MODERATION_API_KEY = "test-key"
    services.create_post(
        user=driver,
        game_account=driver.game_accounts.first(),
        mode=modes[0],
        roles={"tank": True},
        start_at=timezone.now(),
        note="求带飞，谢谢",
    )
    assert ModerationItem.objects.filter(target_type="lfg_note").count() == 1


@pytest.mark.django_db
def test_home_slot_counts_only_for_members(client, post, driver):
    url = reverse("state_fragment") + "?slots=home-lfg"
    anonymous = client.get(url).content.decode()
    assert "登录后查看" in anonymous

    client.force_login(driver)
    signed_in = client.get(url).content.decode()
    assert "当前 1 条招人中的车帖" in signed_in


@pytest.mark.django_db
def test_posting_is_rate_limited(client, driver, modes):
    from django.core.cache import cache

    cache.clear()
    client.force_login(driver)
    site = SiteSettings.load()
    site.lfg_max_active_posts = 50
    site.save()
    start = timezone.localtime() + timedelta(minutes=30)
    payload = {
        "game_account": driver.game_accounts.first().pk,
        "mode": modes[0].pk,
        "role_tank": "on",
        "start_at": start.strftime("%Y-%m-%dT%H:%M"),
        "note": "",
    }
    for _ in range(10):
        client.post(reverse("lfg_create"), payload, follow=True)
    assert LfgPost.objects.filter(owner=driver).count() == 10
    client.post(reverse("lfg_create"), payload, follow=True)
    assert LfgPost.objects.filter(owner=driver).count() == 10


# --- admin ---------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_can_close_a_post(client, post):
    admin = User.objects.create_superuser(
        email="admin-lfg@example.com",
        password="Correct-Horse-Battery-1",
        nickname="超管",
        agreed_terms_at=timezone.now(),
        agreed_cross_border_at=timezone.now(),
    )
    client.force_login(admin)
    assert client.get(reverse("lfg_posts:index")).status_code == 200
    url = reverse("lfg_admin_close", args=[post.pk])
    assert client.get(url).status_code == 200
    client.post(url, follow=True)
    post.refresh_from_db()
    assert post.status == LfgStatus.CLOSED


@pytest.mark.django_db
def test_ordinary_users_cannot_reach_the_admin_board(client, driver, post):
    client.force_login(driver)
    assert client.get(reverse("lfg_admin_close", args=[post.pk])).status_code == 302


@pytest.mark.django_db
def test_game_modes_are_seeded_once(db):
    first = ensure_game_modes()
    second = ensure_game_modes()
    assert len(first) == 5
    assert GameMode.objects.count() == 5
    assert [mode.pk for mode in first] == [mode.pk for mode in second]
