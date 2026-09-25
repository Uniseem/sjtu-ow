"""Demo content for looking at the redesign locally (round 074).

Not part of the app. Run against a *dev* database after `init_site`:

    uv run python manage.py shell < handoff/rounds/074-design-system/seed_demo.py

Creates demo users (`demo-*@example.com`, unusable passwords, so nobody can log
in as them), articles with generated abstract covers, tournaments, scrims,
teams, member groups and comments. Idempotent enough to re-run on an empty
database; it refuses to run if demo users already exist.
"""

import io
import random
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.core.files.images import ImageFile
from django.utils import timezone
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFilter
from wagtail.images.models import Image

from accounts.models import GameAccount, User
from comments.models import Comment
from content.models import ArticleCategory, ArticleIndexPage, HomePage
from content.models import ArticlePage
from members.models import MemberGroup, MemberGroupMembership
from scrims.models import Scrim, ScrimFormat, ScrimSignup, ScrimStatus
from teams.models import Team, TeamMembership, TeamRole
from tournaments.models import (
    IndividualSignup,
    Registration,
    RegistrationMember,
    RegistrationStatus,
    Tournament,
    TournamentStatus,
)

if User.objects.filter(email__startswith="demo-").exists():
    raise SystemExit("demo users already exist; start from a fresh dev database")

rng = random.Random(74)
now = timezone.now()

# --- images ---------------------------------------------------------------------

PALETTES = [
    ((28, 24, 26), (164, 22, 30), (236, 229, 219)),
    ((18, 22, 30), (70, 88, 110), (200, 58, 44)),
    ((36, 30, 28), (120, 96, 72), (230, 200, 160)),
    ((20, 20, 24), (90, 20, 30), (240, 240, 236)),
    ((24, 34, 40), (40, 110, 120), (230, 180, 90)),
    ((40, 16, 20), (178, 20, 26), (250, 210, 200)),
]


