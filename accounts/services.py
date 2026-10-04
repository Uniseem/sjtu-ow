"""Account helpers: groups, profile completeness, game IDs, uploaded faces."""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError

from accounts.models import (
    AvatarSubmission,
    ContactMethod,
    Feature,
    FeatureUserRule,
    GameAccount,
    User,
)
from accounts.permissions import can_use, feature_denied_message
from accounts.ranks import format_rank

GROUP_SJTU = "交大用户"
GROUP_EXTERNAL = "校外用户"
GROUP_CONTENT = "内容编辑"
GROUP_TOURNAMENT = "赛事管理员"
GROUP_SCRIM = "内战管理员"
GROUP_AUTHOR = "认证作者"
GROUP_SUBMITTER = "投稿者"

STAFF_GROUPS = (
    GROUP_CONTENT,
    GROUP_TOURNAMENT,
    GROUP_SCRIM,
    GROUP_AUTHOR,
    GROUP_SUBMITTER,
)
ALL_PRESET_GROUPS = (GROUP_SJTU, GROUP_EXTERNAL, *STAFF_GROUPS)
CONTACT_VIEW_GROUPS = (GROUP_TOURNAMENT, GROUP_SCRIM)


def ensure_user_groups() -> tuple[Group, Group]:
    """Create the two automatic groups if they are missing."""
    sjtu, _ = Group.objects.get_or_create(name=GROUP_SJTU)
    external, _ = Group.objects.get_or_create(name=GROUP_EXTERNAL)
    return sjtu, external


def ensure_preset_groups() -> dict[str, Group]:
    """Create every preset group. Does not change membership."""
    groups = {}
    for name in ALL_PRESET_GROUPS:
        groups[name], _ = Group.objects.get_or_create(name=name)
    return groups


def sync_sjtu_groups(user) -> None:
    """Assign 交大用户 or 校外用户 from is_sjtu; leave other groups alone."""
    if user.pk is None:
        return
    sjtu, external = ensure_user_groups()
    if user.is_sjtu:
        user.groups.add(sjtu)
        user.groups.remove(external)
    else:
        user.groups.add(external)
        user.groups.remove(sjtu)


def max_game_accounts() -> int:
    from core.models import SiteSettings

    site = SiteSettings.load()
    return int(site.max_game_accounts or 5)


def profile_gaps(user: User) -> list[tuple[str, str, str]]:
    """Return missing profile items as (label, url_name, hint)."""
    gaps = []
    if not user.game_accounts.exists():
        gaps.append(("游戏 ID", "me_game_accounts", "至少绑定 1 个游戏 ID"))
    if not user.contact_methods.exists():
        gaps.append(("联系方式", "me_contacts", "至少填写 1 种联系方式"))
    return gaps


def profile_is_complete(user: User) -> bool:
    return not profile_gaps(user)


def deletion_blocked_reason(account: GameAccount) -> str | None:
    """Return a user-facing reason, or None if the game ID may be deleted.

    Design 9.2: a signup points at the game ID it was made with, so the ID
    cannot go while an unfinished scrim still uses it — cancel the signup
    first. Tournament roster snapshots (M4) hold copies, not references.
    """
    from scrims.models import ScrimStatus

    signup = (
        account.scrim_signups.filter(
            scrim__status__in=[ScrimStatus.DRAFT, ScrimStatus.PUBLISHED]
        )
        .select_related("scrim")
        .first()
    )
    if signup is not None:
        return (
            f"这个游戏 ID 正用于内战「{signup.scrim.title}」的报名，"
            f"请先取消报名再删除。"
        )
    from tournaments.models import TournamentStatus

    entry = (
        account.individual_signups.filter(
            tournament__status__in=[TournamentStatus.DRAFT, TournamentStatus.PUBLISHED]
        )
        .select_related("tournament")
        .first()
    )
    if entry is not None:
        return (
            f"这个游戏 ID 正用于赛事「{entry.tournament.title}」的个人报名，"
            f"请先取消报名再删除。"
        )
    return None


