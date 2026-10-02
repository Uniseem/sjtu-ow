"""Round 102, demo data only: fuller articles, comments, tournaments and scrims
for the public demo site. Idempotent; run with `manage.py shell < enrich_demo.py`.
Looks things up by slug and title, so it works on any copy of the demo DB."""

import json
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import F
from django.utils import timezone

from accounts.models import User
from comments import services as comment_services
from comments.models import Comment, CommentLike
from content.models import ArticleCategory, ArticleIndexPage, ArticlePage
from scrims import services as scrim_services
from scrims.models import Scrim, ScrimFormat, ScrimStatus
from tournaments.models import Tournament

CST = ZoneInfo("Asia/Shanghai")
NOW = timezone.now()
rng = random.Random(102)


def at(month, day, hour=20, minute=0, year=2026):
    return datetime(year, month, day, hour, minute, tzinfo=CST)


def u(pk):
    return User.objects.get(pk=pk)


def para(html):
    return {"type": "paragraph", "value": html}


def quote(text, who):
    return {"type": "quote", "value": {"text": text, "attribution": who}}


# --- articles ---------------------------------------------------------------------

ARTICLES = [
    dict(
        slug="site-launch", category="notice", author=20, when=at(9, 1, 10),
        title="社区网站正式上线",
        summary="交大守望先锋社区有了自己的网站：赛事报名、内战报名、战队招募都可以在这里完成。",
        body=[para(
            "<p>经过一个暑假的开发和测试，交大守望先锋社区的网站今天正式上线了。以前散落在 QQ 群公告、在线文档和问卷里的东西，以后都可以在这里找到。</p>"
            "<h2>网站上能做什么</h2><ul>"
            "<li><b>赛事</b>：校内杯、新生杯的报名、名单和赛程都在「赛事」页，报名状态随时能查</li>"
            "<li><b>内战</b>：每周的内战在「内战」页报名，勾好能打的位置，开打前管理员一键分队</li>"
            "<li><b>战队</b>：可以建自己的战队、写招募信息，也可以申请加入别人的队伍</li>"
            "<li><b>成员</b>：社团干部、赛事组和所有成员的名片，常用位置和段位一目了然</li>"
            "<li><b>资讯</b>：公告、赛事通知、攻略、战报和心得，所有成员都可以投稿</li></ul>"
            "<h2>怎么注册</h2><p>用邮箱注册就行，用交大邮箱注册的账号会自动认证为交大同学。注册后到「个人中心」补上游戏 ID 和一种联系方式，资料齐了才能报名赛事和内战。游戏 ID 填战网的 BattleTag，比如「闪光弹#5123」。</p>"
            "<h2>隐私</h2><p>你的游戏 ID、联系方式和邮箱只有赛事管理员、内战管理员能看到，队友和其他成员都看不到。成员页上公开的只有头像、昵称、个人宣言、常用位置和段位；段位也可以在个人中心关掉。</p>"
            "<h2>遇到问题</h2><p>网站还在持续改进，用起来有不顺手的地方、发现了 bug，欢迎在这篇文章下面留言，或者在群里找技术组。也欢迎有兴趣的同学加入技术组一起维护。</p>"
        )],
    ),
    dict(
        slug="recruitment-2026", category="notice", author=1, when=at(9, 10, 12),
        title="2026–2027 学年招新开始啦",
        summary="不管你是青铜还是英杰，只要喜欢守望先锋，都欢迎加入我们。",
        body=[para(
            "<p>新学年开始了！交大守望先锋社区面向全校招新，不管你是刚定级的新人还是打了好几年的老玩家，只要喜欢守望先锋，都欢迎加入。</p>"
            "<h2>我们是谁</h2><p>社区成立于 2017 年，现在有三百多位群成员，覆盖闵行和徐汇两个校区，本科生、研究生都有。社团干部、赛事组和解说导播组的同学都是志愿者。</p>"
            "<h2>平时做什么</h2><ul>"
            "<li><b>每周内战</b>：周三、周五晚上各一场，按段位平衡分队，打完还有复盘</li>"
            "<li><b>校内杯</b>：春秋两季各一届，决赛在菁菁堂线下观赛</li>"
            "<li><b>新生杯</b>：每年秋天专门给新同学的比赛，以老带新</li>"
            "<li><b>线下活动</b>：观赛、聚餐、开黑夜，偶尔和兄弟院校打友谊赛</li></ul>"
            "<h2>怎么加入</h2><ol><li>在本站注册账号，补上游戏 ID 和联系方式</li><li>加入社团 QQ 群，群名片改成「昵称-年级」</li><li>想参加比赛的话，去「战队」页找正在招募的队伍，或者报名新生杯</li></ol><p>不需要面试，也不看段位。</p>"
            "<h2>干事招募</h2><p>赛事组、宣传组、解说导播组和技术组都在招人。赛事组负责排赛程、审报名；宣传组做海报和推送；解说导播组负责比赛直播；技术组维护这个网站。有兴趣的同学在群里私聊我就行。</p>"
        ), quote("打游戏最开心的，是有一群人一起打。", "林间小鹿")],
    ),
    dict(
        slug="scrim-rules-update", category="notice", author=2, when=at(9, 22, 20),
        title="内战报名规则调整说明",
        summary="从十月起，角色限定内战要求勾选的每个位置都填了段位。",
        body=[para(
            "<p>为了让角色限定内战分队更均衡，从十月起内战报名的规则有几处调整，在这里统一说明。</p>"
            "<h2>改了什么</h2><ol><li>角色限定内战（5v5、6v6）报名时，勾选的每个位置都要在所选游戏 ID 上填了段位</li><li>同一个人只能用一个游戏 ID 报名，报名后可以在开打前修改</li><li>报名截止时间统一为开打前两小时，截止后的变动请直接联系内战管理员</li></ol>"
            "<h2>为什么要改</h2><p>分队算法按每个位置的段位来平衡两边。之前不少同学勾了三个位置，却只填了一个位置的段位，算法只能按「未定级」处理，结果经常一边坦克是大师、另一边坦克是白金。九月第三周那场打得那么胶着，就是因为大家的段位都填全了。</p>"
            "<h2>没有定级怎么办</h2><p>某个位置这赛季还没定级，可以先填上赛季的段位，或者填你自己估计的水平，管理员分队时会再看一眼。实在不确定，就先只勾已经定级的位置。</p>"
            "<h2>其他不变的</h2><p>不限位置的内战不受影响，不填段位也能报名。迟到超过十分钟、或者报名了没来又没请假的，下一场会排在替补。</p>"
        )],
    ),
    dict(
        slug="autumn-cup-2026-open", category="event-notice", author=3, when=at(9, 20, 18),
        title="2026 秋季校内杯报名开启",
        summary="报名截止 10 月 15 日，比赛 10 月 25 日开打。本届整队报名，队长在赛事页一次报好全队。",
        body=[para(
            "<p>一年一度的秋季校内杯来了！今年依旧是 5v5 角色限定，小组赛加单败淘汰，决赛回到菁菁堂线下观赛。</p>"
            "<h2>时间安排</h2><ul><li>报名：9 月 20 日 – 10 月 15 日</li><li>抽签分组：10 月 18 日晚</li><li>小组赛：10 月 25 日 – 26 日</li><li>淘汰赛：11 月 1 日 – 2 日</li><li>决赛：11 月 9 日下午，菁菁堂</li></ul>"
            "<h2>怎么报名</h2><p>本届是<b>整队报名</b>：队长在赛事页选择自己的战队，勾选上场的 5 到 6 名队员和他们用的游戏 ID，提交后全队直接进入名单，队员不需要再确认，会收到一封通知邮件。报名提交后赛事组会在三天内审核。</p>"
            "<h2>没有战队怎么办</h2><p>可以去「战队」页看看正在招募的队伍，很多队伍都写了缺哪个位置；也可以自己拉人建一支新战队。2026 级的新同学更推荐参加新生杯，那边是个人报名，赛事组帮忙编队。</p>"
            "<h2>奖励</h2><p>冠军队伍获得社团定制队服和奖杯，前四名都有纪念品。决赛当天还有现场抽奖。</p>"
        )],
    ),
    dict(
        slug="freshman-cup-2026-preview", category="event-notice", author=3, when=at(9, 28, 19),
        title="新生杯 10 月 1 日开放报名：一个人也能报",
        summary="面向 2026 级新生，个人报名，赛事组按位置和段位编队，以老带新。",
        body=[para(
            "<p>2026 新生杯从 10 月 1 日开始接受报名，报名截止到 10 月 31 日，11 月 8 日开赛。</p>"
            "<h2>谁能报名</h2><p>2026 级的交大同学都可以报名，本科生、研究生都算。每支队伍里至少要有 3 名 2026 级新生，剩下的位置由老生带队，所以高年级同学也欢迎来当「带队老生」。</p>"
            "<h2>个人报名怎么操作</h2><ol><li>在个人中心填好游戏 ID 和联系方式</li><li>打开新生杯的赛事页，点「个人报名」</li><li>选一个游戏 ID，勾选你能打的位置（可以多选）</li></ol><p>报名后可以随时修改位置，直到被编入队伍为止。</p>"
            "<h2>怎么编队</h2><p>报名截止后，赛事组会按位置和段位把大家编成实力接近的队伍，每队尽量是一坦两输出两辅助，再配一名替补。编好后每个人都会收到邮件，告诉你队友是谁。</p>"
            "<h2>为什么要以老带新</h2><p>很多新同学只打过快速，第一次打比赛会紧张。每支队伍配一位有比赛经验的老生，帮忙安排训练、讲讲基本的沟通和地图思路。去年新生杯的不少选手，今年已经是校内杯的主力了。</p>"
        )],
    ),
    dict(
        slug="spring-cup-final-time", category="event-notice", author=3, when=at(4, 1, 12),
        title="春季杯决赛时间确定",
        summary="决赛定在 4 月 12 日下午一点，菁菁堂线下观赛。",
        body=[para(
            "<p>经过三周的循环赛，春季校内杯的决赛对阵已经出炉：<b>交大龙骑</b>对阵<b>思源电竞</b>。</p>"
            "<h2>时间和地点</h2><ul><li>时间：4 月 12 日（周日）下午 1 点开始，预计 5 点结束</li><li>地点：菁菁堂</li><li>赛制：BO5，每局由上一局输方选图</li></ul>"
            "<h2>现场观赛须知</h2><p>现场座位约 200 个，先到先坐，12 点半开始入场。现场有应援棒和小零食，比赛间隙有抽奖。请不要在观众席外放手机声音，以免影响选手。</p>"
            "<h2>线上直播</h2><p>没法到场的同学可以看 B 站直播，直播间 12 点 45 分开播，解说是天使降临和林间小鹿。</p>"
            "<h2>招募志愿者</h2><p>决赛当天需要 6 位志愿者帮忙签到、引导和维持秩序，有意向的同学在本文下面留言或者私聊我。</p>"
        )],
    ),
    dict(
        slug="tank-tier-new-season", category="guide", author=14, when=at(9, 15, 21),
        title="新赛季坦克英雄强度浅析",
        summary="版本更新后坦克位的变化，以及校内比赛里常见的阵容。",
        body=[para(
            "<p>新赛季开始后，群里问得最多的就是「现在坦克玩什么」。这篇不排强度榜，只聊在校内比赛这个水平（大多数是白金到大师）里，什么坦克好用、为什么好用。</p>"
            "<h2>5v5 里的坦克是做什么的</h2><p>5v5 只有一个坦克，你就是全队的前排和空间。坦克的任务可以概括成三件事：替队伍站住位置、给队友创造打输出的角度、在团战里吸收对面的技能。能把这三件事做好的英雄就是好坦克，和版本强弱关系没那么大。</p>"
            "<h2>适合校内比赛的几类坦克</h2>"
            "<h3>阵地型：莱因哈特、拉玛刹</h3><p>适合配合好、喜欢正面推进的队伍。缺点是怕被风筝，需要辅助和输出跟得上。</p>"
            "<h3>突进型：温斯顿、D.Va、破坏球</h3><p>适合个人能力强、沟通清楚的队伍。突进打的是「同时进场」，队友跟不上就会变成一个人送。</p>"
            "<h3>远程型：西格玛、奥丽莎</h3><p>上手相对容易，站得住、打得远，校内比赛里出场率一直很高，特别适合新组的队伍。</p>"
            "<h2>校内比赛常见的阵容</h2><p>春季杯七场比赛里，出场最多的是西格玛和莱因哈特，其次是 D.Va。前两名的队伍都至少准备了两套风格不同的坦克。</p>"
            "<h2>给坦克新人的建议</h2><ol><li>先练一个阵地型、一个远程型，覆盖大部分地图</li><li>开团之前看一眼辅助在哪，不要一个人冲</li><li>学会在掩体后面等技能冷却，「活着」本身就是在给队伍创造价值</li></ol>"
        )],
    ),
    dict(
        slug="support-positioning", category="guide", author=15, when=at(9, 18, 21),
        title="辅助的站位与大招资源管理",
        summary="辅助玩家最容易被忽略的两件事：站在哪里，以及什么时候交大招。",
        body=[para(
            "<p>辅助玩家常被说「奶量够了还是输」。其实很多团战输掉，不是因为治疗不够，而是辅助站错了位置，或者大招交得不是时候。</p>"
            "<h2>站位的三条原则</h2><ol><li><b>能看到队友，也能找到掩体</b>：站在能同时看到前排和输出的位置，旁边要有能躲的墙</li><li><b>和另一个辅助拉开</b>：两个辅助站在一起，对面一个突进就能同时打到两人</li><li><b>跟着坦克移动，而不是跟着人群</b>：坦克推进时你往前补位，坦克后撤时你先撤</li></ol>"
            "<h2>大招是团队的资源</h2><p>辅助的大招往往决定一波团战。建议每次团战前在语音里报一下自己的大招状态，比如「我有大了」「大招 80%」。对面先交关键大招时再交反制大招，不要一开团就把大招用掉。</p>"
            "<h2>什么时候该打输出</h2><p>队友都满血、没人受到压力时，辅助就该帮忙打伤害。安娜的睡针、巴蒂斯特的开火、禅雅塔的球，都是很可观的输出。把「空闲时间」用起来，比站在后面等更有用。</p>"
            "<h2>怎么练</h2><p>看自己的录像时，专门盯一件事：每次死亡前三秒自己站在哪里。连续看五场，大概就能找到自己最常犯的站位错误。</p>"
        ), quote("好的辅助不是奶得最多的那个，是死得最少的那个。", "安娜的猫")],
    ),
    dict(
        slug="scrim-review-sep-week3", category="match-report", author=38, when=at(9, 20, 11),
        title="九月第三周内战回顾",
        summary="十个人打了五张图，两边按小局算只差 3 分，打得非常胶着。",
        body=[para(
            "<p>九月第三周的周五夜内战，十二个人报名、十个人上场，打了五张图，最后两边按小局算只差 3 分，是这学期最胶着的一场。</p>"
            "<h2>分队</h2><p>这次报名的同学段位都填得很全，分队算法给出的两边平均分几乎一样：红队坦克是骑士，蓝队坦克是雾岛，输出和辅助的段位也几乎对等。开打前大家都觉得红队稍占优，结果完全不是这样。</p>"
            "<h2>五张图</h2><ol><li>控制图：蓝队 2:1，第三小局最后十秒的反推非常精彩</li><li>护送图：红队守住了最后一个点</li><li>推进图：蓝队靠一波四杀拿下</li><li>混合图：红队推满，蓝队差一米</li><li>闪点图：红队 3:2 险胜</li></ol>"
            "<h2>本场最佳</h2><p>大家投票选出的 MVP 是 Moira：推进图那波四杀就是 Moira 用莫伊拉打出来的，全场治疗量也是第一。</p>"
            "<h2>下周</h2><p>下周五照常开打，七点五十进语音频道。报名时请把每个位置的段位填全，分队会更准。</p>"
        )],
    ),
    dict(
        slug="dps-climb-notes", category="experience", author=22, when=at(9, 25, 22),
        title="从白金到大师：一个输出位的上分笔记",
        summary="一个赛季从白金打到大师，我做对了哪几件事。",
        body=[para(
            "<p>上赛季我从白金 3 打到了大师 5，用了差不多两个月。这篇不讲操作技巧，只记下我觉得真正起作用的几件事，给同样卡在白金钻石的输出玩家参考。</p>"
            "<h2>先找到自己最大的问题</h2><p>我一开始以为是枪法不够，天天泡在训练场。后来看录像才发现，我一大半的死亡都发生在团战开始前：站得太靠前、被对面的黑百合一枪带走。问题不是枪法，是位置。</p>"
            "<h2>把英雄池缩小</h2><p>白金的时候我什么都玩。后来只留下三个：士兵：76、卡西迪、索杰恩，两个稳定输出加一个高爆发。英雄少了，对每张图该站哪、什么时候该进场就熟了。</p>"
            "<h2>每天看一局录像</h2><p>只看自己输掉的团战，每次死亡暂停，问自己三个问题：我为什么在这里？我是不是第一个死的？如果不死，这波团能不能打赢？坚持两周，明显感觉到「不该死的死亡」少了。</p>"
            "<h2>心态</h2><p>连输两把就下线。连败的时候往往在硬撑，越打越急、越急越输。第二天再打，状态完全不一样。</p>"
            "<h2>最后</h2><p>上分没有捷径，但有方向。先弄清楚自己输在哪，再去练。欢迎在评论区交流你们的心得。</p>"
        )],
    ),
    dict(
        slug="first-time-captain", category="experience", author=10, when=at(9, 29, 21),
        title="第一次当队长，我学到了什么",
        summary="从组队、排训练到报名比赛，当队长比我想的要累，也更有意思。",
        body=[para(
            "<p>今年春天，社团几个干部想组一支娱乐向的战队参加校内杯，叫我当队长。我原本以为队长就是「报名的那个人」，半年下来才发现，这活比我想的要累，也更有意思。</p>"
            "<h2>组队：先想清楚要什么样的队</h2><p>一开始我们只想着找段位高的人，结果凑出来五个输出玩家。后来定了一个原则：先保证每个位置有人愿意长期打，再看段位。现在队里一坦、两输出、两辅助，再加一个能补位的替补，稳定多了。</p>"
            "<h2>排训练：时间比内容难</h2><p>六个人的课表完全不一样。我们最后固定了每周二、四晚上九点到十一点，谁来不了提前在群里说。训练内容很简单：先打两局内战热身，再找一支队约练习赛，打完一起看一局录像。</p>"
            "<h2>报名比赛</h2><p>秋季杯是整队报名，我在赛事页选好队员和每个人用的游戏 ID，一次就报完了，队员收到邮件就知道自己在名单里。比以前用问卷报名方便太多。</p>"
            "<h2>输了以后</h2><p>第一次打练习赛 0:3 输了，大家都很沮丧。那天我们没急着复盘，而是一起去吃了顿夜宵。第二天再看录像，问题就看得很清楚了。当队长最重要的不是指挥得多好，而是让大家愿意下周继续来。</p>"
        )],
    ),
    dict(
        slug="push-map-guide", category="guide", author=7, when=at(10, 1, 15),
        title="地图机制速查：推进图怎么打",
        summary="推进图的节奏和其他模式很不一样，整理了几条校内比赛里最常见的错误。",
        body=[para(
            "<p>推进图（新皇后街、斗兽场、埃斯佩兰萨、鲁纳萨匹）在校内比赛里出场率越来越高，但很多队伍还在用打护送图的思路打推进，吃了不少亏。整理了几条最常见的错误。</p>"
            "<h2>先搞清楚规则</h2><p>推进图中间有一台机器人，哪边的人站在它旁边，它就往对面推一面障碍墙。比赛结束时推得更远的一方获胜；有一方推到终点就直接获胜。机器人换边时要先走回中间，所以「推得远」比「抢到机器人」更重要。</p>"
            "<h2>最常见的三个错误</h2><ol><li><b>全员围着机器人</b>：机器人周围是开阔地，五个人挤在一起很容易被一波大招带走。一两个人推车，其他人去前面抢高点、拿视野</li><li><b>赢了团战不推</b>：团战赢了以后很多人去追残血，机器人却停着不动。赢了团战，第一件事是让机器人动起来</li><li><b>不看复活时间</b>：对面刚死两个人时，是推进距离最多的窗口；自己这边少人时，宁可放掉几米也不要一个个送</li></ol>"
            "<h2>开局怎么抢机器人</h2><p>开局机器人在地图正中间，两边距离一样。突进阵容可以第一时间压上去抢，阵地阵容更适合先占住机器人前进路线上的高点，等对面来推时再打。</p>"
            "<h2>加时</h2><p>只要机器人还在动，比赛就不会结束。最后几秒哪怕只剩一个人，也要贴着机器人。</p>"
        )],
    ),
    # New ones.
    dict(
        slug="newbie-guide", category="guide", author=1, when=at(9, 5, 21),
        title="新手入门：第一次打守望先锋该知道的几件事",
        summary="从选位置到听懂语音里的黑话，给刚入坑的同学一份不那么长的入门指南。",
        body=[para(
            "<p>每年都有不少同学因为社团的内战第一次接触守望先锋。这篇写给完全没玩过、或者只打过几局快速的同学。</p>"
            "<h2>先选一个位置</h2><p>守望先锋的英雄分成坦克、输出、支援三类。5v5 的比赛里每队一个坦克、两个输出、两个支援。刚开始不用三个位置都学，挑一个你最喜欢的就好。拿不准的话，支援是很好的起点：能帮到队友，也不用一开始就和对面对枪。</p>"
            "<h2>推荐的入门英雄</h2><ul><li>坦克：莱因哈特、奥丽莎（站得住，技能直观）</li><li>输出：士兵：76、卡西迪（操作简单，练枪法）</li><li>支援：天使、卢西奥（容易上手，能学会看全队血量）</li></ul>"
            "<h2>几个常用的词</h2><ul><li><b>开团</b>：主动发起一波团战</li><li><b>集火</b>：大家一起打同一个目标</li><li><b>大招</b>：每个英雄的终极技能</li><li><b>拉扯</b>：在掩体之间来回走位，消耗对面</li><li><b>人数差</b>：对面有人阵亡、我方人多的那几秒</li></ul>"
            "<h2>怎么开始</h2><ol><li>先打几局训练模式和快速，熟悉操作</li><li>在本站注册，报名一场「新人友好场」内战</li><li>打完别急着下线，在群里问问老玩家刚才哪里可以做得更好</li></ol>"
            "<p>最重要的一条：打得开心。输赢是常事，社团里没人会因为你打得不好而说什么。</p>"
        )],
    ),
    dict(
        slug="replay-review", category="guide", author=11, when=at(9, 8, 20),
        title="怎么看自己的录像复盘",
        summary="游戏里自带的回放很好用，关键是知道该看什么。",
        body=[para(
            "<p>守望先锋自带回放功能，最近打过的比赛都能在生涯概况的回放里找到。很多人知道这个功能，但不知道该怎么看。</p>"
            "<h2>只看输掉的团战</h2><p>一局比赛有十几波团战，全看太累。只挑输掉的那几波，从团战开始前十秒看起。</p>"
            "<h2>盯住三个时刻</h2><ol><li><b>第一个死的是谁，为什么</b>：团战输掉，往往是因为有人先掉了</li><li><b>大招是怎么交的</b>：是不是一开团就交了，对面的反制大招还在</li><li><b>撤退的时机</b>：明显打不过的时候，是不是有人还在硬打</li></ol>"
            "<h2>切换视角</h2><p>回放里可以切到对面任何一个人的第一人称视角。看看对面是怎么看到你的、从哪个角度打你的，比看自己的视角收获更多。</p>"
            "<h2>和队友一起看</h2><p>战队训练时，我们每周挑一局一起看，每个人说一件自己可以做得更好的事。不追究责任，只找问题。</p>"
        )],
    ),
    dict(
        slug="grad-balance", category="experience", author=19, when=at(9, 12, 23),
        title="研一新生：怎么在科研和训练之间找平衡",
        summary="进实验室的第一个月，我差点退出战队。后来想通了几件事。",
        body=[para(
            "<p>九月进了实验室，课、组会、读论文一下子把时间塞满了。第一个月我连着三周没去训练，一度想退出思源电竞。后来和队长、导师都聊了聊，慢慢找到了节奏。</p>"
            "<h2>把训练当成固定日程</h2><p>以前是「有空就打」，结果永远没空。现在我把每周两次训练写进日历，和组会一样对待，到点上线，打完下线，不拖到凌晨。</p>"
            "<h2>和导师说清楚</h2><p>我原本很担心导师觉得打游戏不务正业。没想到导师说只要进度不落下，周末参加比赛完全没问题，还问我们比赛有没有直播。</p>"
            "<h2>降低对自己的要求</h2><p>研究生阶段没法像本科时一天打五六个小时。我接受了段位可能会掉一点，把目标从「上英杰」改成「比赛时不拖后腿」，压力小了很多。</p>"
            "<h2>队友很重要</h2><p>思源电竞大部分队员都是研究生，大家时间都紧，所以训练都很高效。有人赶论文缺席，替补就顶上，没人抱怨。能有一群理解你的队友，是坚持下来的最大原因。</p>"
        )],
    ),
    dict(
        slug="callouts", category="guide", author=9, when=at(9, 27, 22),
        title="语音沟通：报点报什么、怎么报",
        summary="好的沟通能抵半个段位。报点要短、要准，还要知道什么时候安静。",
        body=[para(
            "<p>打内战和比赛时，语音里经常出现两种情况：要么没人说话，要么所有人同时说话。这篇整理一下语音里到底该说什么。</p>"
            "<h2>报点的三个要素</h2><p>一句好的报点包含<b>谁</b>、<b>在哪</b>、<b>什么状态</b>。比如「源氏在左边高台，残血」，比「那边有人」有用得多。</p>"
            "<h2>最值得报的几件事</h2><ol><li>击杀和阵亡：「秒了安娜」「我死了，后撤」</li><li>大招状态：「我有大」「对面莱因哈特大招好了」</li><li>关键技能：「对面安娜睡针交了」「卢西奥音障没了」</li><li>侧翼：「黑影从后面绕过来」</li></ol>"
            "<h2>什么时候该安静</h2><p>团战进行中，语音里最好只有短句和报点。复盘、抱怨、讨论下一波怎么打，都留到团战结束、大家在复活的时候再说。</p>"
            "<h2>指挥只要一个人</h2><p>同一时间只能有一个人决定「打」还是「撤」。一般是坦克或者视野最好的辅助来指挥，其他人可以提建议，但最后听一个人的。</p>"
            "<h2>给新人的建议</h2><p>不知道说什么的话，就先只报两件事：自己死了，以及看到对面的侧翼。这两件事说清楚，已经比大多数路人局好了。</p>"
        )],
    ),
    dict(
        slug="mid-autumn-scrim", category="match-report", author=37, when=at(9, 26, 11),
        title="中秋内战回顾：月饼与五连胜",
        summary="中秋节晚上十个人不限位置打了五局，蓝队一局没丢。打完一起在群里抢月饼券。",
        body=[para(
            "<p>中秋节晚上，十位留校的同学来打了一场不限位置的内战，打完一起在群里抢了月饼券。</p>"
            "<h2>阵容</h2><p>不限位置的内战，大家都玩起了平时不太碰的英雄：坦克专精的骑士玩了一晚上的半藏，辅助玩家咩咩拿起了黑百合。</p>"
            "<h2>五局比赛</h2><p>蓝队从第一局开始就打得非常顺，五局全胜。关键人物是糖豆：五局用了四个不同的英雄，每局都是全场击杀最多。红队在第四局最接近翻盘，可惜最后一波团战被卢西奥的音障挡住了。</p>"
            "<h2>花絮</h2><ul><li>第三局双方同时选了五个源氏，打成了「源氏大战」</li><li>有人在最后一局用莱因哈特冲锋撞下了地图，全场语音笑了半分钟</li><li>打完以后红队要求「下次重新分队」，被管理员驳回</li></ul>"
            "<h2>下一场</h2><p>国庆期间还有一场 6v6 怀旧场，不限位置，留校的同学可以来玩。</p>"
        )],
    ),
    dict(
        slug="autumn-cup-casters", category="event-notice", author=3, when=at(9, 30, 19), tournament="2026 秋季校内杯",
        title="秋季校内杯招募解说和导播",
        summary="想试试解说比赛、或者对直播技术感兴趣？秋季杯的解说导播组正在招人。",
        body=[para(
            "<p>秋季校内杯会全程在 B 站直播，解说导播组需要更多同学加入。没有经验也没关系，比赛前会安排两次练习。</p>"
            "<h2>招募岗位</h2><ul><li><b>解说</b>：负责比赛的实况和分析，一般两人一组</li><li><b>导播</b>：负责切换镜头和观战视角，熟悉观战模式会更好</li><li><b>场控</b>：负责和选手、裁判沟通，处理暂停和技术问题</li></ul>"
            "<h2>时间投入</h2><p>小组赛和淘汰赛都在周末，每人每天最多排两场。比赛前有两次线上练习，分别在 10 月 19 日和 10 月 22 日晚上。</p>"
            "<h2>怎么报名</h2><p>在本文下面留言，或者在群里私聊我，说一下想做哪个岗位、平时看不看比赛。解说岗位请附上一段一分钟左右的试音，随便解说一段比赛录像就行。</p>"
        ), quote("解说最难的不是说，是知道什么时候不说。", "天使降临")],
    ),
    dict(
        slug="october-schedule", category="notice", author=1, when=at(10, 2, 10),
        title="十月社团活动安排",
        summary="国庆 6v6 怀旧场、每周内战、新人友好场和秋季杯抽签，十月的活动都在这里。",
        body=[para(
            "<p>十月活动比较多，统一列在这里，具体时间以各活动页面为准。</p>"
            "<h2>内战</h2><ul><li>10 月 5 日（周一，国庆假期）晚上：国庆特别场 · 6v6 怀旧，不限位置</li><li>每周三晚上八点：周三内战，6v6 角色限定</li><li>每周五晚上八点：周五夜内战，5v5 角色限定</li><li>10 月 11 日（周日）下午三点：新人友好场，欢迎第一次参加的同学</li></ul>"
            "<h2>赛事</h2><ul><li>秋季校内杯报名截止：10 月 15 日</li><li>秋季校内杯抽签：10 月 18 日晚，B 站直播</li><li>秋季校内杯小组赛：10 月 25 日 – 26 日</li><li>新生杯报名：进行中，截止 10 月 31 日</li></ul>"
            "<h2>线下</h2><p>10 月 18 日抽签那天晚上，在闵行校区学生中心有一场观赛聚会，一起看抽签、吃夜宵。名额 30 人，报名方式会在群里通知。</p>"
            "<h2>干事例会</h2><p>各组干事 10 月 8 日晚上九点线上例会，讨论秋季杯的分工。</p>"
        )],
    ),
    dict(
        slug="caster-diary", category="experience", author=13, when=at(6, 20, 20),
        title="当了一学期解说，我想说的",
        summary="从第一次开麦说不出话，到决赛解说五局，聊聊解说这件事。",
        body=[para(
            "<p>春季杯是我第一次当解说。从循环赛第一场开麦时紧张得说不出话，到决赛解说了整整五局，这一学期收获很多，写下来留个纪念。</p>"
            "<h2>第一场</h2><p>第一场我准备了满满一页稿子，结果比赛一开始就全忘了。搭档林间小鹿很淡定，一直在接我的话。赛后看回放，我说得最多的一句是「哇」。</p>"
            "<h2>做准备比临场重要</h2><p>后来我每场比赛前都会做三件事：看两支队伍上一场的录像，记下每个选手的常用英雄，准备几句介绍战队的话。准备充分，临场就不慌。</p>"
            "<h2>给搭档留空间</h2><p>两个人解说，最怕的是抢话。我们约定：一个人负责实况（谁在打谁、谁死了），另一个人负责分析（为什么这样打、接下来会怎样），团战时只有负责实况的人说话。</p>"
            "<h2>决赛那一箭</h2><p>决胜局最后那一箭，我只来得及喊出半句「半藏——」，现场就已经沸腾了。那一刻觉得，解说就是陪大家一起见证这些瞬间。</p>"
            "<h2>欢迎加入</h2><p>秋季杯解说组在招人，有兴趣的同学欢迎来试试。</p>"
        )],
    ),
]

