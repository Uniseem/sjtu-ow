package manual

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// Step 是手册的一个步骤。
type Step struct {
	Text      string `json:"text"`
	LinkURL   string `json:"link_url,omitempty"`
	LinkLabel string `json:"link_label,omitempty"`
}

// Part 是手册的一个角色板块。
type Part struct {
	Key   string `json:"key"`
	Title string `json:"title"`
	Steps []Step `json:"steps"`
}

var ownerPart = Part{
	Key:   "owner",
	Title: "超级管理员（站长）",
	Steps: []Step{
		{
			Text:      "上线清单：后台首页下面列着还没做的配置，逐项完成。最要紧的是全站设置里的邮件（SMTP）：注册要验证邮箱，配好后点「发送测试邮件」。",
			LinkURL:   "/admin/",
			LinkLabel: "后台首页",
		},
		{
			Text:      "分配角色：「成员 → 用户与权限」里编辑某人 → 角色，勾「内容编辑」「赛事管理员」「内战管理员」或「认证作者」。各角色能做什么、按组关功能在旁边的「角色」小标签里。",
			LinkURL:   "/admin/users/",
			LinkLabel: "用户",
		},
		{
			Text: "出问题时看待办：邮件发不出去、后台任务没在运行、备份没跑或上传失败、AI 审核有内容没看成，每条都写了原因和去哪儿处理。",
		},
		{
			Text: "每天夜里服务器的定时任务会备份、清理旧数据（顺带提醒和关闭没人处理的入队申请），见 README「定时维护」。",
		},
		{
			Text:      "年审、换届总结要报的数（办了几场内战和赛事、多少人参加、新增多少成员）在「数据」，选好时间段可以下载逐场的表。",
			LinkURL:   "/admin/activity/",
			LinkLabel: "活动数据",
		},
	},
}

var contentPart = Part{
	Key:   "content",
	Title: "内容编辑",
	Steps: []Step{
		{
			Text:      "网站默认信任所有人：投稿、头像都是发了就公开，不用你先审。AI 每 30 分钟巡查一次，有可疑的会发信给站长（或全站设置里填的邮箱）。",
			LinkURL:   "/admin/",
			LinkLabel: "后台首页",
		},
		{
			Text:      "AI 巡查的记录在「审核 → 内容」，标不标处理结果都行；需要作者改的，用「要求作者修改」写一段说明发给他。文章有问题，打开它撤下或直接改。",
			LinkURL:   "/admin/moderation/",
			LinkLabel: "巡查记录",
		},
		{
			Text:      "头像：「审核 → 头像」按上传时间列出，看到不合适的就撤下（要选原因，撤下后问要不要发信告诉本人）。",
			LinkURL:   "/admin/avatars/",
			LinkLabel: "头像",
		},
		{
			Text:      "评论：在文章页上直接隐藏、恢复、置顶，也可以到「审核 → 评论」统一看，每行直接点隐藏或置顶。",
			LinkURL:   "/admin/comments/",
			LinkLabel: "评论",
		},
		{
			Text:      "发文章和群发：「内容 → 文章」右上的「写文章」，写完点「发布」。重要的公告发布后，在文章列表这一行的「通知全体成员」里群发给开着活动通知的成员。正文用 Markdown 写，工具栏点「?」看写法，图片拖进来或粘贴就上传。",
			LinkURL:   "/admin/articles/",
			LinkLabel: "文章",
		},
		{
			Text: "定时上线和下线：编辑页「网址和发布时间」一组里填定时上线（到点自动发布）或定时下线（到点自动撤下），再点「发布」。到点后半分钟内生效。要上线时同时群发，在文章列表这一行的「通知全体成员」里安排好。",
		},
		{
			Text:      "首页的置顶文章、资讯栏目的介绍、关于我们和两份协议在「内容 → 网站页面」里改；文章分类在「内容 → 分类」。",
			LinkURL:   "/admin/pages/",
			LinkLabel: "网站页面",
		},
		{
			Text:      "成员展示上的分组和职务（比如「社团干部 · 社长」）在这里维护。",
			LinkURL:   "/admin/member-groups/",
			LinkLabel: "成员分组",
		},
	},
}