def add_game_account(user: User, **fields) -> GameAccount:
    if user.game_accounts.count() >= max_game_accounts():
        raise ValidationError(f"每人最多绑定 {max_game_accounts()} 个游戏 ID。")
    account = GameAccount(user=user, **fields)
    account.full_clean()
    account.save()
    return account


def add_contact_method(user: User, **fields) -> ContactMethod:
    contact = ContactMethod(user=user, **fields)
    contact.full_clean()
    contact.save()
    return contact


def assign_round_permissions() -> None:
    """Attach permissions this milestone can actually grant. Idempotent."""
    groups = ensure_preset_groups()
    access_admin = Permission.objects.get(
        content_type__app_label="wagtailadmin",
        codename="access_admin",
    )
    view_contact = Permission.objects.get(
        content_type__app_label="accounts",
        codename="view_contactmethod",
    )
    for name in STAFF_GROUPS:
        groups[name].permissions.add(access_admin)
    for name in CONTACT_VIEW_GROUPS:
        groups[name].permissions.add(view_contact)


def email_is_verified(user) -> bool:
    if user is None or not getattr(user, "pk", None):
        return False
    from allauth.account.models import EmailAddress

    return EmailAddress.objects.filter(user=user, verified=True).exists()


def user_should_be_submitter(user) -> bool:
    if user is None or not getattr(user, "pk", None):
        return False
    if not user.is_active:
        return False
    if not email_is_verified(user):
        return False
    return can_use(user, Feature.ARTICLE_SUBMIT)


def sync_submitter_group(user) -> bool:
    """Add or remove 「投稿者」 to match 5.4.2. Returns whether the user is in it."""
    if user is None or not getattr(user, "pk", None):
        return False
    group, _ = Group.objects.get_or_create(name=GROUP_SUBMITTER)
    should = user_should_be_submitter(user)
    in_group = user.groups.filter(pk=group.pk).exists()
    if should and not in_group:
        user.groups.add(group)
        return True
    if not should and in_group:
        user.groups.remove(group)
        return False
    return should


def sync_submitters_for_users(users) -> None:
    for user in users:
        sync_submitter_group(user)


def sync_submitters_for_group(group: Group) -> None:
    sync_submitters_for_users(group.user_set.all())


def sync_all_submitter_memberships() -> int:
    """Recompute 投稿者 for verified users and anyone already in the group."""
    from allauth.account.models import EmailAddress

    group, _ = Group.objects.get_or_create(name=GROUP_SUBMITTER)
    ids = set(group.user_set.values_list("pk", flat=True))
    ids.update(
        EmailAddress.objects.filter(verified=True).values_list("user_id", flat=True)
    )
    changed = 0
    for user in User.objects.filter(pk__in=ids):
        before = user.groups.filter(pk=group.pk).exists()
        after = sync_submitter_group(user)
        if before != after:
            changed += 1
    return changed


def with_avatars(queryset, path: str = ""):
    """Load each person's picture and its thumbnails with the rows
    (design-details 2.3). `path` leads from the rows to the user, such as
    "author__"; without this a list of faces costs queries per face."""
    return queryset.select_related(f"{path}avatar").prefetch_related(
        f"{path}avatar__renditions"
    )


