"""Site-wide business logic.

So far: 「通知全体成员」 and 「通知报名的人」, the mails people send about a
tournament, scrim or article (design 10.4, v6.19; v7.5), and how far a copied
scrim or tournament moves (14.2, v6.51). Email itself lives in
core.mail and core.letters, prerendering in core.prerender.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core import signing
from django.db import transaction
from django.urls import reverse

UNSUBSCRIBE_SALT = "core.announcements.unsubscribe"
EVERYONE = "everyone"
PARTICIPANTS = "participants"
NOTE_MAX = 500


class AnnouncementError(Exception):
    pass


@dataclass(frozen=True)
class Kind:
    """What can be announced and how: the letter, who may send it, and
    whether only SJTU members are told."""

    key: str
    letter: object  # (obj, unsubscribe_url) -> Letter
    can_send: object  # (user) -> bool
    model: object
    is_live: object  # (obj) -> bool
    back_url: object  # (obj) -> admin address to return to
    label: str  # for the breadcrumb
    noun: str  # 「这场赛事」, in the notice from the second mail on (10.3)
    # 「通知报名的人」 (v7.5): who signed up, and their letter
    # (obj, moved_from, note) -> Letter. None where nobody signs up.
    participants: object = None
    update_letter: object = None


def _published(obj) -> bool:
    return getattr(obj, "status", "") == "published"


def kinds() -> dict[str, Kind]:
    from content import notifications as article_mail
    from content.models import ArticlePage
    from content.permissions import user_can_edit_author
    from core.models import Broadcast
    from scrims import notifications as scrim_mail
    from scrims import services as scrim_services
    from scrims.models import Scrim
    from tournaments import notifications as tournament_mail
    from tournaments import services as tournament_services
    from tournaments.models import Tournament

    return {
        Broadcast.Kind.TOURNAMENT: Kind(
            Broadcast.Kind.TOURNAMENT,
            tournament_mail.new_tournament_letter,
            tournament_services.can_manage,
            Tournament,
            _published,
            lambda obj: reverse("tournaments:index"),
            "赛事",
            "这场赛事",
            tournament_mail.participants,
            tournament_mail.update_letter,
        ),
        Broadcast.Kind.SCRIM: Kind(
            Broadcast.Kind.SCRIM,
            scrim_mail.new_scrim_letter,
            scrim_services.can_manage,
            Scrim,
            _published,
            lambda obj: reverse("scrims:index"),
            "内战活动",
            "这场内战",
            scrim_mail.participants,
            scrim_mail.scrim_update_letter,
        ),
        # Design 10.4 (v6.23): content editors announce a published article.
        Broadcast.Kind.ARTICLE: Kind(
            Broadcast.Kind.ARTICLE,
            article_mail.new_article_letter,
            user_can_edit_author,
            ArticlePage,
            lambda obj: bool(obj.live),
            lambda obj: reverse("backoffice:articles"),
            "文章",
            "这篇文章",
        ),
    }


# --- who gets it, and how they stop it --------------------------------------


def announcement_recipients(*, sjtu_only: bool = False):
    """Active members with a verified address who left the notices on."""
    from accounts.models import User

    people = User.objects.filter(
        is_active=True,
        accepts_announcements=True,
        emailaddress__verified=True,
        emailaddress__primary=True,
    )
    if sjtu_only:
        people = people.filter(is_sjtu=True)
    return people.distinct().order_by("pk")


def unsubscribe_token(user) -> str:
    return signing.dumps(user.pk, salt=UNSUBSCRIBE_SALT)


def user_for_token(token: str):
    """The member a link was made for, or None if it was tampered with."""
    from accounts.models import User

    try:
        pk = signing.loads(token, salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=pk, is_active=True).first()


def unsubscribe_url(user) -> str:
    from core.letters import site_url

    return site_url(
        reverse("announcements_unsubscribe", args=[unsubscribe_token(user)])
    )


def set_announcements(user, accepts: bool) -> None:
    if user.accepts_announcements != accepts:
        user.accepts_announcements = accepts
        user.save(update_fields=["accepts_announcements"])


# --- sending ----------------------------------------------------------------


def history(kind: str, obj):
    """Every mail sent (or planned) about this one, newest first (v7.5)."""
    from core.models import Broadcast

    return Broadcast.objects.filter(kind=kind, object_id=obj.pk).order_by(
        "-created_at", "-pk"
    )


def waiting_broadcast(kind: str, obj):
    """The one planned for when this article goes live, if any (v6.54)."""
    return history(kind, obj).filter(waits_for_publish=True).first()


def repeat_notice(kind: str, obj, before: int) -> str:
    """Design 10.3 (v7.5): from the second mail about the same thing on,
    say how many went before; things may have changed since."""
    if before <= 0:
        return ""
    return (
        f"关于{kinds()[kind].noun}「{obj.title}」，之前已经发过 {before} 次邮件，"
        "这次可能有修改，请以这封为准。"
    )


def compose(
    kind: str,
    obj,
    *,
    audience: str = EVERYONE,
    unsubscribe: str = "",
    moved_from=None,
    note: str = "",
    before: int = 0,
):
    """The letter one mail of this kind is, with the notice on top."""
    entry = kinds()[kind]
    if audience == PARTICIPANTS:
        letter = entry.update_letter(obj, moved_from, note)
    else:
        letter = entry.letter(obj, unsubscribe)
    letter.notice = repeat_notice(kind, obj, before)
    return letter


def participant_count(kind: str, obj) -> int:
    entry = kinds()[kind]
    return len(entry.participants(obj)) if entry.participants else 0


def going_live_at(kind: str, obj):
    """When an article planned under 「设置计划」 goes live (design 10.4,
    v6.54); None if it is live already, not planned, or not an article."""
    from core.models import Broadcast

    if kind != Broadcast.Kind.ARTICLE or obj.live:
        return None
    planned = (
        obj.revisions.filter(approved_go_live_at__isnull=False)
        .order_by("-approved_go_live_at")
        .first()
    )
    return planned.approved_go_live_at if planned else None


def announcement_problem(
    kind: str, obj, *, publishing: bool = False, audience: str = EVERYONE
) -> str:
    """Why this cannot go out now; "" when it can. ``publishing``: asked
    on the publish page, before the status changes. A planned article can be
    announced ahead: it goes out when it goes live (v6.54). v7.5: the same
    one may go out again; only a second plan for going live is refused."""
    from core.mail import SMTPNotConfigured, build_smtp_backend
    from core.models import SiteSettings

    entry = kinds()[kind]
    if audience == PARTICIPANTS:
        if entry.participants is None:
            return "这类内容没有报名的人。"
        if not publishing and not entry.is_live(obj):
            return "发布之后才能通知报名的人。"
        if not entry.participants(obj):
            return "还没有人报名，没有人可以通知。"
    else:
        if (
            not publishing
            and not entry.is_live(obj)
            and going_live_at(kind, obj) is None
        ):
            return "发布之后才能通知全体成员。"
        if waiting_broadcast(kind, obj) is not None:
            return "已经安排在上线时通知全体成员，到时会发出，不用再安排。"
    try:
        build_smtp_backend(SiteSettings.load())
    except SMTPNotConfigured:
        return "还没有配置邮件（全站设置里的 SMTP），发不出去。"
    return ""


def recipient_count(obj) -> int:
    return announcement_recipients(sjtu_only=getattr(obj, "sjtu_only", False)).count()


@transaction.atomic
def announce(*, kind: str, obj, actor, audience: str = EVERYONE, note: str = ""):
    """Record the mail and queue it (design 10.4). v7.5: to everyone or to
    the people signed up, as often as someone sends it; each knows how many
    went before it, and a notice to the people signed up carries the
    admin's words and the start time they knew until now."""
    from core import admin_log
    from core.models import Broadcast
    from core.tasks import send_broadcast

    entry = kinds()[kind]
    if not entry.can_send(actor):
        raise AnnouncementError("你没有这类活动的管理权限。")
    note = (note or "").strip() if audience == PARTICIPANTS else ""
    if len(note) > NOTE_MAX:
        raise AnnouncementError(f"说明最多 {NOTE_MAX} 字。")
    problem = announcement_problem(kind, obj, audience=audience)
    if problem:
        raise AnnouncementError(problem)
    # A planned article: noted now, sent by send_waiting() when it goes live.
    waiting = audience == EVERYONE and going_live_at(kind, obj) is not None
    moved_from = getattr(obj, "moved_from", None) if audience == PARTICIPANTS else None
    if waiting:
        count = 0
    elif audience == PARTICIPANTS:
        count = participant_count(kind, obj)
    else:
        count = recipient_count(obj)
    broadcast = Broadcast.objects.create(
        kind=kind,
        object_id=obj.pk,
        audience=audience,
        before=history(kind, obj).count(),
        note=note,
        moved_from=moved_from,
        subject=compose(
            kind, obj, audience=audience, moved_from=moved_from, note=note
        ).subject,
        sent_by=actor,
        recipient_count=count,
        waits_for_publish=waiting,
    )
    if moved_from is not None:
        # They are being told now (design 8.1, 9.1): the prompt goes.
        entry.model.objects.filter(pk=obj.pk).update(moved_from=None)
        obj.moved_from = None
    action = "announce" if audience == EVERYONE else "notify_participants"
    admin_log.record(
        obj,
        f"{kind}s.{action}",
        actor,
        recipients=count,
        on_publish=waiting,
        before=broadcast.before,
    )
    if not waiting:
        transaction.on_commit(lambda: send_broadcast.enqueue(broadcast.pk))
    return broadcast