# The spring final keeps its picture and quote; only the text grows.
FINAL_TEXT = [
    para(
        "<p>4 月 12 日下午，春季校内杯决赛在菁菁堂打响，现场来了八十多位观众，直播间同时在线最高到了 600 多人。</p>"
        "<h2>赛前</h2><p>交大龙骑是上届冠军，循环赛三战全胜；思源电竞以研究生为主，打法以运营见长。赛前不少观众认为龙骑的个人能力更强，但思源的配合更稳定。</p>"
        "<h2>前四局</h2><p>第一局控制图，思源电竞靠扎实的阵地战先下一城。第二局龙骑换上突进阵容，闪光弹的猎空连续切掉对面后排，扳回一局。第三、四局双方各取一局，比分来到 2:2。</p>"
        "<h2>决胜局</h2><p>决胜局是推进图。思源一度推到龙骑的最后一段，龙骑在加时阶段打出一波漂亮的团战：半藏の弓一箭带走对面双辅助，残局里盾墙的莱因哈特护住机器人，完成翻盘。</p>"
    ),
    "IMAGE",
    "QUOTE",
    para(
        "<h2>赛后</h2><p>这是交大龙骑的第二座校内杯冠军。思源电竞的队长夜猫子赛后说，秋季杯还会再来。感谢所有参赛队伍，感谢解说、导播和志愿者同学，也感谢来到现场的每一位观众。</p>"
    ),
]


