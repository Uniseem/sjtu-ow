"""Design 9.1 and 9.2: scrim visibility, signup rules, reminders."""

from datetime import timedelta

import pytest
from django.core import mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import ContactMethod, ContactType, GameAccount, User
from scrims import services
from scrims.models import Role, Scrim, ScrimFormat, ScrimSignup, ScrimStatus, Team

DIAMOND_3 = 22
PLATINUM_1 = 18


def make_user(email, nickname, *, sjtu=True, tank=None, damage=DIAMOND_3, support=None):
    now = timezone.now()
    user = User.objects.create_user(
        email=email,
        password="Correct-Horse-Battery-1",
        nickname=nickname,
        is_sjtu=sjtu,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    GameAccount.objects.create(
        user=user,
        battletag=f"{nickname}#1234",
        rank_tank=tank,
        rank_damage=damage,
        rank_support=support,
    )
    ContactMethod.objects.create(user=user, type=ContactType.QQ, value="123456789")
    return user


def make_scrim(**kwargs):
    now = timezone.now()
    options = {
        "title": "周五内战",
        "starts_at": now + timedelta(days=1),
        "format": ScrimFormat.RQ_5V5,
        "status": ScrimStatus.PUBLISHED,
    }
    options.update(kwargs)
    return Scrim.objects.create(**options)


@pytest.fixture
def scrim(db):
    return make_scrim()


@pytest.fixture
def player(db):
    return make_user("p1@example.com", "玩家甲", tank=DIAMOND_3, support=PLATINUM_1)


# --- visibility ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_list_shows_published_and_recently_finished(db):
    now = timezone.now()
    published = make_scrim(title="已发布")
    recent = make_scrim(
        title="刚结束", status=ScrimStatus.FINISHED, starts_at=now - timedelta(days=3)
    )
    make_scrim(
        title="很久以前",
        status=ScrimStatus.FINISHED,
        starts_at=now - timedelta(days=40),
    )
    make_scrim(title="已取消", status=ScrimStatus.CANCELLED)
    make_scrim(title="草稿", status=ScrimStatus.DRAFT)

    titles = [scrim.title for scrim in services.public_scrims()]

    assert set(titles) == {published.title, recent.title}


@pytest.mark.django_db
def test_a_draft_is_a_404_but_a_cancelled_one_is_not(client, db):
    draft = make_scrim(status=ScrimStatus.DRAFT)
    cancelled = make_scrim(status=ScrimStatus.CANCELLED)

    assert client.get(f"/scrims/{draft.pk}/").status_code == 404

    response = client.get(f"/scrims/{cancelled.pk}/")
    assert response.status_code == 200
    assert "已取消" in response.content.decode()


@pytest.mark.django_db
def test_the_detail_page_never_shows_ranks_or_game_ids(client, scrim, player):
    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.TANK, Role.DAMAGE],
    )

    html = client.get(f"/scrims/{scrim.pk}/").content.decode()

    assert "玩家甲" in html
    assert "坦克" in html
    assert "玩家甲#1234" not in html  # design 9.2: no game IDs
    assert "钻石" not in html  # design 9.2: no ranks
    assert "白金" not in html


@pytest.mark.django_db
def test_signup_counts(client, scrim):
    tank = make_user("t@example.com", "坦克哥", tank=DIAMOND_3)
    both = make_user("b@example.com", "全能", tank=DIAMOND_3, support=DIAMOND_3)
    for user, roles in ((tank, [Role.TANK]), (both, [Role.TANK, Role.SUPPORT])):
        services.sign_up(
            scrim=scrim,
            user=user,
            game_account_id=user.game_accounts.first().pk,
            roles=roles,
        )

    counts = services.signup_counts(scrim)

    assert counts == {"total": 2, "tank": 2, "damage": 0, "support": 1}


# --- signup rules --------------------------------------------------------------


@pytest.mark.django_db
def test_role_queue_requires_a_rank_for_every_ticked_role(scrim, player):
    """Design 9.2: 角色限定 — each ticked role needs a rank on that ID."""
    account = player.game_accounts.first()
    account.rank_support = None
    account.save()

    with pytest.raises(services.ScrimError) as caught:
        services.sign_up(
            scrim=scrim,
            user=player,
            game_account_id=account.pk,
            roles=[Role.TANK, Role.SUPPORT],
        )

    assert "支援" in str(caught.value)
    assert not scrim.signups.exists()