def send_waiting(kind: str, obj) -> bool:
    """The article just went live (design 10.4, v6.54): send what was planned
    for this moment, to whoever has the notices on now."""
    from core.models import Broadcast
    from core.tasks import send_broadcast

    sent = False
    for broadcast in Broadcast.objects.filter(
        kind=kind, object_id=obj.pk, waits_for_publish=True
    ):
        # The update is the claim: a second signal finds nothing left to send.
        if Broadcast.objects.filter(pk=broadcast.pk, waits_for_publish=True).update(
            waits_for_publish=False, recipient_count=recipient_count(obj)
        ):
            transaction.on_commit(lambda pk=broadcast.pk: send_broadcast.enqueue(pk))
            sent = True
    return sent


def deliver(broadcast) -> int:
    """The worker's half: one letter per member, each with their own
    unsubscribe link. People who turned the notices off since are skipped."""
    from core.letters import send

    entry = kinds()[broadcast.kind]
    obj = entry.model.objects.filter(pk=broadcast.object_id).first()
    if obj is None:
        return 0
    if broadcast.audience == PARTICIPANTS:
        letter = compose(
            broadcast.kind,
            obj,
            audience=PARTICIPANTS,
            moved_from=broadcast.moved_from,
            note=broadcast.note,
            before=broadcast.before,
        )
        people = entry.participants(obj) if entry.participants else []
        return send(letter, people, fail_silently=True)
    sent = 0
    for person in announcement_recipients(sjtu_only=getattr(obj, "sjtu_only", False)):
        letter = compose(
            broadcast.kind,
            obj,
            unsubscribe=unsubscribe_url(person),
            before=broadcast.before,
        )
        sent += send(letter, [person], fail_silently=True)
    return sent


WEEK = timedelta(weeks=1)


def weeks_ahead(times, now=None) -> int:
    """「复制」 a scrim or tournament (design 14.2, v6.51): how many whole weeks
    its times move so the earliest lies ahead. At least one, so a weekly scrim
    copied before it is played lands on the week after."""
    from django.utils import timezone

    filled = [moment for moment in times if moment is not None]
    if not filled:
        return 1
    now = now or timezone.now()
    earliest = min(filled)
    if earliest + WEEK > now:
        return 1
    return (now - earliest) // WEEK + 1


def copy_ahead(original, copied, times, now=None):
    """A new, unsaved instance of ``original``'s model holding only its
    ``copied`` fields and its ``times`` moved whole weeks ahead."""
    shift = WEEK * weeks_ahead([getattr(original, name) for name in times], now)
    values = {name: getattr(original, name) for name in copied}
    for name in times:
        moment = getattr(original, name)
        values[name] = moment + shift if moment is not None else None
    return type(original)(**values)