def article_body(raw_blocks):
    return json.dumps(raw_blocks, ensure_ascii=False)


news = ArticleIndexPage.objects.get(slug="news")
created = updated = 0
for spec in ARTICLES:
    author = u(spec["author"])
    page = ArticlePage.objects.filter(slug=spec["slug"]).first()
    fields = dict(
        title=spec["title"],
        summary=spec["summary"],
        category=ArticleCategory.objects.get(slug=spec["category"]),
        body=article_body(spec["body"]),
    )
    if spec.get("tournament"):
        fields["tournament"] = Tournament.objects.get(title=spec["tournament"])
    if page is None:
        page = ArticlePage(slug=spec["slug"], author=author, owner=author, **fields)
        news.add_child(instance=page)
        created += 1
    else:
        for name, value in fields.items():
            setattr(page, name, value)
        updated += 1
    page.save_revision(user=author).publish()
    ArticlePage.objects.filter(pk=page.pk).update(
        first_published_at=spec["when"],
        last_published_at=spec["when"],
        latest_revision_created_at=spec["when"],
    )

final = ArticlePage.objects.get(slug="spring-cup-final-report")
old = {block.block_type: block for block in final.body}
raw = []
for item in FINAL_TEXT:
    if item == "IMAGE":
        raw.append({"type": "image", "value": {"image": old["image"].value["image"].pk, "caption": old["image"].value["caption"]}})
    elif item == "QUOTE":
        raw.append({"type": "quote", "value": {"text": old["quote"].value["text"], "attribution": old["quote"].value["attribution"]}})
    else:
        raw.append(item)
