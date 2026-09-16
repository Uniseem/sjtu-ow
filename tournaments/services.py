"""Tournament rules and the hooks M4's registration round will fill in."""

from __future__ import annotations

import logging

from django.utils import timezone

from tournaments.models import Tournament, TournamentStatus

logger = logging.getLogger(__name__)

PHASE_LABELS = {
    "open": "报名中",
    "upcoming": "即将开始报名",
    "closed": "已截止",
    "finished": "已结束",
    "cancelled": "已取消",
}
LIST_PHASES = ("open", "upcoming", "closed", "finished")


class TournamentError(Exception):
    """Something an admin may not do right now; the message is shown."""


def listed_tournaments():
    return Tournament.objects.filter(
        status__in=[TournamentStatus.PUBLISHED, TournamentStatus.FINISHED]
    ).select_related("cover")


def grouped_tournaments(now=None):
    """The four groups on the list page, in order (design 8.2)."""
    now = now or timezone.now()
    groups = {phase: [] for phase in LIST_PHASES}
    for tournament in listed_tournaments():
        phase = tournament.phase(now)
        if phase in groups:
            groups[phase].append(tournament)
    groups["open"].sort(key=lambda item: item.registration_closes_at)
    groups["upcoming"].sort(key=lambda item: item.registration_opens_at)
    groups["closed"].sort(key=lambda item: item.registration_closes_at, reverse=True)
    groups["finished"].sort(
        key=lambda item: item.starts_at or item.created_at,
        reverse=True,
    )
    return [(phase, PHASE_LABELS[phase], groups[phase]) for phase in LIST_PHASES]


def has_registrations(tournament) -> bool:
    """Once anyone has registered, the review mode is locked (design 8.1)."""
    return tournament.registrations.exists()


def active_registration_captains(tournament):
    """Captains with a live registration, for the cancellation mail (8.1)."""
    from tournaments.models import ACTIVE_STATUSES

    captains = []
    registrations = tournament.registrations.filter(
        status__in=ACTIVE_STATUSES
    ).select_related("team")
    for registration in registrations:
        captain = registration.team.captain()
        if captain is not None:
            captains.append(captain)
    return captains


def approved_teams(tournament):
    """Approved teams and their size, for the public page (design 8.2).

    The count is annotated rather than asked per row: design 15.1 assumes up
    to 200 teams in one tournament, and counting inside the loop made this
    page issue one query per team.
    """
    from django.db.models import Count

    from tournaments.models import RegistrationStatus

    registrations = (
        tournament.registrations.filter(status=RegistrationStatus.APPROVED)
        .select_related("team")
        .annotate(roster_size=Count("members"))
        .order_by("submitted_at")
    )
    return [
        {
            "team": registration.team,
            "team_name": registration.team_name,
            "member_count": registration.roster_size,
        }
        for registration in registrations
    ]


def roster_min_warning(tournament) -> str:
    from core.models import SiteSettings

    team_max = int(SiteSettings.load().team_max_members or 10)
    if tournament.roster_min > team_max:
        return (
            f"参赛人数下限 {tournament.roster_min} 大于全站战队人数上限 "
            f"{team_max}，没有战队能满足这个要求。"
        )
    return ""


def can_manage(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm("tournaments.change_tournament")
    )


def publish(*, tournament, actor) -> Tournament:
    if tournament.status == TournamentStatus.CANCELLED:
        raise TournamentError("已取消的赛事不能再发布。")
    tournament.status = TournamentStatus.PUBLISHED
    if tournament.published_at is None:
        tournament.published_at = timezone.now()
    tournament.save(update_fields=["status", "published_at", "updated_at"])
    after_change(tournament, actor=actor)
    return tournament


def finish(*, tournament, actor) -> Tournament:
    if tournament.status != TournamentStatus.PUBLISHED:
        raise TournamentError("只有已发布的赛事可以标记为已结束。")
    tournament.status = TournamentStatus.FINISHED
    tournament.save(update_fields=["status", "updated_at"])
    after_change(tournament, actor=actor)
    return tournament


def cancel(*, tournament, actor, reason="") -> Tournament:
    if tournament.status == TournamentStatus.CANCELLED:
        raise TournamentError("赛事已经取消了。")
    tournament.status = TournamentStatus.CANCELLED
    tournament.save(update_fields=["status", "updated_at"])
    notify_cancelled(tournament, reason)
    after_change(tournament, actor=actor)
    return tournament


def notify_cancelled(tournament, reason="") -> None:
    """Mail every captain with a live registration (design 8.1). M4/015."""
    from tournaments import notifications

    for captain in active_registration_captains(tournament):
        notifications.tournament_cancelled(tournament, captain, reason)


def can_delete(tournament) -> bool:
    """A tournament that was published once can only be cancelled (design 8.1)."""
    return tournament.published_at is None and tournament.status in (
        TournamentStatus.DRAFT,
    )


def after_change(tournament, actor=None) -> None:
    """Static pages follow the tournament; the description goes to AI review."""
    from core import prerender

    if tournament.is_listed:
        prerender.request_page(tournament.get_absolute_url(), kind="tournament")
    else:
        prerender.request_removal(tournament.get_absolute_url())
    prerender.request_page("/tournaments/", kind="tournament_index")
    schedule_phase_refresh(tournament)
    if tournament.description:
        _submit_moderation(tournament, actor)


def schedule_phase_refresh(tournament) -> None:
    """Regenerate when registration opens and when it closes (design 13.13.4)."""
    from core import prerender
    from core.tasks import prerender_page

    if not prerender.is_enabled() or not tournament.is_listed:
        return
    now = timezone.now()
    for moment in (
        tournament.registration_opens_at,
        tournament.registration_closes_at,
    ):
        if moment and moment > now:
            prerender_page.using(run_after=moment).enqueue(
                tournament.get_absolute_url()
            )
            prerender_page.using(run_after=moment).enqueue("/tournaments/")


def _submit_moderation(tournament, actor) -> None:
    from moderation import services as moderation_services

    try:
        moderation_services.submit(
            target_type="tournament_description",
            target_id=tournament.pk,
            field="description",
            text=tournament.description,
            url=tournament.get_absolute_url(),
            author=actor if getattr(actor, "pk", None) else tournament.created_by,
        )
    except Exception:  # noqa: BLE001 — review must never block an admin action
        logger.warning("赛事说明送审失败 #%s", tournament.pk, exc_info=True)


TOURNAMENT_PERMISSIONS = (
    "add_tournament",
    "change_tournament",
    "delete_tournament",
    "view_tournament",
)
MANAGER_GROUP = "赛事管理员"


def assign_tournament_permissions() -> list[str]:
    """Tournament managers get the tournament model permissions (design 4.1)."""
    from django.contrib.auth.models import Group, Permission

    permissions = list(
        Permission.objects.filter(
            content_type__app_label="tournaments",
            codename__in=TOURNAMENT_PERMISSIONS,
        )
    )
    granted = []
    group = Group.objects.filter(name=MANAGER_GROUP).first()
    if group is not None and permissions:
        group.permissions.add(*permissions)
        granted.append(group.name)
    return granted