var tournamentsPart = Part{
	Key:   "tournaments",
	Title: "赛事管理员",
	Steps: []Step{
		{
			Text:      "新建赛事：后台首页的「新建赛事」，或者「活动 → 赛事」右上的「新建赛事」。标题、报名开始和截止时间必填；填了比赛时间，开赛前才会自动提醒。报名方式默认是个人报名（每人自己报，你来编队），整队报名由队长为全队报。「选手联系方式」（比如选手群号）只给报了名的人看。每年都办的赛事，在去年那场的「更多 → 复制」里建，时间按整周挪到今年。详细说明用 Markdown 写，图片直接拖进来或粘贴就上传，B 站视频把链接单独贴一行。",
			LinkURL:   "/admin/tournaments/new/",
			LinkLabel: "新建赛事",
		},
		{
			Text:      "发布和通知：在赛事列表这一行的「更多 → 发布」（编辑页右侧也有）。发布确认页可以勾「同时通知全体成员」；发布后也可以在「更多 → 通知全体成员」里先看信再发。有修改可以再发，第二封起信的开头会写明之前发过几次。",
			LinkURL:   "/admin/tournaments/",
			LinkLabel: "赛事列表",
		},
		{
			Text:      "审核报名：首页待办会写有几份等你审，「审核 → 报名」标签上也写着件数；在「活动 → 赛事」列表的「待审核」一列可以直接点进那项赛事的。逐条通过或驳回（驳回要写备注），也可以勾选后一起通过。做完会问要不要给队长发信（做完事顺带的信都先问一句，可以不发）。",
			LinkURL:   "/admin/registrations/",
			LinkLabel: "报名审核",
		},
		{
			Text: "编队（个人报名的赛事）：报名截止后待办会写「有 N 人等待编队」。在赛事的「更多 → 队伍编排」里把散人拖进队伍，保存后这些队伍直接算通过，再问要不要给编进的人每人发一封信；没编进的人开赛前一天会自动收到说明。",
		},
		{
			Text: "改时间、取消：直接改比赛时间，保存不会发信，提醒按新时间重发；编辑页会提示「报名的人还不知道」，点「通知报名的人」先看信再发（可以写一段说明，信里写原来和现在的时间）。取消在「更多 → 取消赛事」，写一句原因，取消后问要不要给报了名的队长发信。",
		},
		{
			Text: "结束：打完在「更多 → 标记为已结束」；开赛 3 天还没标，待办会提醒。比赛结果写一篇战报文章，在文章里关联这项赛事，赛事页会列出来。",
		},
	},
}

var scrimsPart = Part{
	Key:   "scrims",
	Title: "内战管理员",
	Steps: []Step{
		{
			Text:      "新建内战：后台首页的「新建内战」，或者「活动 → 内战」右上的「新建内战」，选规格（角色限定或不限位置，5v5 或 6v6）和开始时间。发布时可以同时通知全体成员。每周都有的内战，在上一场的「更多 → 复制」里建，时间自动挪到下一周。说明和赛事一样用 Markdown 写，图片直接拖进来或粘贴。",
			LinkURL:   "/admin/scrims/new/",
			LinkLabel: "新建内战",
		},
		{
			Text:      "分队：报名截止后待办会写「还没分队」。在内战的「更多 → 分队」里勾选上场的人、生成分队、拖拽调整、保存，再点「复制」把结果发到群里。报名的人在活动页和提醒邮件里能看到自己分在哪。",
			LinkURL:   "/admin/scrims/",
			LinkLabel: "内战列表",
		},
		{
			Text: "提醒和结束：开始前 2 小时（全站设置里可改）自动给报名的人发提醒；开始 6 小时后自动标记已结束，也可以提前手动标。",
		},
		{
			Text: "改时间、取消：改开始时间保存不发信、提醒按新时间重发，要告诉报名的人点「通知报名的人」；取消在「更多 → 取消内战」，取消后问要不要给报名的人发信。",
		},
	},
}

var authorsPart = Part{
	Key:   "authors",
	Title: "认证作者",
	Steps: []Step{
		{
			Text:      "你的文章发布后直接上线；网址、搜索描述和定时上线下线在编辑页的「网址和发布时间」一组里。只能改自己的文章。正文用 Markdown 写，工具栏点「?」看写法，图片拖进来或粘贴就上传。",
			LinkURL:   "/admin/articles/",
			LinkLabel: "我的文章",
		},
	},
}

// PartsFor 获取当前用户有权阅读的手册章节。
func PartsFor(v *app.Viewer) []Part {
	if v == nil || v.Disabled {
		return nil
	}
	if v.Superuser {
		return []Part{ownerPart, contentPart, tournamentsPart, scrimsPart, authorsPart}
	}

	var parts []Part
	if v.HasRole(accounts.RoleContentEditor) || v.HasCap(accounts.CapArticlesEditAny) {
		parts = append(parts, contentPart)
	}
	if v.HasRole(accounts.RoleTournamentAdmin) || v.HasCap(accounts.CapTournamentsManage) {
		parts = append(parts, tournamentsPart)
	}
	if v.HasRole(accounts.RoleScrimAdmin) || v.HasCap(accounts.CapScrimsManage) {
		parts = append(parts, scrimsPart)
	}
	if v.HasRole(accounts.RoleCertifiedAuthor) && len(parts) == 0 {
		parts = append(parts, authorsPart)
	}
	return parts
}