if "赛后" not in str(final.body):
    final.body = article_body(raw)
    final.save_revision(user=final.author).publish()
first = at(4, 13, 10)
ArticlePage.objects.filter(pk=final.pk).update(
    first_published_at=first, last_published_at=first, latest_revision_created_at=first
)
print("articles created", created, "updated", updated + 1, "| total", ArticlePage.objects.live().count())

# --- comments ----------------------------------------------------------------------

# Old replies said the autumn cup takes individuals; since 093 it takes teams only.
FIXES = {
    "没有战队可以个人报名吗？": "没有战队的话怎么办？",
    "可以的，赛事页有「个人报名」，截止后我们统一编队。": "秋季杯这次是整队报名。可以去「战队」页找正在招募的队伍；新同学也可以报新生杯，那边是个人报名。",
    "好的谢谢！已经报了。": "好的，我去战队页看看！",
}
for before, after in FIXES.items():
    Comment.objects.filter(body=before).update(body=after)

COMMENTS = {
    "site-launch": [
        (24, "终于不用在群公告里翻报名链接了！", 6, [(20, "以后报名都在网站上，群里只发提醒。")]),
        (34, "手机上看也很方便，赞一个。", 3, []),
        (31, "校外的同学也能注册吗？", 2, [(20, "可以的，用任意邮箱注册，只是有些赛事仅限交大同学。")]),
    ],
    "recruitment-2026": [
        (40, "技术组还缺人吗？会一点 Python。", 4, [(1, "缺！私聊我～")]),
        (36, "白银也可以来吗？", 5, [(1, "当然可以，不看段位。"), (2, "内战按段位分队，白银也能打得很开心。")]),
    ],
    "scrim-rules-update": [
        (16, "支持，上次分队确实有点不平衡。", 7, []),
        (39, "没定级的位置能不能先不勾？", 3, [(2, "可以，只勾定级了的位置就行。")]),
    ],
    "autumn-cup-2026-open": [
        (18, "抽签有直播吗？", 4, [(3, "有，10 月 18 日晚上 B 站直播。")]),
    ],
    "freshman-cup-2026-preview": [
        (28, "已报名！希望能分到一个靠谱的队伍。", 5, [(3, "放心，每队都会配一位有经验的老生。")]),
        (32, "大二能报吗？", 2, [(3, "新生杯只收 2026 级新生，大二可以来当带队的老生哦。")]),
    ],
    "tank-tier-new-season": [
        (27, "莱因哈特永远的神！", 8, [(14, "锤哥稳住，我们能赢。")]),
        (33, "远程坦克确实适合新队伍，我们队一开始就是西格玛起家。", 3, []),
    ],
    "support-positioning": [
        (6, "「和另一个辅助拉开」这条太真实了，经常被一起切掉。", 6, []),
        (23, "大招报状态这个好，下次内战试试。", 2, [(15, "试试看，效果很明显。")]),
    ],
    "spring-cup-final-report": [
        (25, "现场看太燃了，秋季杯还去。", 4, []),
    ],
    "scrim-review-sep-week3": [
        (40, "谢谢大家投票！那波四杀纯属运气。", 9, [(38, "谦虚了，全场治疗量第一。")]),
        (12, "下周还要来。", 1, []),
    ],
    "dps-climb-notes": [
        (8, "把英雄池缩小这条，我也是这样上来的。", 4, []),
    ],
    "first-time-captain": [
        (29, "吃夜宵那段好有画面感。", 5, []),
        (17, "队长辛苦了！", 3, [(10, "不辛苦，下周二见。")]),
    ],
    "push-map-guide": [
        (19, "赢了团战不推这条，说的就是我们队。", 6, [(7, "哈哈，下次赢了先推车。")]),
        (21, "加时那条学到了。", 2, []),
    ],
    "newbie-guide": [
        (35, "刚入坑，这篇太有用了。", 3, [(1, "欢迎！周日下午有新人友好场，可以来玩。")]),
    ],
    "callouts": [
        (26, "「指挥只要一个人」太重要了。", 5, []),
        (4, "下次内战我就只报死亡和侧翼，从简单的开始。", 2, []),
    ],
    "grad-balance": [
        (22, "同研一，感同身受。", 4, [(19, "一起加油！")]),
    ],
    "mid-autumn-scrim": [
        (24, "四个英雄纯属乱玩哈哈。", 5, []),
        (30, "五个源氏那局我也在，太乱了。", 3, []),
    ],
    "october-schedule": [
        (37, "观赛聚会怎么报名？", 2, [(1, "下周会在群里发报名表。")]),
    ],
    "autumn-cup-casters": [
        (38, "导播需要什么设备吗？", 1, [(3, "不需要，用社团的直播电脑。")]),
        (13, "欢迎大家来，解说真的很好玩！", 4, []),
    ],
    "caster-diary": [
        (9, "那个「哇」我到现在都记得。", 7, [(13, "不许再提了！")]),
    ],
    "replay-review": [
        (5, "切对面视角这个技巧太好用了。", 3, []),
    ],
}

