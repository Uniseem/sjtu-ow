"""Site-wide business logic.

So far: 「通知全体成员」, the activity notices (design 10.4, v6.19), and how
far a copied scrim or tournament moves (14.2, v6.51). Email itself lives in
core.mail and core.letters, prerendering in core.prerender.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core import signing
from django.db import IntegrityError, transaction
from django.urls import reverse

UNSUBSCRIBE_SALT = "core.announcements.unsubscribe"


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
        ),
        Broadcast.Kind.SCRIM: Kind(
            Broadcast.Kind.SCRIM,
            scrim_mail.new_scrim_letter,
            scrim_services.can_manage,
            Scrim,
            _published,
            lambda obj: reverse("scrims:index"),
            "内战活动",
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


def sent_broadcast(kind: str, obj):
    from core.models import Broadcast

    return Broadcast.objects.filter(kind=kind, object_id=obj.pk).first()


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


def announcement_problem(kind: str, obj, *, publishing: bool = False) -> str:
    """Why this cannot go out now; "" when it can. ``publishing``: asked
    on the publish page, before the status changes. A planned article can be
    announced ahead: it goes out when it goes live (v6.54)."""
    from core.mail import SMTPNotConfigured, build_smtp_backend
    from core.models import SiteSettings

    if (
        not publishing
        and not kinds()[kind].is_live(obj)
        and going_live_at(kind, obj) is None
    ):
        return "发布之后才能通知全体成员。"
    done = sent_broadcast(kind, obj)
    if done is not None and done.waits_for_publish:
        return "已经安排在上线时通知全体成员，同一篇只发一次。"
    if done is not None:
        return (
            f"已经在 {_moment(done.created_at)} 通知过 {done.recipient_count} 人，"
            "同一场只发一次。"
        )
    try:
        build_smtp_backend(SiteSettings.load())
    except SMTPNotConfigured:
        return "还没有配置邮件（全站设置里的 SMTP），发不出去。"
    return ""


def recipient_count(obj) -> int:
    return announcement_recipients(sjtu_only=getattr(obj, "sjtu_only", False)).count()


@transaction.atomic
def announce(*, kind: str, obj, actor):
    """Record the notice and queue it (design 10.4). One per object."""
    from core import admin_log
    from core.models import Broadcast
    from core.tasks import send_broadcast

    entry = kinds()[kind]
    if not entry.can_send(actor):
        raise AnnouncementError("你没有这类活动的管理权限。")
    problem = announcement_problem(kind, obj)
    if problem:
        raise AnnouncementError(problem)
    # A planned article: noted now, sent by send_waiting() when it goes live.
    waiting = going_live_at(kind, obj) is not None
    try:
        with transaction.atomic():
            broadcast = Broadcast.objects.create(
                kind=kind,
                object_id=obj.pk,
                subject=entry.letter(obj, "").subject,
                sent_by=actor,
                recipient_count=0 if waiting else recipient_count(obj),
                waits_for_publish=waiting,
            )
    except IntegrityError as exc:  # someone else pressed it a moment ago
        raise AnnouncementError("刚刚已经有人发过了，同一场只发一次。") from exc
    admin_log.record(
        obj,
        f"{kind}s.announce",
        actor,
        recipients=broadcast.recipient_count,
        on_publish=waiting,
    )
    if not waiting:
        transaction.on_commit(lambda: send_broadcast.enqueue(broadcast.pk))
    return broadcast


def send_waiting(kind: str, obj) -> bool:
    """The article just went live (design 10.4, v6.54): send what was planned
    for this moment, to whoever has the notices on now."""
    from core.models import Broadcast
    from core.tasks import send_broadcast

    waiting = Broadcast.objects.filter(
        kind=kind, object_id=obj.pk, waits_for_publish=True
    )
    if not waiting.update(
        waits_for_publish=False, recipient_count=recipient_count(obj)
    ):
        return False
    broadcast = Broadcast.objects.get(kind=kind, object_id=obj.pk)
    transaction.on_commit(lambda: send_broadcast.enqueue(broadcast.pk))
    return True


def deliver(broadcast) -> int:
    """The worker's half: one letter per member, each with their own
    unsubscribe link. People who turned the notices off since are skipped."""
    from core.letters import send

    entry = kinds()[broadcast.kind]
    obj = entry.model.objects.filter(pk=broadcast.object_id).first()
    if obj is None:
        return 0
    sent = 0
    for person in announcement_recipients(sjtu_only=getattr(obj, "sjtu_only", False)):
        sent += send(
            entry.letter(obj, unsubscribe_url(person)), [person], fail_silently=True
        )
    return sent


def _moment(value) -> str:
    from django.utils.timezone import localtime

    return f"{localtime(value):%Y-%m-%d %H:%M}"


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
