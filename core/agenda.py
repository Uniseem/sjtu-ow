"""「我的安排」 on the homepage (design 5.2, v6.48): what a signed-in member
has signed up for and is still to come, earliest first.

The homepage is prerendered for everyone, so this is a personalised slot
(design 13.13.3): empty on the static page, filled for a signed-in visitor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.template.loader import render_to_string
from django.utils import timezone

MAX_ITEMS = 4
# A scrim stays on the list while it is being played (it finishes six hours
# in, design 9.1).
SCRIM_GRACE = timedelta(hours=6)


@dataclass(frozen=True)
class Item:
    kind: str  # 赛事 / 内战
    title: str
    url: str
    when: datetime | None
    note: str


def items_for(user, now=None) -> list[Item]:
    from scrims.models import ScrimSignup, ScrimStatus
    from scrims.services import placement, split_scrim_ids
    from tournaments.models import (
        IndividualSignup,
        RegistrationMember,
        TournamentStatus,
    )

    if not getattr(user, "is_authenticated", False):
        return []
    now = now or timezone.now()
    items = []

    signups = list(
        ScrimSignup.objects.filter(
            user=user,
            scrim__status=ScrimStatus.PUBLISHED,
            scrim__starts_at__gte=now - SCRIM_GRACE,
        ).select_related("scrim")
    )
    split = split_scrim_ids([signup.scrim_id for signup in signups])
    for signup in signups:
        place = placement(signup, has_split=signup.scrim_id in split)
        items.append(
            Item(
                "内战",
                signup.scrim.title,
                f"/scrims/{signup.scrim_id}/",
                signup.scrim.starts_at,
                place or "已报名",
            )
        )

    def upcoming(tournament) -> bool:
        return tournament.starts_at is None or tournament.starts_at >= now

    for row in RegistrationMember.objects.filter(
        user=user,
        is_active=True,
        tournament__status=TournamentStatus.PUBLISHED,
    ).select_related("registration", "tournament"):
        if upcoming(row.tournament):
            registration = row.registration
            items.append(
                Item(
                    "赛事",
                    row.tournament.title,
                    registration.get_absolute_url(),
                    row.tournament.starts_at,
                    f"{registration.team_name} · {registration.get_status_display()}",
                )
            )
    for signup in IndividualSignup.objects.filter(
        user=user,
        registration__isnull=True,
        tournament__status=TournamentStatus.PUBLISHED,
    ).select_related("tournament"):
        if upcoming(signup.tournament):
            items.append(
                Item(
                    "赛事",
                    signup.tournament.title,
                    signup.tournament.get_absolute_url(),
                    signup.tournament.starts_at,
                    "等待编队",
                )
            )

    # Dated ones by time, then those without a start time.
    items.sort(key=lambda item: (item.when is None, item.when or now))
    return items[:MAX_ITEMS]


def agenda_context(request) -> dict:
    return {"agenda_items": items_for(getattr(request, "user", None))}


def my_agenda_slot(request, argument):
    context = agenda_context(request)
    context["oob"] = True
    return render_to_string("slots/agenda.html", context, request=request)