everyone = list(User.objects.filter(is_active=True).values_list("pk", flat=True))


def stamp(comment, when):
    Comment.objects.filter(pk=comment.pk).update(created_at=min(when, NOW))


def like(comment, count):
    likers = [pk for pk in everyone if pk != comment.author_id]
    rng.shuffle(likers)
    for pk in likers[:count]:
        CommentLike.objects.get_or_create(comment=comment, user_id=pk)
    Comment.objects.filter(pk=comment.pk).update(
        like_count=CommentLike.objects.filter(comment=comment).count()
    )


added = 0
for slug, threads in COMMENTS.items():
    page = ArticlePage.objects.get(slug=slug)
    when = page.first_published_at
    for author_pk, body, likes, replies in threads:
        when = when + timedelta(hours=rng.randint(2, 20), minutes=rng.randint(0, 59))
        top = Comment.objects.filter(page=page, author_id=author_pk, body=body).first()
        if top is None:
            top = comment_services.create(page=page, author=u(author_pk), body=body)
            stamp(top, when)
            like(top, likes)
            added += 1
        reply_when = when
        for reply_pk, reply_body in replies:
            reply_when = reply_when + timedelta(minutes=rng.randint(20, 300))
            if not Comment.objects.filter(page=page, author_id=reply_pk, body=reply_body).exists():
                reply = comment_services.create(page=page, author=u(reply_pk), body=reply_body, parent=top)
                stamp(reply, reply_when)
                like(reply, rng.randint(0, 3))
                added += 1
