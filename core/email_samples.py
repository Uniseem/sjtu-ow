"""Every email the site sends, rendered with made-up data (design 10.3).

For the specimen page /_styleguide/emails/. Nothing here reads or writes the
database apart from looking up nobody's name: the builders get stand-ins for
teams, tournaments and scrims, so the page shows exactly what a real letter
looks like without anyone receiving one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.utils import timezone

from core import letters


@dataclass
class Sample:
    key: str
    group: str
    title: str  # what the email is, as design 10.2 names it
    to: str  # who gets it
    subject: str
    text: str
    html: str


def _team():
    return SimpleNamespace(
        pk=1,
        name="交大龙骑",
        member_contact="QQ 群 123456789",
        get_absolute_url=lambda: "/teams/1/",
    )


def _tournament():
    return SimpleNamespace(
        pk=1,
        title="2026 秋季校内杯",
        starts_at=timezone.make_aware(datetime(2026, 11, 8, 14, 0)),
        registration_closes_at=timezone.make_aware(datetime(2026, 11, 1, 23, 59)),
        participant_contact="选手群 987654321",
        get_absolute_url=lambda: "/tournaments/1/",
    )


def _registration(status="pending", label="待审核", *, adhoc=False):
    return SimpleNamespace(
        pk=1,
        tournament=_tournament(),
        tournament_id=1,
        team_id=None if adhoc else 1,
        team_name="新生一队" if adhoc else "交大龙骑",
        roster_version=1,
        status=status,
        get_status_display=lambda: label,
        get_absolute_url=lambda: "/registrations/1/",
        submitted_by=SimpleNamespace(nickname="七月流火"),
    )


def _application(status):
    return SimpleNamespace(
        team=_team(),
        applicant=SimpleNamespace(nickname="小天使"),
        role_labels=lambda: ["坦克", "支援"],
        message="周末晚上都有空，主玩坦克。",
        status=status,
        decision_note="这个赛季名额满了，下个赛季欢迎再来。",
    )


def _scrim():
    starts = timezone.make_aware(datetime(2026, 10, 5, 19, 30))
    return SimpleNamespace(
        pk=2,
        title="国庆特别场 · 6v6 怀旧",
        starts_at=starts,
        get_format_display=lambda: "不限位置 6v6",
    )


def _flagged(pk, risk, kind, excerpt):
    return SimpleNamespace(
        pk=pk,
        get_target_type_display=lambda: kind,
        get_risk_display=lambda: risk,
        category_labels=lambda: ["辱骂"],
        reason="评论里有针对其他用户的辱骂。",
        quote="",
        excerpt=excerpt,
        url=f"/news/sample-{pk}/",
    )


def _avatar(status, reason, note=""):
    labels = {"porn": "色情低俗", "impersonation": "冒充官方"}
    return SimpleNamespace(
        status=status,
        get_reason_display=lambda: labels[reason],
        note=note,
        user=SimpleNamespace(nickname="小天使", email="angel@example.com"),
        created_at=timezone.make_aware(datetime(2026, 10, 3, 14, 20)),
    )


def _letter(key, group, title, to, letter, name) -> Sample:
    text, html = letters.render(letter, name)
    return Sample(key, group, title, to, letter.subject, text, html)


def _account(key, title, to, prefix, **context) -> Sample:
    """An allauth email, through the same frame the adapter gives it."""
    from django.conf import settings

    name = getattr(context.get("user"), "nickname", "") or ""
    base = {
        "verify_minutes": settings.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT // 60,
        "reset_minutes": settings.ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT // 60,
        **context,
    }
    subject = render_to_string(f"account/email/{prefix}_subject.txt", base).strip()
    base = {**letters.frame(name, subject=subject), **base}
    text = render_to_string(f"account/email/{prefix}_message.txt", base).strip()
    html = render_to_string(f"account/email/{prefix}_message.html", base)
    return Sample(key, "账号", title, to, subject, text, html)


def samples() -> list[Sample]:
    from accounts import notifications as faces
    from content import notifications as articles
    from core.mail import test_letter
    from moderation import notifications as moderation
    from scrims import notifications as scrims
    from teams import notifications as teams
    from tournaments import notifications as tournaments
    from tournaments import notifications_registration as registration

    approved = _registration("approved", "已通过")
    rejected = _registration("rejected", "已驳回")
    adhoc = _registration("approved", "已通过", adhoc=True)
    row = SimpleNamespace(battletag="小天使#5123")
    leaver = SimpleNamespace(nickname="西瓜")
    flagged = [
        _flagged(42, "高", "评论", "你这种水平也配打天梯？"),
        _flagged(43, "中", "文章", "比赛录像里出现了未经同意的真实姓名。"),
        _flagged(44, "低", "个人宣言", "加群领福利，私聊。"),
    ]
    return [
        _account(
            "verify",
            "注册 / 修改邮箱验证码",
            "注册人",
            "email_confirmation",
            code="482915",
            user=SimpleNamespace(nickname="小天使"),
        ),
        _account(
            "reset",
            "找回密码验证码",
            "本人",
            "password_reset_code",
            code="730264",
            user=SimpleNamespace(nickname="小天使"),
        ),
        _account(
            "unknown",
            "没有注册的邮箱",
            "填写的邮箱",
            "unknown_account",
            signup_url=letters.site_url("/accounts/signup/"),
        ),
        _account(
            "exists",
            "已经注册过的邮箱",
            "填写的邮箱",
            "account_already_exists",
            email="xiaotianshi@example.com",
            password_reset_url=letters.site_url("/accounts/password/reset/"),
        ),
        _letter(
            "smtp", "后台", "SMTP 测试邮件", "操作的管理员", test_letter(), "管理员"
        ),
        _letter(
            "apply",
            "战队",
            "收到入队申请",
            "队长",
            teams.application_submitted_letter(_application("pending")),
            "七月流火",
        ),
        _letter(
            "apply-ok",
            "战队",
            "入队申请通过",
            "申请人",
            teams.application_decided_letter(_application("approved")),
            "小天使",
        ),
        _letter(
            "apply-no",
            "战队",
            "入队申请未通过",
            "申请人",
            teams.application_decided_letter(_application("rejected")),
            "小天使",
        ),
        _letter(
            "applications-waiting",
            "战队",
            "入队申请等你处理",
            "队长",
            teams.applications_waiting_letter(_team(), [_application("pending")]),
            "七月流火",
        ),
        _letter(
            "removed",
            "战队",
            "被移出战队",
            "被移除的人",
            teams.member_removed_letter(_team()),
            "小天使",
        ),
        _letter(
            "unplaced-reminder",
            "赛事",
            "赛事开始提醒（还没编进队伍）",
            "散人池里还没编进的人",
            tournaments.unplaced_reminder_letter(_tournament()),
            "西瓜",
        ),
        _letter(
            "tournament-moved",
            "赛事",
            "比赛时间改了",
            "报了名的人（名单里的、散人池里的）",
            tournaments.time_changed_letter(
                _tournament(), timezone.make_aware(datetime(2026, 11, 7, 14, 0))
            ),
            "小天使",
        ),
        _letter(
            "member-left",
            "战队",
            "队员退出战队",
            "队长",
            teams.member_left_letter(
                _team(), SimpleNamespace(nickname="西瓜"), [_registration()]
            ),
            "七月流火",
        ),
        _letter(
            "captain",
            "战队",
            "成为队长",
            "新队长",
            teams.captain_changed_letter(_team()),
            "小天使",
        ),
        _letter(
            "disbanded",
            "战队",
            "战队解散",
            "全体成员",
            teams.team_disbanded_letter(_team()),
            "小天使",
        ),
        _letter(
            "submitted",
            "赛事",
            "报名已提交",
            "队长",
            registration.registration_submitted_letter(_registration(), "submit"),
            "七月流火",
        ),
        _letter(
            "entered",
            "赛事",
            "你已被报名参加",
            "名单里的队员",
            registration.team_member_entered_letter(_registration(), row),
            "小天使",
        ),
        _letter(
            "approved",
            "赛事",
            "报名通过",
            "队长",
            registration.registration_status_changed_letter(approved),
            "七月流火",
        ),
        _letter(
            "rejected",
            "赛事",
            "报名驳回",
            "队长",
            registration.registration_status_changed_letter(
                rejected, "名单里有两位队员没有填联系方式。"
            ),
            "七月流火",
        ),
        _letter(
            "cancelled",
            "赛事",
            "赛事取消",
            "队长、临时队伍成员",
            tournaments.tournament_cancelled_letter(
                _tournament(), "场地临时不能用，改期另行通知。"
            ),
            "七月流火",
        ),
        _letter(
            "formed",
            "赛事",
            "已编入临时队伍",
            "被编入的成员",
            registration.adhoc_team_formed_letter(adhoc),
            "西瓜",
        ),
        _letter(
            "returned",
            "赛事",
            "移出临时队伍 / 队伍解散",
            "受影响的成员",
            registration.adhoc_members_returned_letter(
                _tournament(), "新生一队", dissolved=True
            ),
            "西瓜",
        ),
        _letter(
            "left",
            "赛事",
            "临时队伍成员退出",
            "赛事管理员",
            registration.adhoc_member_left_letter(adhoc, leaver),
            "赛事管理员",
        ),
        _letter(
            "tournament-reminder",
            "赛事",
            "赛事开始提醒",
            "已通过报名的队员，每人一封",
            tournaments.tournament_reminder_letter(
                _tournament(),
                SimpleNamespace(registration=approved, battletag=row.battletag),
            ),
            "小天使",
        ),
        _letter(
            "reminder",
            "内战",
            "内战开始提醒",
            "全部报名者",
            scrims.scrim_reminder_letter(
                _scrim(), "A 队 · 坦克", "https://qm.qq.com/q/example"
            ),
            "小天使",
        ),
        _letter(
            "new-tournament",
            "活动通知",
            "新赛事通知（群发）",
            "开着活动通知的成员",
            tournaments.new_tournament_letter(
                SimpleNamespace(
                    title="2026 秋季校内杯",
                    summary="五人一队，单败淘汰，冠军队伍有社团周边。",
                    starts_at=timezone.make_aware(datetime(2026, 11, 8, 14, 0)),
                    registration_opens_at=timezone.make_aware(datetime(2026, 10, 1)),
                    registration_closes_at=timezone.make_aware(
                        datetime(2026, 11, 1, 23, 59)
                    ),
                    get_registration_mode_display=lambda: "个人报名，赛事组编队",
                    sjtu_only=True,
                    get_absolute_url=lambda: "/tournaments/1/",
                ),
                "https://example.com/unsubscribe/sample/",
            ),
            "小天使",
        ),
        _letter(
            "new-article",
            "活动通知",
            "新文章通知（群发）",
            "开着活动通知的成员",
            articles.new_article_letter(
                SimpleNamespace(
                    title="秋季招新开始了",
                    summary="面向全校，不限段位，填表后拉你进群。",
                    category=SimpleNamespace(name="公告"),
                    url="/news/autumn-recruiting/",
                ),
                "https://example.com/unsubscribe/sample/",
            ),
            "小天使",
        ),
        _letter(
            "new-scrim",
            "活动通知",
            "新内战通知（群发）",
            "开着活动通知的成员",
            scrims.new_scrim_letter(
                SimpleNamespace(
                    **vars(_scrim()),
                    signup_deadline=timezone.make_aware(datetime(2026, 10, 5, 18, 0)),
                    sjtu_only=False,
                    description="怀旧版本，六人一队，不限位置。",
                ),
                "https://example.com/unsubscribe/sample/",
            ),
            "小天使",
        ),
        _letter(
            "scrim-moved",
            "内战",
            "内战时间改了",
            "全部报名者",
            scrims.scrim_time_changed_letter(
                _scrim(), timezone.make_aware(datetime(2026, 10, 4, 19, 30))
            ),
            "小天使",
        ),
        _letter(
            "scrim-cancelled",
            "内战",
            "内战取消",
            "全部报名者",
            scrims.scrim_cancelled_letter(_scrim()),
            "小天使",
        ),
        _letter(
            "patrol",
            "审核",
            "AI 巡查发现可能不妥的内容（v6.72）",
            "「巡查提醒发到」填的邮箱，没填是全部超级管理员",
            moderation.patrol_letter(flagged),
            "站长",
        ),
        _letter(
            "ask-author",
            "审核",
            "要求修改内容",
            "内容的作者",
            moderation.revise_letter(
                SimpleNamespace(
                    target_type="team_description",
                    target_id=3,
                    url="/teams/3/",
                    quote="来的都是菜鸡",
                    excerpt="欢迎新人！来的都是菜鸡，别来拖后腿。",
                    get_target_type_display=lambda: "战队简介",
                ),
                "简介里有贬低其他玩家的说法，请改成正面的招募介绍。",
            ),
            "队长甲",
        ),
        _letter(
            "avatar-taken-down",
            "账号",
            "头像被撤下",
            "上传的人",
            faces.avatar_taken_down_letter(_avatar("taken_down", "porn")),
            "小天使",
        ),
    ]


def sample(key: str) -> Sample | None:
    return next((item for item in samples() if item.key == key), None)