@pytest.mark.django_db
def test_role_queue_accepts_roles_that_have_ranks(scrim, player):
    signup = services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.TANK, Role.DAMAGE],
    )
    assert signup.role_tank and signup.role_damage and not signup.role_support


@pytest.mark.django_db
def test_open_queue_only_needs_one_rank_anywhere(db):
    """Design 9.2: 不限位置 — one rank on the chosen ID is enough."""
    scrim = make_scrim(format=ScrimFormat.OPEN_5V5)
    player = make_user("open@example.com", "不限位", damage=DIAMOND_3)

    signup = services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.TANK, Role.SUPPORT],  # no ranks for these
    )

    assert signup.role_tank and signup.role_support


@pytest.mark.django_db
def test_open_queue_still_needs_at_least_one_rank(db):
    scrim = make_scrim(format=ScrimFormat.OPEN_5V5)
    player = make_user("blank@example.com", "没段位", damage=None)

    with pytest.raises(services.ScrimError, match="段位"):
        services.sign_up(
            scrim=scrim,
            user=player,
            game_account_id=player.game_accounts.first().pk,
            roles=[Role.DAMAGE],
        )


@pytest.mark.django_db
def test_at_least_one_role(scrim, player):
    with pytest.raises(services.ScrimError, match="至少"):
        services.sign_up(
            scrim=scrim,
            user=player,
            game_account_id=player.game_accounts.first().pk,
            roles=[],
        )


@pytest.mark.django_db
def test_cannot_use_someone_elses_game_id(scrim, player):
    other = make_user("other@example.com", "别人")

    with pytest.raises(services.ScrimError, match="自己的游戏 ID"):
        services.sign_up(
            scrim=scrim,
            user=player,
            game_account_id=other.game_accounts.first().pk,
            roles=[Role.DAMAGE],
        )


# --- the seven preconditions ---------------------------------------------------


@pytest.mark.django_db
def test_sjtu_only(db):
    scrim = make_scrim(sjtu_only=True)
    outsider = make_user("out@example.com", "校外", sjtu=False)

    problems = services.signup_problems(scrim=scrim, user=outsider)

    assert any("仅限交大" in problem for problem in problems)


@pytest.mark.django_db
def test_a_draft_scrim_refuses_signups(player):
    scrim = make_scrim(status=ScrimStatus.DRAFT)
    problems = services.signup_problems(scrim=scrim, user=player)
    assert any("不接受报名" in problem for problem in problems)


@pytest.mark.django_db
def test_a_cancelled_scrim_refuses_signups(player):
    scrim = make_scrim(status=ScrimStatus.CANCELLED)
    problems = services.signup_problems(scrim=scrim, user=player)
    assert any("不接受报名" in problem for problem in problems)


@pytest.mark.django_db
def test_past_the_deadline(player):
    now = timezone.now()
    scrim = make_scrim(
        starts_at=now + timedelta(days=1), signup_closes_at=now - timedelta(hours=1)
    )
    problems = services.signup_problems(scrim=scrim, user=player)
    assert any("截止" in problem for problem in problems)


@pytest.mark.django_db
def test_an_empty_deadline_means_up_until_it_starts(player):
    now = timezone.now()
    scrim = make_scrim(starts_at=now + timedelta(hours=1), signup_closes_at=None)
    assert scrim.signup_deadline == scrim.starts_at
    assert services.signup_problems(scrim=scrim, user=player) == []


@pytest.mark.django_db
def test_an_incomplete_profile(scrim, player):
    player.contact_methods.all().delete()
    problems = services.signup_problems(scrim=scrim, user=player)
    assert any("资料不完整" in problem for problem in problems)


@pytest.mark.django_db
def test_a_deactivated_account(scrim, player):
    player.is_active = False
    player.save(update_fields=["is_active"])
    problems = services.signup_problems(scrim=scrim, user=player)
    assert any("停用" in problem for problem in problems)