print("comments added", added, "| total", Comment.objects.count())

# --- tournaments -------------------------------------------------------------------

TOURNAMENTS = {
    "2026 秋季校内杯": dict(
        summary="交大守望先锋社区秋季赛：5v5 角色限定，小组赛加单败淘汰，决赛线下观赛。本届整队报名。",
        description=(
            "<h2>赛程</h2><ul><li>报名：9 月 20 日 – 10 月 15 日</li><li>抽签分组：10 月 18 日晚，B 站直播</li><li>小组赛：10 月 25 日 – 26 日，线上</li><li>淘汰赛：11 月 1 日 – 2 日，线上</li><li>决赛：11 月 9 日下午，菁菁堂线下观赛</li></ul>"
            "<h2>赛制</h2><ul><li>5v5 角色限定，使用当前赛季竞技模式地图池</li><li>小组赛 BO3，每组前两名出线；淘汰赛 BO5，决赛 BO7</li><li>第一张图由赛事组抽取，之后每局由上一局输方选图</li></ul>"
            "<h2>报名须知</h2><p>本届<b>整队报名</b>：队长在本页选择自己的战队，勾选 5 到 6 名上场队员和他们使用的游戏 ID，提交后全队直接进入名单，队员不需要确认，会收到通知邮件。报名提交后赛事组会在三天内审核。</p><p>同一名选手只能在一支队伍的名单里。比赛中使用的游戏 ID 必须是报名时提交的那个。</p>"
            "<h2>规则要点</h2><ol><li>每场比赛开始前 15 分钟，双方队长在赛事群里确认到齐</li><li>比赛中出现断线，每局可以暂停一次，每次不超过 5 分钟</li><li>禁止代打和使用第三方软件，一经查实取消比赛资格</li><li>对比赛结果有异议，请在比赛结束后 30 分钟内联系赛事组</li></ol>"
            "<h2>奖励</h2><p>冠军队伍获得社团定制队服和奖杯，亚军、季军和第四名获得纪念徽章。决赛现场有观众抽奖。</p>"
            "<h2>联系赛事组</h2><p>报名和赛程问题请在群里联系阿凯，或者在《2026 秋季校内杯报名开启》一文下面留言。</p>"
        ),
    ),
    "2026 新生杯": dict(
        summary="面向 2026 级新生的入门赛事，个人报名、赛事组编队，以老带新。仅限交大同学。",
        description=(
            "<h2>谁能报名</h2><p>2026 级交大同学，本科生、研究生都可以。每支队伍至少 3 名 2026 级新生，其余位置由报名带队的老生补齐。</p>"
            "<h2>怎么报名</h2><p>本届是<b>个人报名</b>：在本页点「个人报名」，选一个游戏 ID，勾选你能打的位置。报名截止后赛事组按位置和段位编队，编好会邮件通知每个人。被编入队伍之前，随时可以修改位置或取消报名。</p>"
            "<h2>赛程</h2><ul><li>报名：10 月 1 日 – 10 月 31 日</li><li>编队完成：11 月 3 日前</li><li>小组赛：11 月 8 日 – 9 日</li><li>决赛：11 月 15 日晚，线上直播</li></ul>"
            "<h2>赛制</h2><p>5v5 角色限定，小组循环赛 BO1，决赛 BO3。地图池只用控制、护送、推进三种模式，每种两张，赛前公布。</p>"
            "<h2>新生福利</h2><p>编队完成后，每支队伍会配一位有比赛经验的老生做教练，带大家打两次练习赛。参赛的新同学每人一张社团纪念贴纸。</p>"
        ),
    ),
    "2026 春季校内杯": dict(
        summary="春季校内杯四支队伍循环赛加决赛，交大龙骑 3:2 险胜思源电竞夺冠。",
        description=(
            "<h2>赛制</h2><p>5v5 角色限定。四支队伍单循环 BO3，前两名进入决赛；决赛 BO5，4 月 12 日在菁菁堂线下进行。</p>"
            "<h2>最终排名</h2><ol><li>交大龙骑（冠军）</li><li>思源电竞（亚军）</li><li>徐汇老兵</li><li>菁菁堂守望者</li></ol>"
            "<h2>决赛</h2><p>交大龙骑 3:2 思源电竞。决胜局推进图加时阶段，半藏の弓一箭带走对面双辅助，龙骑完成翻盘。完整战报见资讯《春季杯决赛战报：交大龙骑 3:2 思源电竞》。</p>"
            "<h2>个人奖项</h2><ul><li>决赛 MVP：半藏の弓</li><li>最佳坦克：盾墙</li><li>最佳辅助：夜猫子</li></ul>"
            "<h2>感谢</h2><p>感谢所有参赛队伍，感谢解说天使降临、林间小鹿，导播和志愿者同学，以及到场和在线观看的每一位观众。</p>"
        ),
    ),
    "华东高校守望先锋邀请赛": dict(
        summary="与兄弟院校联合举办的邀请赛，因档期冲突本届取消。",
        description=(
            "<p>原计划 10 月 1 日举办的华东高校守望先锋邀请赛，因合办院校的场地和档期冲突，<b>本届取消</b>。</p>"
            "<p>我们正在和兄弟院校商量明年春季重新举办，有消息会第一时间在资讯里通知。给大家添麻烦了，抱歉。</p>"
        ),
    ),
    "2026 冬季娱乐赛（筹备中）": dict(
        summary="期末考试后的娱乐赛，赛制待定。",
        description="<p>筹备中：冬季娱乐赛计划在期末考试后举办，赛制待定（候选：6v6 怀旧、限定英雄池、1v1 决斗）。</p>",
    ),
}
for title, fields in TOURNAMENTS.items():
    Tournament.objects.filter(title=title).update(**fields)
