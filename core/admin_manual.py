"""「后台手册」 (design 14.1, v6.47): what each role does in the admin, a few
steps each, linking to the real places. Everyone sees only their parts.

The officers who take the site over are not necessarily developers, and
Wagtail's own help is a generic English editing guide.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import reverse


@dataclass(frozen=True)
class Step:
    text: str
    link: tuple[str, str] | None = None  # (url name, label)


@dataclass(frozen=True)
class Part:
    key: str
    title: str
    steps: tuple[Step, ...]


TOURNAMENTS = Part(
    "tournaments",
    "赛事管理员",
    (
        Step(
            "新建赛事：社区 → 赛事 → 添加。标题、报名开始和截止时间必填；填了比赛时间，"
            "开赛前才会自动提醒。报名方式默认是个人报名（每人自己报，你来编队），整队"
            "报名由队长为全队报。「选手联系方式」（比如选手群号）只给报了名的人看。"
            "每年都办的赛事，在去年那场的「更多 → 复制」里建，时间按整周挪到今年。",
            ("tournaments:add", "新建赛事"),
        ),
        Step(
            "发布和通知：在赛事列表这一行的「更多 → 发布」。发布确认页可以勾「同时通知"
            "全体成员」；发布后也可以在「更多 → 通知全体成员」里先看信再发，每场一次。",
            ("tournaments:index", "赛事列表"),
        ),
        Step(
            "审核报名：首页待办会写有几份等你审。逐条通过或驳回（驳回要写备注，队长会"
            "收到），也可以勾选后一起通过。",
            ("registration_review_index", "报名审核"),
        ),
        Step(
            "编队（个人报名的赛事）：报名截止后待办会写「有 N 人等待编队」。在赛事的"
            "「更多 → 队伍编排」里把散人拖进队伍，保存后这些队伍直接算通过，每人收到"
            "一封邮件；没编进的人开赛前一天也会收到说明。"
        ),
        Step(
            "改时间、取消：直接改比赛时间，报了名的人会收到「比赛时间改了」，提醒按新"
            "时间重发。取消在「更多 → 取消赛事」，写一句原因，报了名的人都会收到。"
        ),
        Step(
            "结束：打完在「更多 → 标记为已结束」；开赛 3 天还没标，待办会提醒。比赛"
            "结果写一篇战报文章，在文章里关联这项赛事，赛事页会列出来。"
        ),
    ),
)

SCRIMS = Part(
    "scrims",
    "内战管理员",
    (
        Step(
            "新建内战：社区 → 内战活动 → 添加，选规格（角色限定或不限位置，5v5 或 6v6）"
            "和开始时间。发布时可以同时通知全体成员。每周都有的内战，在上一场的「更多 →"
            " 复制」里建，时间自动挪到下一周。",
            ("scrims:add", "新建内战"),
        ),
        Step(
            "分队：报名截止后待办会写「还没分队」。在内战的「更多 → 分队」里勾选上场的"
            "人、生成分队、拖拽调整、保存，再点「复制」把结果发到群里。报名的人在活动页"
            "和提醒邮件里能看到自己分在哪。",
            ("scrims:index", "内战列表"),
        ),
        Step(
            "提醒和结束：开始前 2 小时（全站设置里可改）自动给报名的人发提醒；"
            "开始 6 小时后自动标记已结束，也可以提前手动标。"
        ),
        Step(
            "改时间、取消：改开始时间会通知报名的人并重新提醒；"
            "取消在「更多 → 取消内战」，报名的人都会收到。"
        ),
    ),
)

CONTENT = Part(
    "content",
    "内容编辑",
    (
        Step(
            "每天看一眼首页的待办：几条内容等复核、几张头像等审核、几篇投稿等你审。",
            ("wagtailadmin_home", "后台首页"),
        ),
        Step(
            "审稿：投稿提交后进入「内容审核」流程，打开稿件，在页面底部的操作里通过"
            "（直接发布）或退回（写意见，投稿人会收到）。"
        ),
        Step(
            "AI 审核标记的内容：每条看过后选「无问题」「已处置」或「忽略」；"
            "需要作者改的，用「要求作者修改」写一段说明发给他。",
            ("moderation_index", "内容审核"),
        ),
        Step("头像：通过后才公开，不通过要写原因。", ("avatar_review", "头像审核")),
        Step(
            "评论：在文章页上直接隐藏、恢复、置顶，也可以到这里统一看。",
            ("comments:index", "评论"),
        ),
        Step(
            "发文章和群发：在页面里写文章直接发布；重要的公告发布后，在页面列表的"
            "「更多 → 通知全体成员」里群发给开着活动通知的成员。"
        ),
        Step(
            "定时上线和下线：编辑页右侧「状态」面板点「设置计划」，填上线时间（到点"
            "自动发布）或过期时间（到点自动撤下），再点发布。到点后半分钟内生效。"
            "要上线时同时群发，在页面列表的「更多 → 上线时通知全体成员」里安排好。"
        ),
        Step(
            "成员展示上的分组和职务（比如「社团干部 · 社长」）在这里维护。",
            ("wagtailsnippets_members_membergroup:list", "成员分组"),
        ),
    ),
)

AUTHORS = Part(
    "authors",
    "认证作者",
    (
        Step(
            "你的文章不用审核，发布后直接上线；网址和搜索描述在编辑页的「推荐」里，"
            "定时发布在右侧「状态」面板的「设置计划」里。只能改自己的文章。"
        ),
    ),
)

OWNER = Part(
    "owner",
    "超级管理员（站长）",
    (
        Step(
            "上线清单：后台首页下面列着还没做的配置，逐项完成。最要紧的是全站设置里的"
            "邮件（SMTP）：注册要验证邮箱，配好后点「发送测试邮件」。",
            ("wagtailadmin_home", "后台首页"),
        ),
        Step(
            "分配角色：用户 → 用户 → 编辑某人 → 角色，勾「内容编辑」「赛事管理员」"
            "「内战管理员」或「认证作者」。",
            ("wagtailusers_users:index", "用户"),
        ),
        Step(
            "出问题时看待办：邮件发不出去、后台任务没在运行、备份没跑或上传失败、"
            "AI 审核调用失败、静态页生成失败，每条都写了原因和去哪儿处理。"
        ),
        Step(
            "每天夜里服务器的定时任务会备份、清理旧数据（顺带提醒和关闭没人处理的入队"
            "申请）、重新生成静态页，见 README「定时维护」。异地备份填完对象存储后先点"
            "全站设置里的「测试对象存储」。"
        ),
        Step(
            "年审、换届总结要报的数（办了几场内战和赛事、多少人参加、新增多少成员）"
            "在「社区 → 活动数据」，选好时间段可以下载逐场的表。",
            ("admin_activity", "活动数据"),
        ),
    ),
)


def parts_for(user) -> list[Part]:
    from accounts.services import GROUP_AUTHOR, GROUP_CONTENT
    from scrims import services as scrim_services
    from tournaments import services as tournament_services

    if not getattr(user, "is_authenticated", False):
        return []
    groups = set(user.groups.values_list("name", flat=True))
    parts = []
    if user.is_superuser:
        parts.append(OWNER)
    if user.is_superuser or GROUP_CONTENT in groups:
        parts.append(CONTENT)
    if tournament_services.can_manage(user):
        parts.append(TOURNAMENTS)
    if scrim_services.can_manage(user):
        parts.append(SCRIMS)
    if GROUP_AUTHOR in groups and GROUP_CONTENT not in groups and not user.is_superuser:
        parts.append(AUTHORS)
    return parts


def manual_view(request):
    parts = parts_for(request.user)
    if not parts:
        raise PermissionDenied("后台手册给管理员看；投稿须知在编辑页上。")
    shown = [
        (
            part,
            [
                (
                    step.text,
                    reverse(step.link[0]) if step.link else "",
                    step.link[1] if step.link else "",
                )
                for step in part.steps
            ],
        )
        for part in parts
    ]
    return render(
        request,
        "core/admin/manual.html",
        {"page_title": "后台手册", "header_icon": "help", "parts": shown},
    )