@pytest.mark.django_db
def test_the_feature_permission(scrim, player):
    from accounts.models import Feature, FeatureUserRule

    FeatureUserRule.objects.create(
        user=player, feature=Feature.SCRIM_SIGNUP, allowed=False
    )
    problems = services.signup_problems(scrim=scrim, user=player)
    assert any("无法报名内战" in problem for problem in problems)


@pytest.mark.django_db
def test_an_anonymous_visitor(scrim):
    from django.contrib.auth.models import AnonymousUser

    assert services.signup_problems(scrim=scrim, user=AnonymousUser()) == ["请先登录"]


# --- editing and cancelling ----------------------------------------------------


@pytest.mark.django_db
def test_signing_up_twice_updates_instead_of_duplicating(scrim, player):
    account = player.game_accounts.first()
    services.sign_up(
        scrim=scrim, user=player, game_account_id=account.pk, roles=[Role.DAMAGE]
    )
    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=account.pk,
        roles=[Role.TANK, Role.DAMAGE],
    )

    assert scrim.signups.count() == 1
    signup = scrim.signups.get()
    assert signup.role_tank and signup.role_damage


@pytest.mark.django_db(transaction=True)
def test_the_unique_constraint_holds(scrim, player):
    account = player.game_accounts.first()
    ScrimSignup.objects.create(
        scrim=scrim, user=player, game_account=account, role_damage=True
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        ScrimSignup.objects.create(
            scrim=scrim, user=player, game_account=account, role_tank=True
        )


@pytest.mark.django_db
def test_cancelling_a_signup(scrim, player):
    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )

    services.cancel(scrim=scrim, user=player)

    assert not scrim.signups.exists()


@pytest.mark.django_db
def test_cancelling_after_the_split_marks_the_teams_stale(scrim, player):
    """Design 9.2: dropping out after a split must be visible to the admin."""
    signup = services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    signup.is_selected = True
    signup.team = Team.A
    signup.assigned_role = Role.DAMAGE
    signup.save()
    Scrim.objects.filter(pk=scrim.pk).update(teams_generated_at=timezone.now())
    scrim.refresh_from_db()
    assert services.teams_are_stale(scrim) is False

    services.cancel(scrim=scrim, user=player)

    scrim.refresh_from_db()
    assert services.teams_are_stale(scrim) is True


@pytest.mark.django_db
def test_changing_the_game_id_clears_the_placement(scrim, player):
    """The split used the old ID's ranks, so it no longer applies."""
    signup = services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    signup.is_selected = True
    signup.team = Team.A
    signup.assigned_role = Role.DAMAGE
    signup.rating_used = DIAMOND_3
    signup.save()
    second = GameAccount.objects.create(
        user=player, battletag="玩家甲#5678", rank_damage=PLATINUM_1
    )

    services.sign_up(
        scrim=scrim, user=player, game_account_id=second.pk, roles=[Role.DAMAGE]
    )

    signup.refresh_from_db()
    assert signup.game_account_id == second.pk
    assert signup.is_selected is False
    assert signup.team == ""
    assert signup.rating_used is None


@pytest.mark.django_db
def test_cannot_cancel_after_the_deadline(player):
    now = timezone.now()
    scrim = make_scrim(starts_at=now + timedelta(days=1))
    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    Scrim.objects.filter(pk=scrim.pk).update(signup_closes_at=now - timedelta(hours=1))
    scrim.refresh_from_db()

    with pytest.raises(services.ScrimError, match="截止"):
        services.cancel(scrim=scrim, user=player)


@pytest.mark.django_db
def test_cancelling_without_a_signup(scrim, player):
    with pytest.raises(services.ScrimError, match="还没有报名"):
        services.cancel(scrim=scrim, user=player)


# --- game ID deletion ----------------------------------------------------------


@pytest.mark.django_db
def test_a_game_id_in_use_by_a_signup_cannot_be_deleted(scrim, player):
    from accounts.services import deletion_blocked_reason

    account = player.game_accounts.first()
    assert deletion_blocked_reason(account) is None

    services.sign_up(
        scrim=scrim, user=player, game_account_id=account.pk, roles=[Role.DAMAGE]
    )

    assert "内战" in deletion_blocked_reason(account)