print("tournaments updated", len(TOURNAMENTS))

# --- scrims ------------------------------------------------------------------------

SCRIMS = {
    ("周五夜内战", ScrimStatus.PUBLISHED): (
        "老规矩，晚上八点开打，七点五十进语音频道（社团语音「内战 1」「内战 2」）。\n\n"
        "· 5v5 角色限定，打五张图，每张图打完换边\n"
        "· 分队结果开打前半小时发在群里，也会显示在本页\n"
        "· 报名截止到当天晚上六点，之后有变动请直接找老周\n"
        "· 迟到超过十分钟由替补顶上\n\n"
        "打完照例复盘十分钟，欢迎留下来聊。"
    ),
    ("国庆特别场 · 6v6 怀旧", ScrimStatus.PUBLISHED): (
        "国庆留校的同学一起来玩 6v6！不限位置，两坦两输出两辅助随便组，图个开心。\n\n"
        "· 晚上七点半开始，大约打到十点\n"
        "· 不限位置，报名时不用填段位\n"
        "· 开打前随机分队，每打两张图重新分一次\n"
        "· 打完在群里抽三位同学送社团周边"
    ),
    ("周三内战", ScrimStatus.PUBLISHED): (
        "6v6 角色限定，每队两坦两输出两辅助。\n\n"
        "· 晚上八点开打，打四张图\n"
        "· 报名时请把勾选位置的段位填全，分队按段位平衡\n"
        "· 报名截止到当天晚上六点\n"
        "· 人数不够 12 人时改成 5v5，会提前在群里通知"
    ),
    ("周五夜内战", ScrimStatus.FINISHED): (
        "九月第三周的内战，12 人报名、10 人上场，五张图打得非常胶着。\n\n"
        "回顾见资讯《九月第三周内战回顾》。"
    ),
    ("中秋内战", ScrimStatus.FINISHED): (
        "中秋节晚上来几把，不限位置。打完一起抢月饼券。\n\n"
        "回顾见资讯《中秋内战回顾：月饼与五连胜》。"
    ),
}
for (title, status), text in SCRIMS.items():
    Scrim.objects.filter(title=title, status=status).update(description=text)