def refresh_nickname_pages(user) -> None:
    """Regenerate the public pages that print this user's nickname (13.13.4)."""
    from content.models import ArticlePage
    from core import prerender

    for membership in user.team_memberships.select_related("team"):
        if not membership.team.is_disbanded:
            prerender.request_page(membership.team.get_absolute_url(), kind="team")
    # Former members are listed too (design-details 5.3), face and all.
    for alumnus in user.team_alumni.select_related("team"):
        if not alumnus.team.is_disbanded:
            prerender.request_page(alumnus.team.get_absolute_url(), kind="team")
    for signup in user.scrim_signups.select_related("scrim"):
        if signup.scrim.is_public:
            prerender.request_page(f"/scrims/{signup.scrim_id}/", kind="scrim")
    for entry in user.individual_signups.select_related("tournament"):
        if entry.tournament.is_listed:  # the pool prints live nicknames (8.8.1)
            prerender.request_page(
                entry.tournament.get_absolute_url(), kind="tournament"
            )
    from django.db.models import Q

    commented = (
        Q(author=user) | Q(comments__author=user) | Q(comments__reply_to_user=user)
    )
    for article in ArticlePage.objects.live().public().filter(commented).distinct():
        url = article.get_url()
        if url:
            prerender.request_page(url, kind="article")
    # Article cards on the homepage and the listings carry the byline (v6.2).
    if ArticlePage.objects.live().public().filter(author=user).exists():
        from content.signals import refresh_listings

        refresh_listings("article")
    prerender.request_page("/members/", kind="members")


DELETED_NICKNAME = "已注销用户"
DELETED_NOTE = "用户自行注销"


class AccountDeletionError(Exception):
    """Why the account cannot be deleted right now; shown to the user."""


def deletion_blockers(user) -> list[str]:
    """A captain must hand over or disband first (design 3.8, 7.4)."""
    from teams.models import TeamMembership, TeamRole

    captained = TeamMembership.objects.filter(
        user=user, role=TeamRole.CAPTAIN, team__disbanded_at__isnull=True
    ).select_related("team")
    return [
        f"你是战队「{membership.team.name}」的队长，请先转让队长或解散战队。"
        for membership in captained
    ]


def _leave_adhoc_teams(user) -> None:
    """Design 3.8 + 8.8.2: a placed player leaves their ad-hoc teams first."""
    from tournaments.models import ACTIVE_STATUSES, TournamentStatus
    from tournaments.registration import leave

    entries = user.individual_signups.filter(
        registration__isnull=False,
        registration__status__in=ACTIVE_STATUSES,
        registration__tournament__status__in=[
            TournamentStatus.DRAFT,
            TournamentStatus.PUBLISHED,
        ],
    ).select_related("registration__tournament")
    for entry in entries:
        leave(registration=entry.registration, user=user, enforce_deadline=False)


# What deleting an account does with every column that points at a person
# (round 173). A test lists the columns again: a new one must be decided here.
KEPT_ACTION = "保留：操作人记录，名字显示「已注销用户」"
KEPT_PAGE = "保留：Wagtail 页面的所有者和锁定人"
ON_DELETION = {
    "accounts.AvatarSubmission.user": "删除，连图片（forget_uploaded_faces）",
    "accounts.AvatarSubmission.reviewed_by": KEPT_ACTION,
    "accounts.ContactMethod.user": "删除",
    "accounts.FeatureGroupRestriction.updated_by": KEPT_ACTION,
    "accounts.FeatureUserRule.user": "删除",
    "accounts.FeatureUserRule.updated_by": KEPT_ACTION,
    "accounts.GameAccount.user": "删除（报名先撤掉，报名引用它）",
    "comments.Comment.author": "保留，署名显示「已注销用户」，和文章一样",
    "comments.Comment.reply_to_user": "保留，显示「@已注销用户」",
    "comments.CommentLike.user": "保留，只算在赞数里",
    "content.ArticleIndexPage.locked_by": KEPT_PAGE,
    "content.ArticleIndexPage.owner": KEPT_PAGE,
    "content.ArticlePage.author": "保留，署名显示「已注销用户」（3.8）",
    "content.ArticlePage.locked_by": KEPT_PAGE,
    "content.ArticlePage.owner": KEPT_PAGE,
    "content.HomePage.locked_by": KEPT_PAGE,
    "content.HomePage.owner": KEPT_PAGE,
    "content.StandardPage.locked_by": KEPT_PAGE,
    "content.StandardPage.owner": KEPT_PAGE,
    "core.Broadcast.sent_by": KEPT_ACTION,
    "core.FontFamily.created_by": KEPT_ACTION,
    "members.MemberGroupMembership.user": "删除",
    "moderation.ModerationItem.author": "昵称、宣言的送审记录删除，其余跟着内容保留",
    "moderation.ModerationItem.reviewed_by": KEPT_ACTION,
    "scrims.Scrim.created_by": KEPT_ACTION,
    "scrims.ScrimSignup.user": "删除（remove_signups_of）",
    "teams.TeamAlumnus.user": "保留，退役记录显示「已注销用户」",
    "teams.TeamApplication.applicant": "等待中的撤回（leave_all_teams），处理过的保留",
    "teams.TeamApplication.decided_by": KEPT_ACTION,
    "teams.TeamMembership.user": "删除（leave_all_teams；队长要先转让或解散）",
    "tournaments.IndividualSignup.user": "删除，临时队伍先退出（_leave_adhoc_teams）",
    "tournaments.Registration.submitted_by": KEPT_ACTION,
    "tournaments.RegistrationMember.user": "保留：名单快照（3.8）",
    "tournaments.RegistrationStatusLog.actor_user": KEPT_ACTION,
    "tournaments.Tournament.created_by": KEPT_ACTION,
}