@pytest.mark.django_db
def test_a_finished_scrim_does_not_block_deletion(player):
    from accounts.services import deletion_blocked_reason

    scrim = make_scrim()
    account = player.game_accounts.first()
    services.sign_up(
        scrim=scrim, user=player, game_account_id=account.pk, roles=[Role.DAMAGE]
    )
    Scrim.objects.filter(pk=scrim.pk).update(status=ScrimStatus.FINISHED)

    assert deletion_blocked_reason(account) is None


# --- reminders and cancellation emails -----------------------------------------


@pytest.mark.django_db
def test_the_reminder_goes_out_once(scrim, player, settings):
    from scrims.tasks import send_scrim_reminder

    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    Scrim.objects.filter(pk=scrim.pk).update(
        starts_at=timezone.now() + timedelta(minutes=30)
    )

    assert send_scrim_reminder.func(scrim.pk) == "sent:1"
    assert len(mail.outbox) == 1
    assert scrim.title in mail.outbox[0].subject

    assert send_scrim_reminder.func(scrim.pk) == "already_sent"
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_the_reminder_reschedules_when_the_start_moves_later(scrim, player):
    from scrims.tasks import send_scrim_reminder

    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    Scrim.objects.filter(pk=scrim.pk).update(
        starts_at=timezone.now() + timedelta(days=5)
    )

    assert send_scrim_reminder.func(scrim.pk) == "rescheduled"
    assert mail.outbox == []


@pytest.mark.django_db
def test_no_reminder_for_a_cancelled_scrim(scrim, player):
    from scrims.tasks import send_scrim_reminder

    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    Scrim.objects.filter(pk=scrim.pk).update(status=ScrimStatus.CANCELLED)

    assert send_scrim_reminder.func(scrim.pk) == "not_published"
    assert mail.outbox == []


@pytest.mark.django_db(transaction=True)
def test_cancelling_a_scrim_mails_everyone(db):
    scrim = make_scrim()
    for index in range(2):
        user = make_user(f"c{index}@example.com", f"报名者{index}")
        services.sign_up(
            scrim=scrim,
            user=user,
            game_account_id=user.game_accounts.first().pk,
            roles=[Role.DAMAGE],
        )
    mail.outbox.clear()

    services.cancel_scrim(scrim=scrim)

    assert len(mail.outbox) == 2
    assert all("已取消" in message.subject for message in mail.outbox)
    scrim.refresh_from_db()
    assert scrim.status == ScrimStatus.CANCELLED


@pytest.mark.django_db
def test_a_cancelled_scrim_cannot_be_published(scrim):
    services.cancel_scrim(scrim=scrim)
    with pytest.raises(services.ScrimError, match="已取消"):
        services.publish(scrim=scrim)


# --- the pages themselves ------------------------------------------------------


@pytest.mark.django_db
def test_the_signup_box_uses_no_alpine_expressions(client, scrim, player):
    """The site ships Alpine's CSP build, which cannot evaluate inline JS.

    A page that looks fine but whose buttons do nothing still returns 200,
    so assert on the markup rather than the status code.
    """
    client.force_login(player)
    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )

    html = client.get(f"/scrims/{scrim.pk}/").content.decode()

    for attribute in ("x-data", "x-on:", "x-ref", "@click"):
        assert attribute not in html, attribute
    assert "<details" in html  # the edit form opens without any script


@pytest.mark.django_db
def test_the_pages_carry_no_inline_styles(client, scrim, player):
    services.sign_up(
        scrim=scrim,
        user=player,
        game_account_id=player.game_accounts.first().pk,
        roles=[Role.DAMAGE],
    )
    for url in ("/scrims/", f"/scrims/{scrim.pk}/"):
        assert 'style="' not in client.get(url).content.decode(), url


@pytest.mark.django_db
def test_the_fragment_matches_the_live_page(client, scrim, player):
    """Design 13.13.3: the slot and the live page must agree."""
    client.force_login(player)
    live = client.get(f"/scrims/{scrim.pk}/").content.decode()
    fragment = client.get(f"/_fragments/scrims/{scrim.pk}/actions/").content.decode()

    marker = f'data-slot="scrim-actions:{scrim.pk}"'
    assert marker in live
    assert marker in fragment
    assert "报名" in fragment