friendly, made = Scrim.objects.get_or_create(
    title="周日下午 · 新人友好场",
    defaults=dict(
        description=(
            "专门给第一次参加内战、或者刚开始玩守望先锋的同学准备的一场。\n\n"
            "· 下午三点开始，打三到四张图，五点前结束\n"
            "· 不限位置，不看段位，想玩什么就玩什么\n"
            "· 每队会有一位老玩家，在语音里帮忙讲解\n"
            "· 第一次用语音频道的同学，两点半可以提前进来调试麦克风\n\n"
            "不用紧张，打得开心最重要。"
        ),
        starts_at=at(10, 11, 15),
        signup_closes_at=at(10, 11, 13),
        format=ScrimFormat.OPEN_5V5,
        status=ScrimStatus.PUBLISHED,
        created_by=u(2),
    ),
)
signed = 0
for pk, roles in [(35, ["support"]), (34, ["damage"]), (28, ["tank", "damage"]), (32, ["support"]), (36, ["damage", "support"]), (16, ["support"]), (1, ["tank"]), (24, ["damage"])]:
    user = u(pk)
    account = user.game_accounts.first()
    if account is None or friendly.signups.filter(user=user).exists():
        continue
    try:
        scrim_services.sign_up(scrim=friendly, user=user, game_account_id=account.pk, roles=roles)
        signed += 1
    except Exception as error:  # demo data: report and go on
        print("  signup skipped", user.nickname, error)
print("friendly scrim", "created" if made else "exists", "| signups", friendly.signups.count(), "(+%d)" % signed)

# --- people ------------------------------------------------------------------------

MOTTOS = {5: "一箭入魂", 7: "推进图爱好者", 12: "稳定发挥就是胜利", 22: "战术目镜启动", 34: "第三局才热身", 35: "夏天的辅助"}
for pk, motto in MOTTOS.items():
    user = u(pk)
    if not user.motto:
        user.motto = motto
        user.save(update_fields=["motto"])
User.objects.filter(pk=30, main_role="").update(main_role="damage")
print("mottos filled; users without motto:", User.objects.filter(motto="").count())