def delete_account(user) -> None:
    """Anonymise the account in place (design 3.8). Users are never deleted.

    Registration roster snapshots and their logs stay: they record what was
    submitted. Articles stay and show the new nickname.
    """
    from allauth.account.models import EmailAddress
    from django.db import transaction

    from members.models import MemberGroupMembership
    from moderation.models import ModerationItem, TargetType
    from scrims.services import remove_signups_of
    from teams.services import leave_all_teams

    blockers = deletion_blockers(user)
    if blockers:
        raise AccountDeletionError(blockers[0])
    with transaction.atomic():
        remove_signups_of(user)  # before game IDs: signups PROTECT them
        _leave_adhoc_teams(user)  # design 8.8.2: free the places first
        user.individual_signups.all().delete()  # design 8.8.1, same reason
        leave_all_teams(user)
        user.game_accounts.all().delete()
        MemberGroupMembership.objects.filter(user=user).delete()  # design 3.8
        user.contact_methods.all().delete()
        EmailAddress.objects.filter(user=user).delete()
        FeatureUserRule.objects.filter(user=user).delete()
        user.email = f"deleted-{user.pk}@deleted.invalid"
        user.nickname = DELETED_NICKNAME
        user.avatar = None  # design-details 2.3
        # Public profile (design 3.8, v6.2): the author card still shows it.
        user.motto = ""
        user.main_role = ""
        user.flex_roles = ""
        user.is_sjtu = False
        user.sjtu_verified_via = None
        user.sjtu_verified_at = None
        user.is_active = False
        user.is_staff = False
        user.deactivation_note = DELETED_NOTE
        user.set_unusable_password()
        user.save()
        forget_uploaded_faces(user)  # design 3.8, v6.11
        # After the save: its signal puts everyone back in 交大用户 / 校外用户.
        user.groups.clear()
        # The review queue keeps a copy of each nickname and motto it checked,
        # including the nickname the save above just sent.
        ModerationItem.objects.filter(
            target_type__in=[TargetType.NICKNAME, TargetType.MOTTO],
            target_id=user.pk,
        ).delete()