@pytest.mark.django_db
def test_the_fragment_404s_for_a_draft(client, db):
    draft = make_scrim(status=ScrimStatus.DRAFT)
    assert client.get(f"/_fragments/scrims/{draft.pk}/actions/").status_code == 404


@pytest.mark.django_db
def test_signing_up_through_the_view(client, scrim, player):
    client.force_login(player)
    account = player.game_accounts.first()

    response = client.post(
        f"/scrims/{scrim.pk}/signup/",
        {"game_account": account.pk, "roles": ["tank", "damage"]},
    )

    assert response.status_code == 302
    signup = scrim.signups.get()
    assert signup.role_tank and signup.role_damage


@pytest.mark.django_db
def test_the_view_reports_problems_instead_of_crashing(client, scrim, player):
    client.force_login(player)
    account = player.game_accounts.first()
    account.rank_support = None
    account.save()

    response = client.post(
        f"/scrims/{scrim.pk}/signup/",
        {"game_account": account.pk, "roles": ["support"]},
        follow=True,
    )

    assert response.status_code == 200
    assert not scrim.signups.exists()
    assert any("支援" in str(m) for m in response.context["messages"])


@pytest.mark.django_db
def test_prerender_targets_track_public_scrims(db):
    from scrims.prerender_targets import scrim_targets

    published = make_scrim()
    draft = make_scrim(status=ScrimStatus.DRAFT)

    targets = scrim_targets()

    assert targets["/scrims/"] == "scrim_index"
    assert targets[f"/scrims/{published.pk}/"] == "scrim"
    assert f"/scrims/{draft.pk}/" not in targets


# --- refusals the guard sweep found untested (round 059) ------------------------


@pytest.mark.django_db
def test_a_scrim_cannot_be_cancelled_twice(scrim):
    """A second cancel would mail everyone who signed up again."""
    services.cancel_scrim(scrim=scrim)
    with pytest.raises(services.ScrimError, match="已经取消"):
        services.cancel_scrim(scrim=scrim)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "method, name",
    [
        ("post", "scrim_signup"),
        ("post", "scrim_cancel_signup"),
        ("get", "me_scrims"),
    ],
)
def test_signed_out_visitors_are_sent_to_log_in(client, scrim, method, name):
    from django.urls import reverse

    args = [] if name == "me_scrims" else [scrim.pk]
    response = getattr(client, method)(reverse(name, args=args))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_a_game_id_used_by_a_finished_scrim_can_really_be_deleted(client, player):
    """Round 068: the guard said yes but the foreign key said PROTECT."""
    from django.urls import reverse

    from scrims.models import ScrimSignup

    scrim = make_scrim()
    account = player.game_accounts.first()
    signup = services.sign_up(
        scrim=scrim, user=player, game_account_id=account.pk, roles=[Role.DAMAGE]
    )
    Scrim.objects.filter(pk=scrim.pk).update(status=ScrimStatus.FINISHED)
    client.force_login(player)

    response = client.post(reverse("me_game_account_delete", args=[account.pk]))

    assert response.status_code == 302
    assert not player.game_accounts.filter(pk=account.pk).exists()
    signup.refresh_from_db()
    assert signup.game_account is None
    assert signup.battletag == ScrimSignup.DELETED_ID_LABEL
    assert signup.rank_pairs == [("damage", "输出 未填段位")]
    assert signup.best_rating is None


@pytest.mark.django_db
def test_a_game_id_used_by_a_live_scrim_is_still_refused(client, scrim, player):
    from django.urls import reverse

    account = player.game_accounts.first()
    services.sign_up(
        scrim=scrim, user=player, game_account_id=account.pk, roles=[Role.DAMAGE]
    )
    client.force_login(player)

    response = client.post(
        reverse("me_game_account_delete", args=[account.pk]), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 400
    assert "内战" in response.content.decode()
    assert player.game_accounts.filter(pk=account.pk).exists()