def make_image(title, seed, size=(1600, 900)):
    r = random.Random(seed)
    dark, mid, light = PALETTES[seed % len(PALETTES)]
    img = PILImage.new("RGB", size, dark)
    draw = ImageDraw.Draw(img)
    w, h = size
    for _ in range(9):
        x = r.randint(-w // 4, w)
        y = r.randint(-h // 4, h)
        rad = r.randint(h // 6, int(h / 1.4))
        colour = mid if r.random() < 0.6 else light
        draw.ellipse([x - rad, y - rad, x + rad, y + rad], fill=colour)
    img = img.filter(ImageFilter.GaussianBlur(radius=90))
    draw = ImageDraw.Draw(img)
    for i in range(0, w + h, 46):
        draw.line([(i, 0), (i - h, h)], fill=tuple(min(255, c + 10) for c in dark), width=1)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    buf.seek(0)
    image = Image(title=title)
    image.file = ImageFile(buf, name=f"demo-{seed}.jpg")
    image.save()
    return image


def make_logo(name, seed):
    r = random.Random(seed)
    colours = [(178, 20, 26), (30, 30, 34), (48, 92, 120), (140, 110, 60), (80, 40, 90)]
    img = PILImage.new("RGB", (400, 400), colours[seed % len(colours)])
    draw = ImageDraw.Draw(img)
    for _ in range(3):
        cx, cy = r.randint(80, 320), r.randint(80, 320)
        rad = r.randint(60, 150)
        draw.polygon(
            [(cx, cy - rad), (cx + rad, cy), (cx, cy + rad), (cx - rad, cy)],
            outline=(245, 240, 232),
            width=10,
        )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    image = Image(title=f"{name} 队标")
    image.file = ImageFile(buf, name=f"logo-{seed}.png")
    image.save()
    return image


# --- users ----------------------------------------------------------------------

NICKS = [
    "夜航", "白露", "青梧", "阿哲", "Kairo", "小满", "南风", "栗子", "Mercy酱", "老周",
    "望舒", "Rin", "拾一", "钢板", "闪光", "木鱼", "Soba", "沉舟", "北岛", "星野",
    "七月", "竹间", "Leo", "糯米", "长夜", "阿奎", "橘猫", "Echo", "山岚", "一苇",
]
users = []
for i, nick in enumerate(NICKS):
    user = User.objects.create(
        email=f"demo-{i}@example.com",
        nickname=nick,
        is_sjtu=i % 4 != 3,
        agreed_terms_at=now,
        agreed_cross_border_at=now,
    )
    user.set_unusable_password()
    user.save()
    User.objects.filter(pk=user.pk).update(date_joined=now - timedelta(days=200 - i * 6))
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    ranks = [rng.choice([None, *range(8, 40)]) for _ in range(3)]
    GameAccount.objects.create(
        user=user,
        battletag=f"{nick if nick.isascii() else 'Player'}#{rng.randint(1000, 99999)}",
        rank_tank=ranks[0],
        rank_damage=ranks[1],
        rank_support=ranks[2],
    )
    users.append(user)

# --- teams ----------------------------------------------------------------------

TEAMS = [
    ("思源", "2019 年成立的老队，校赛三连冠。每周二、四晚训练，欢迎稳定上线的辅助。"),
    ("东川路电竞", "闵行校区宿舍楼里组起来的队伍，主打开心上分，也打校赛。"),
    ("Cyan Tide", "研究生为主，节奏偏慢，重视复盘。缺一个主坦。"),
    ("零点整", "只在零点以后训练的队伍。"),
    ("鹊桥", "徐汇和闵行两个校区联合组队。"),
    ("Anchor", "刚成立，招募所有位置。"),
]
teams = []
for i, (name, desc) in enumerate(TEAMS):
    team = Team.objects.create(
        name=name,
        description=desc,
        logo=make_logo(name, i) if i % 3 != 2 else None,
        is_recruiting=i % 2 == 0,
    )
    members = users[i * 5 : i * 5 + 5]
    for j, user in enumerate(members):
        TeamMembership.objects.create(
            team=team, user=user, role=TeamRole.CAPTAIN if j == 0 else TeamRole.MEMBER
        )
    teams.append(team)

# --- members --------------------------------------------------------------------

groups = [
    ("社团理事会", "负责社团日常运营、赛事组织和对外联络。", [(0, "社长"), (5, "副社长"), (10, "秘书长"), (15, "赛事部部长")]),
    ("赛事与内战组", "排期、裁判、分队和直播。", [(1, "内战负责人"), (6, "裁判"), (11, "导播"), (16, "")]),
    ("内容组", "写公告、战报和攻略，运营 B 站账号。", [(2, "主编"), (7, ""), (12, "")]),
]
for order, (name, desc, people) in enumerate(groups):
    group = MemberGroup.objects.create(name=name, description=desc, sort_order=order)
    for k, (idx, title) in enumerate(people):
        MemberGroupMembership.objects.create(group=group, user=users[idx], title=title, sort_order=k)

# --- articles -------------------------------------------------------------------

home = HomePage.objects.first()
news = ArticleIndexPage.objects.get(slug="news")
cats = {c.slug: c for c in ArticleCategory.objects.all()}
cat_list = list(cats.values())

PARA = (
    "<p>本学期的第一场校内赛在闵行校区学生中心落下帷幕。十二支队伍在两天里打完了四十一张地图，"
    "从小组赛一路打到决赛，观众席上坐满了来看比赛的同学。</p>"
    "<h2>小组赛：老队的底蕴</h2>"
    "<p>思源在小组赛里没丢一张图。他们的辅助位是上学期从内战里挖来的新人，在渣客镇的最后一波团战里"
    "用一个关键的大招稳住了局面。赛后队长说，「我们练得最多的不是枪法，是交流」。</p>"
    "<ul><li>小组赛采用 BO3，每张地图按官方轮换</li><li>淘汰赛 BO5，决赛 BO7</li>"
    "<li>全部比赛在校内网络环境下进行</li></ul>"
    "<p>下学期的秋季赛报名已经开放，个人也可以报名，由赛事组编成临时队伍参赛。</p>"
)

ARTICLES = [
    ("2026 秋季校内赛报名开始", "notice", "十二支队伍的名额，个人也可以报名，由赛事组编队。报名截止到 10 月 10 日。"),
    ("暑期内战回顾：48 人、8 支队伍、一个晚上", "report", "自动分队第一次在大规模内战里使用，分差最大的一场只有 3 分。"),
    ("新赛季辅助位环境：从理解节奏开始", "guide", "不讲数值，讲什么时候该交技能、什么时候该站出来。"),
    ("社团网站开始测试", "notice", "注册、战队、内战报名都可以用了，发现问题请在群里告诉我们。"),
    ("从青铜到钻石：一个新人坦克的半年", "essay", "我是怎么在内战里被打醒的。"),
    ("春季赛决赛：思源 4:3 东川路电竞", "report", "七张图打满，最后一波推车在终点前两米停下。"),
    ("内战规则更新：位置与段位", "notice", "从本周起，内战报名需要填写三个位置的段位。"),
    ("地图笔记：伊利奥斯的三个点", "guide", "每个点位的高台、血包和绕后路线。"),
    ("招新季 | 欢迎加入守望先锋社", "notice", "不论段位，只要你喜欢这个游戏。"),
    ("观赛指南：怎么看懂一场职业比赛", "guide", "看小地图、看大招、看阵容。"),
]
articles = []
for i, (title, cat_slug, summary) in enumerate(ARTICLES):
    category = cats.get(cat_slug) or cat_list[i % len(cat_list)]
    page = ArticlePage(
        title=title,
        slug=f"demo-{i}",
        category=category,
        summary=summary,
        author=users[(i * 3) % len(users)],
        cover=make_image(title, i + 10) if i % 3 != 2 else None,
        body=[
            ("paragraph", PARA),
            ("quote", {"text": "我们练得最多的不是枪法，是交流。", "attribution": "思源战队队长"}),
            ("paragraph", PARA),
        ],
    )
    news.add_child(instance=page)
    rev = page.save_revision()
    rev.publish()
    ArticlePage.objects.filter(pk=page.pk).update(
        first_published_at=now - timedelta(days=i * 4 + 1, hours=i)
    )
    articles.append(ArticlePage.objects.get(pk=page.pk))

# --- tournaments ----------------------------------------------------------------

tour_open = Tournament.objects.create(
    title="2026 秋季校内赛",
    summary="上海交通大学守望先锋社区秋季校内赛，面向全体在校同学，支持个人报名。",
    description="<p>赛制：小组赛 BO3，淘汰赛 BO5，决赛 BO7。</p><p>比赛在闵行校区学生中心进行，全程直播。</p>",
    cover=make_image("秋季赛", 40),
    starts_at=now + timedelta(days=20),
    registration_opens_at=now - timedelta(days=5),
    registration_closes_at=now + timedelta(days=12),
    roster_min=5,
    roster_max=7,
    sjtu_only=True,
    allow_individual_signup=True,
    status=TournamentStatus.PUBLISHED,
    published_at=now - timedelta(days=5),
)
tour_soon = Tournament.objects.create(
    title="新生杯",
    summary="只给 2026 级新生的比赛，老生可以报名当教练。",
    starts_at=now + timedelta(days=45),
    registration_opens_at=now + timedelta(days=10),
    registration_closes_at=now + timedelta(days=30),
    status=TournamentStatus.PUBLISHED,
    published_at=now - timedelta(days=1),
)
tour_done = Tournament.objects.create(
    title="2026 春季校内赛",
    summary="十支队伍，思源夺冠。",
    cover=make_image("春季赛", 41),
    starts_at=now - timedelta(days=120),
    registration_opens_at=now - timedelta(days=150),
    registration_closes_at=now - timedelta(days=130),
    status=TournamentStatus.FINISHED,
    published_at=now - timedelta(days=150),
)
for t_index, team in enumerate(teams[:4]):
    for tour in (tour_open, tour_done) if t_index < 3 else (tour_open,):
        status = (
            RegistrationStatus.APPROVED
            if tour is tour_done or t_index < 2
            else RegistrationStatus.PENDING
        )
        reg = Registration.objects.create(
            tournament=tour,
            team=team,
            status=status,
            team_name=team.name,
            submitted_by=team.memberships.get(role=TeamRole.CAPTAIN).user,
        )
        for m in team.memberships.select_related("user"):
            ga = m.user.game_accounts.first()
            RegistrationMember.objects.create(
                registration=reg,
                tournament=tour,
                user=m.user,
                game_account=ga,
                nickname=m.user.nickname,
                battletag=ga.battletag,
                is_sjtu=m.user.is_sjtu,
                rank_tank=ga.rank_tank,
                rank_damage=ga.rank_damage,
                rank_support=ga.rank_support,
                is_captain=m.role == TeamRole.CAPTAIN,
            )
for k, user in enumerate(users[25:30]):
    IndividualSignup.objects.create(
        tournament=tour_open,
        user=user,
        game_account=user.game_accounts.first(),
        role_tank=k % 3 == 0,
        role_damage=k % 3 == 1,
        role_support=k % 3 == 2 or k == 4,
    )
for i in (0, 1, 5):
    ArticlePage.objects.filter(pk=articles[i].pk).update(
        tournament=tour_open if i == 0 else tour_done
    )

# --- scrims ---------------------------------------------------------------------

scrim_specs = [
    ("周五夜间内战", now + timedelta(days=2, hours=3), ScrimFormat.RQ_5V5, ScrimStatus.PUBLISHED, 14),
    ("周末大内战 · 6v6 回归", now + timedelta(days=5), ScrimFormat.RQ_6V6, ScrimStatus.PUBLISHED, 9),
    ("新人友好局", now + timedelta(days=9), ScrimFormat.OPEN_5V5, ScrimStatus.PUBLISHED, 4),
    ("中秋内战", now - timedelta(days=6), ScrimFormat.RQ_5V5, ScrimStatus.FINISHED, 10),
    ("暑期大内战", now - timedelta(days=40), ScrimFormat.RQ_5V5, ScrimStatus.FINISHED, 20),
]
for title, starts, fmt, status, count in scrim_specs:
    scrim = Scrim.objects.create(
        title=title,
        description="九点准时开始，八点五十前进语音频道。分队结果会在开始前十分钟公布。",
        starts_at=starts,
        signup_closes_at=starts - timedelta(hours=2),
        format=fmt,
        status=status,
        sjtu_only=False,
    )
    for k, user in enumerate(users[:count]):
        ScrimSignup.objects.create(
            scrim=scrim,
            user=user,
            game_account=user.game_accounts.first(),
            role_tank=k % 3 == 0,
            role_damage=k % 3 == 1 or k % 5 == 0,
            role_support=k % 3 == 2,
        )

# --- comments -------------------------------------------------------------------

target = articles[1]
bodies = [
    "分队真的很均衡，最后一把打到加时。",
    "希望下次能早点公布分队结果，好提前商量阵容。",
    "第一次参加内战，体验很好，谢谢组织的同学！",
    "请问下一次是什么时候？",
    "@夜航 你那把源氏太离谱了",
]
tops = []
for k, body in enumerate(bodies[:4]):
    c = Comment.objects.create(page=target, author=users[k + 3], body=body, like_count=[12, 3, 27, 0][k])
    tops.append(c)
Comment.objects.filter(pk=tops[2].pk).update(is_pinned=True)
for k in range(3):
    Comment.objects.create(
        page=target,
        author=users[k + 10],
        parent=tops[0],
        reply_to_user=tops[0].author if k else None,
        body=["同意，最后那波太刺激了。", "加时那一下我手都在抖", "下次还来"][k],
        like_count=k,
    )

# --- homepage carousel -----------------------------------------------------------

from content.models import HomePageCarouselItem  # noqa: E402

for k, article in enumerate([a for a in articles if a.cover_id][:3]):
    HomePageCarouselItem.objects.create(
        page=home, image=article.cover, title=article.title, link_page=article, sort_order=k
    )
home.save_revision().publish()

print("demo content ready")