# Every column that points at a person, and where 「导出个人信息」 puts it
# (round 172; comments, likes and feature rules had been left out since 072).
# A test lists the columns again: a new one must be added to one of the two.
EXPORTED = {
    "accounts.AvatarSubmission.user": "avatar_uploads",
    "accounts.ContactMethod.user": "contact_methods",
    "accounts.FeatureUserRule.user": "feature_rules",
    "accounts.GameAccount.user": "game_accounts",
    "comments.Comment.author": "comments",
    "comments.CommentLike.user": "comment_likes",
    "content.ArticlePage.author": "articles",
    "members.MemberGroupMembership.user": "member_groups",
    "scrims.ScrimSignup.user": "scrim_signups",
    "teams.TeamAlumnus.user": "team_alumni",
    "teams.TeamApplication.applicant": "team_applications",
    "teams.TeamMembership.user": "teams",
    "tournaments.IndividualSignup.user": "individual_signups",
    "tournaments.RegistrationMember.user": "tournament_registrations",
}
STAFF_ACTION = "记的是谁做了这个操作（管理员、队长），不是关于这个人的资料"
WAGTAIL_PAGE = "Wagtail 内部的页面所有者和锁定人；文章按作者导出"
NOT_EXPORTED = {
    "accounts.AvatarSubmission.reviewed_by": STAFF_ACTION,
    "accounts.FeatureGroupRestriction.updated_by": STAFF_ACTION,
    "accounts.FeatureUserRule.updated_by": STAFF_ACTION,
    "comments.Comment.reply_to_user": "别人回复这个人的评论，是别人写的内容",
    "content.ArticleIndexPage.locked_by": WAGTAIL_PAGE,
    "content.ArticleIndexPage.owner": WAGTAIL_PAGE,
    "content.ArticlePage.locked_by": WAGTAIL_PAGE,
    "content.ArticlePage.owner": WAGTAIL_PAGE,
    "content.HomePage.locked_by": WAGTAIL_PAGE,
    "content.HomePage.owner": WAGTAIL_PAGE,
    "content.StandardPage.locked_by": WAGTAIL_PAGE,
    "content.StandardPage.owner": WAGTAIL_PAGE,
    "core.Broadcast.sent_by": STAFF_ACTION,
    "core.FontFamily.created_by": STAFF_ACTION,
    "moderation.ModerationItem.author": (
        "AI 审核的内部复核记录（设计 5.5）；"
        "送审的内容本身在昵称、宣言、文章、评论里已导出"
    ),
    "moderation.ModerationItem.reviewed_by": STAFF_ACTION,
    "scrims.Scrim.created_by": STAFF_ACTION,
    "teams.TeamApplication.decided_by": STAFF_ACTION,
    "tournaments.Registration.submitted_by": (
        STAFF_ACTION + "；本人在名单里的那条按 tournament_registrations 导出"
    ),
    "tournaments.RegistrationStatusLog.actor_user": STAFF_ACTION,
    "tournaments.Tournament.created_by": STAFF_ACTION,
}


def personal_data(user) -> dict:
    """Everything the site holds about the user, for download (design 3.8).

    Only the user's own data: no teammates' contacts, no admin records.
    """
    from accounts.models import FeatureUserRule
    from accounts.roles import ROLE_LABELS, parse_roles
    from comments.models import Comment, CommentLike
    from content.models import ArticlePage
    from members.models import MemberGroupMembership
    from scrims.models import ScrimSignup
    from teams.models import TeamApplication, TeamMembership
    from tournaments.models import RegistrationMember

    def when(value):
        return value.isoformat() if value else None

    return {
        "account": {
            "email": user.email,
            "nickname": user.nickname,
            "is_sjtu": user.is_sjtu,
            "date_joined": when(user.date_joined),
            "agreed_terms_at": when(user.agreed_terms_at),
            "agreed_cross_border_at": when(user.agreed_cross_border_at),
            # design-details 3 (v5.2)
            "motto": user.motto,
            "main_role": ROLE_LABELS.get(user.main_role, ""),
            "flex_roles": [ROLE_LABELS[role] for role in parse_roles(user.flex_roles)],
            "show_rank": user.show_rank,
            "accepts_announcements": user.accepts_announcements,
        },
        "game_accounts": [
            {
                "battletag": account.battletag,
                "rank_tank": format_rank(account.rank_tank),
                "rank_damage": format_rank(account.rank_damage),
                "rank_support": format_rank(account.rank_support),
                "ranks_updated_at": when(account.ranks_updated_at),
            }
            for account in user.game_accounts.all()
        ],
        "contact_methods": [
            {"type": contact.get_type_display(), "value": contact.value}
            for contact in user.contact_methods.all()
        ],
        "teams": [
            {
                "team": membership.team.name,
                "role": membership.get_role_display(),
                "joined_at": when(membership.joined_at),
            }
            for membership in TeamMembership.objects.filter(user=user).select_related(
                "team"
            )
        ],
        # design 3.8 (v6.11): what happened to each picture, not who reviewed it
        "avatar_uploads": [
            {
                "status": upload.get_status_display(),
                "uploaded_at": when(upload.created_at),
                "reviewed_at": when(upload.reviewed_at),
                "reason": upload.get_reason_display() if upload.reason else "",
                "note": upload.note,
            }
            for upload in user.avatar_submissions.all()
        ],
        "team_alumni": [
            {
                "team": alumnus.team.name,
                "joined_at": when(alumnus.joined_at),
                "left_at": when(alumnus.left_at),
                "reason": alumnus.get_reason_display(),
            }
            for alumnus in user.team_alumni.select_related("team")
        ],
        "team_applications": [
            {
                "team": application.team.name,
                "status": application.get_status_display(),
                "message": application.message,
                "created_at": when(application.created_at),
            }
            for application in TeamApplication.objects.filter(
                applicant=user
            ).select_related("team")
        ],
        "tournament_registrations": [
            {
                "tournament": member.registration.tournament.title,
                "team": member.registration.team_name,
                "status": member.registration.get_status_display(),
                "nickname_snapshot": member.nickname,
                "battletag_snapshot": member.battletag,
            }
            for member in RegistrationMember.objects.filter(user=user).select_related(
                "registration__tournament"
            )
        ],
        "individual_signups": [
            {
                "tournament": entry.tournament.title,
                "battletag": entry.game_account.battletag
                if entry.game_account
                else "（游戏 ID 已删除）",
                "roles": entry.role_labels,
                "created_at": when(entry.created_at),
                "team": entry.registration.team_name if entry.registration else None,
            }
            for entry in user.individual_signups.select_related(
                "tournament", "game_account", "registration"
            )
        ],
        "scrim_signups": [
            {
                "scrim": signup.scrim.title,
                "starts_at": when(signup.scrim.starts_at),
                "battletag": signup.battletag,
                "roles": [
                    label
                    for field, label in (
                        ("role_tank", "坦克"),
                        ("role_damage", "输出"),
                        ("role_support", "支援"),
                    )
                    if getattr(signup, field)
                ],
            }
            for signup in ScrimSignup.objects.filter(user=user).select_related(
                "scrim", "game_account"
            )
        ],
        "member_groups": [
            {"group": membership.group.name, "title": membership.title}
            for membership in MemberGroupMembership.objects.filter(
                user=user
            ).select_related("group")
        ],
        "articles": [
            {"title": page.title, "url": page.get_url()}
            for page in ArticlePage.objects.filter(author=user)
        ],
        "comments": [
            {
                "article": comment.page.title,
                "body": comment.body,
                "created_at": when(comment.created_at),
                "edited_at": when(comment.edited_at),
                "state": "作者已删除"
                if comment.is_deleted
                else ("已隐藏" if comment.is_hidden else "公开"),
            }
            for comment in Comment.objects.filter(author=user)
            .select_related("page")
            .order_by("created_at")
        ],
        "comment_likes": [
            {"article": like.comment.page.title, "liked_at": when(like.created_at)}
            for like in CommentLike.objects.filter(user=user)
            .select_related("comment__page")
            .order_by("created_at")
        ],
        "feature_rules": [
            {
                "feature": rule.get_feature_display(),
                "allowed": rule.allowed,
                "reason": rule.note,
            }
            for rule in FeatureUserRule.objects.filter(user=user)
        ],
    }


# --- uploaded faces (design-details 2.3, v6.11) ------------------------------------

AVATAR_UPLOADS_PER_DAY = 5
DAY_SECONDS = 24 * 60 * 60


class AvatarUploadError(Exception):
    """Why an upload was refused; the message is for the person."""


class AvatarReviewError(Exception):
    """Why a review action cannot be done; the message is for the reviewer."""


def pending_avatar(user):
    """The picture this person is waiting on, if any."""
    return (
        user.avatar_submissions.filter(status=AvatarSubmission.Status.PENDING)
        .select_related("image")
        .first()
    )


def uploaded_face_ids(user) -> set[int]:
    """Pictures that came to this person through the upload: theirs to
    delete. Faces put on the demo by script are not among them."""
    return set(
        AvatarSubmission.objects.filter(user=user)
        .exclude(image=None)
        .values_list("image_id", flat=True)
    )


def _delete_images(ids) -> None:
    from wagtail.images import get_image_model

    ids = [pk for pk in ids if pk]
    for image in get_image_model().objects.filter(pk__in=ids):
        image.delete()  # Wagtail removes the file and thumbnails after commit


def _set_face(user, image_id) -> None:
    """Change the face through save(), so its pages are regenerated (2.3)."""
    user.avatar_id = image_id
    user.save(update_fields=["avatar"])


def submit_avatar(user, uploaded) -> AvatarSubmission:
    """Process an upload and put it in the review queue; whatever the person
    was waiting on before is withdrawn. Their face does not change yet."""
    from django.db import transaction

    from accounts.images import AvatarError, create_face_image
    from accounts.notifications import avatars_waiting_soon
    from core.ratelimit import over_limit

    if not can_use(user, Feature.AVATAR_UPLOAD):
        raise AvatarUploadError(feature_denied_message())
    if over_limit(f"avatar-upload:{user.pk}", AVATAR_UPLOADS_PER_DAY, DAY_SECONDS):
        raise AvatarUploadError("今天上传的次数用完了，明天再来吧。")
    try:
        image = create_face_image(uploaded, user=user)
    except AvatarError as error:
        raise AvatarUploadError(str(error)) from error
    with transaction.atomic():
        earlier = list(
            AvatarSubmission.objects.filter(
                user=user, status=AvatarSubmission.Status.PENDING
            )
        )
        for old in earlier:
            old.status = AvatarSubmission.Status.WITHDRAWN
            old.save(update_fields=["status"])
        _delete_images(old.image_id for old in earlier)
        submission = AvatarSubmission.objects.create(user=user, image=image)
    avatars_waiting_soon()
    return submission


def withdraw_avatar(user) -> bool:
    """Take back the picture waiting for review."""
    from django.db import transaction

    with transaction.atomic():
        submission = pending_avatar(user)
        if submission is None:
            return False
        submission.status = AvatarSubmission.Status.WITHDRAWN
        submission.save(update_fields=["status"])
        _delete_images([submission.image_id])
    return True


def remove_avatar(user) -> bool:
    """Back to the default face at once, no review; the old picture goes if
    the person uploaded it."""
    from django.db import transaction

    if not user.avatar_id:
        return False
    with transaction.atomic():
        old = user.avatar_id
        owned = old in uploaded_face_ids(user)
        _set_face(user, None)
        if owned:
            _delete_images([old])
    return True


def _decided(submission, status, reviewer, reason="", note=""):
    from django.utils import timezone

    submission.status = status
    submission.reason = reason
    submission.note = (note or "")[:200]
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=["status", "reason", "note", "reviewed_by", "reviewed_at"]
    )


def _locked(submission_id, status):
    submission = (
        AvatarSubmission.objects.select_related("user", "image")
        .filter(pk=submission_id)
        .first()
    )
    if submission is None or submission.status != status:
        raise AvatarReviewError("这张头像已经被处理过了，刷新看看。")
    return submission


def approve_avatar(submission_id, reviewer) -> AvatarSubmission:
    """The picture becomes the face; an earlier uploaded face is deleted."""
    from django.db import transaction

    with transaction.atomic():
        submission = _locked(submission_id, AvatarSubmission.Status.PENDING)
        if submission.image_id is None:
            raise AvatarReviewError("这张头像的图片不见了，没法通过。")
        user = submission.user
        old = user.avatar_id
        owned = old in uploaded_face_ids(user)
        _decided(submission, AvatarSubmission.Status.APPROVED, reviewer)
        _set_face(user, submission.image_id)
        if old and owned:
            _delete_images([old])
    return submission


def _check_reason(reason) -> str:
    from moderation.models import Category

    if reason not in Category.values:
        raise AvatarReviewError("请选一个原因。")
    return reason


def reject_avatar(submission_id, reviewer, reason, note="") -> AvatarSubmission:
    """Not shown; the picture is deleted and the person told why."""
    from django.db import transaction

    from accounts.notifications import avatar_rejected

    reason = _check_reason(reason)
    with transaction.atomic():
        submission = _locked(submission_id, AvatarSubmission.Status.PENDING)
        image_id = submission.image_id
        _decided(submission, AvatarSubmission.Status.REJECTED, reviewer, reason, note)
        _delete_images([image_id])
        transaction.on_commit(lambda: avatar_rejected(submission))
    return submission


def take_down_avatar(submission_id, reviewer, reason, note="") -> AvatarSubmission:
    """An approved face that turned out wrong: off the site, deleted, the
    person told why."""
    from django.db import transaction

    from accounts.notifications import avatar_taken_down

    reason = _check_reason(reason)
    with transaction.atomic():
        submission = _locked(submission_id, AvatarSubmission.Status.APPROVED)
        user = submission.user
        if not submission.image_id or user.avatar_id != submission.image_id:
            raise AvatarReviewError("这张头像现在没在用，不用撤下。")
        image_id = submission.image_id
        _decided(submission, AvatarSubmission.Status.TAKEN_DOWN, reviewer, reason, note)
        _set_face(user, None)
        _delete_images([image_id])
        transaction.on_commit(lambda: avatar_taken_down(submission))
    return submission


def forget_uploaded_faces(user) -> None:
    """Account deletion (design 3.8): every uploaded picture and its record."""
    ids = uploaded_face_ids(user)
    AvatarSubmission.objects.filter(user=user).delete()
    _delete_images(ids)


# --- the admin's user screens (design 14.2, 3.7; round 115) -------------------------


def after_deactivation(user) -> list:
    """Design 3.7: a stopped account's pending team applications are cancelled
    (it can no longer log in to follow them up), and the teams it captains
    stop recruiting (v6.62). Returns those teams."""
    from django.utils import timezone

    from teams.models import ApplicationStatus
    from teams.services import pause_recruiting

    user.team_applications.filter(status=ApplicationStatus.PENDING).update(
        status=ApplicationStatus.CANCELLED,
        decided_at=timezone.now(),
        decision_note="账号已停用",
    )
    return pause_recruiting(user)


def admin_profile(user, *, viewer) -> dict:
    """What the user edit page shows beside the form: the person on the site.
    Contacts only for those allowed to see them (design 3.5.3, 4.1)."""
    from accounts.roles import public_profile
    from teams.models import TeamMembership

    can_see_contacts = viewer.is_superuser or viewer.has_perm(
        "accounts.view_contactmethod"
    )
    return {
        "game_accounts": [
            (
                account.battletag,
                "、".join(
                    f"{label} {format_rank(getattr(account, field))}"
                    for label, field in (
                        ("坦克", "rank_tank"),
                        ("输出", "rank_damage"),
                        ("支援", "rank_support"),
                    )
                    if getattr(account, field) is not None
                )
                or "未定级",
            )
            for account in user.game_accounts.all()
        ],
        "contacts": [
            (contact.get_type_display(), contact.value)
            for contact in user.contact_methods.all()
        ]
        if can_see_contacts
        else None,
        "teams": [
            (membership.team, membership.get_role_display())
            for membership in TeamMembership.objects.filter(user=user).select_related(
                "team"
            )
        ],
        "roles": public_profile(user),
        "rules": [
            (rule.get_feature_display(), "允许" if rule.allowed else "禁止", rule.note)
            for rule in user.feature_rules.all()
        ],
        "verified": email_is_verified(user),
    }
