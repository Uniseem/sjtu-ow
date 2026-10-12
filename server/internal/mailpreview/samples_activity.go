package mailpreview

import "github.com/Uniseem/sjtu-ow/server/internal/platform/mail"

func scrimSamples() []Sample {
	link := sampleURL("/scrims/2/")
	facts := [][2]string{{"开始时间", "2026-10-05 19:30"}, {"规格", "不限位置 6v6"}}
	return []Sample{
		specimen("reminder", "内战", "内战开始提醒", "全部报名者", memberName, "server/internal/scrims/service.go", mail.Letter{
			Subject:    "内战提醒：" + scrimName,
			Lead:       "内战「" + scrimName + "」就要开始了，请提前上线。",
			Facts:      append(facts, [2]string{"你的位置", "A 队 · 坦克"}, [2]string{"社团 QQ 群", "群入口（虚构）"}),
			Paragraphs: []string{"分队结果由管理员发到群里。临时来不了的话，请尽早告诉管理员。"},
			Action:     []string{"查看活动页面", link}, Reason: scrimReason(),
		}),
		specimen("scrim-update", "内战", "内战有更新（管理员点「通知报名的人」，时间改过）", "全部报名者", memberName, "server/internal/scrims/service.go", mail.Letter{
			Subject:    "内战有更新：" + scrimName,
			Lead:       "内战「" + scrimName + "」的时间改了：原来 2026-10-04 19:30，现在 2026-10-05 19:30。",
			Facts:      facts,
			Paragraphs: []string{"临时来不了的话，请在活动页面取消报名。"},
			Action:     []string{"查看活动页面", link}, Reason: scrimReason(),
		}),
		specimen("scrim-cancelled", "内战", "内战取消", "全部报名者", memberName, "server/internal/scrims/service.go", mail.Letter{
			Subject: "内战已取消：" + scrimName,
			Lead:    "内战「" + scrimName + "」取消了，原定的时间不用再留出来。",
			Facts:   facts, Paragraphs: []string{"之后有新的内战会在网站上公布。"},
			Action: []string{"查看活动页面", link}, Reason: scrimReason(),
		}),
	}
}

func announcementSamples() []Sample {
	unsubscribe := sampleURL("/unsubscribe/sample/")
	return []Sample{
		specimen("new-tournament", "活动通知", "新赛事通知（群发）", "开着活动通知的成员", memberName, "server/internal/tournaments/announce.go", mail.Letter{
			Subject:    "新赛事：" + tournamentName,
			Lead:       "社团发布了新的赛事「" + tournamentName + "」，现在可以报名了。",
			Facts:      [][2]string{{"比赛时间", "2026-11-08 14:00"}, {"报名开始", "2026-10-01 00:00"}, {"报名截止", "2026-11-01 23:59"}, {"报名方式", "个人报名，赛事组编队"}, {"参与资格", "仅限交大成员"}},
			Paragraphs: []string{"五人一队，单败淘汰，冠军队伍有社团周边。"},
			Action:     []string{"查看并报名", sampleURL("/tournaments/1/")},
			Reason:     activityReason(), Unsubscribe: unsubscribe,
		}),
		specimen("new-tournament-upcoming", "活动通知", "新赛事通知（报名尚未开始）", "开着活动通知的成员", memberName, "server/internal/tournaments/announce.go", mail.Letter{
			Subject:    "新赛事：" + tournamentName,
			Lead:       "社团发布了新的赛事「" + tournamentName + "」，报名将在 2026-10-10 00:00 开始。",
			Facts:      [][2]string{{"比赛时间", "2026-11-08 14:00"}, {"报名开始", "2026-10-10 00:00"}, {"报名截止", "2026-11-01 23:59"}, {"报名方式", "整队报名"}},
			Paragraphs: []string{"请先完善游戏 ID 和联系方式。"},
			Action:     []string{"查看赛事页面", sampleURL("/tournaments/1/")},
			Reason:     activityReason(), Unsubscribe: unsubscribe,
		}),
		specimen("new-article", "活动通知", "新文章通知（群发）", "开着活动通知的成员", memberName, "server/internal/content/announce.go", mail.Letter{
			Subject:    "公告：秋季招新开始了",
			Lead:       "社团发布了一篇公告「秋季招新开始了」。",
			Paragraphs: []string{"面向全校，不限段位，填表后拉你进群。"},
			Action:     []string{"阅读全文", sampleURL("/news/autumn-recruiting/")},
			Reason:     activityReason(), Unsubscribe: unsubscribe,
		}),
		specimen("new-scrim", "活动通知", "新内战通知（群发）", "开着活动通知的成员", memberName, "server/internal/scrims/announce.go", mail.Letter{
			Subject:    "新内战：" + scrimName,
			Lead:       "社团发布了新的内战「" + scrimName + "」，现在可以报名了。",
			Facts:      [][2]string{{"开始时间", "2026-10-05 19:30"}, {"报名截止", "2026-10-05 18:00"}, {"规格", "不限位置 6v6"}, {"参与资格", "不限是否来自交大"}},
			Paragraphs: []string{"怀旧版本，六人一队，不限位置。"},
			Action:     []string{"查看并报名", sampleURL("/scrims/2/")},
			Reason:     activityReason(), Unsubscribe: unsubscribe,
		}),
	}
}

func moderationSamples() []Sample {
	return []Sample{
		specimen("patrol", "审核", "AI 巡查发现可能不妥的内容（v6.72）", "「巡查提醒发到」填的邮箱，没填是全部超级管理员", "站长", "core/email_samples.py; D5巡查执行待移植", mail.Letter{
			Subject: "内容巡查：发现3条可能不妥的内容",
			Lead:    "这一轮内容巡查发现了 3 条可能需要人工复核的内容。AI 的判断仅供参考。",
			Items: [][2]string{
				{"评论 · 高风险：你这种水平也配打天梯？", sampleURL("/admin/moderation/42/")},
				{"文章 · 中风险：比赛录像里出现了未经同意的真实姓名。", sampleURL("/admin/moderation/43/")},
				{"个人宣言 · 低风险：加群领福利，私聊。", sampleURL("/admin/moderation/44/")},
			},
			ItemLink: "巡查详情", Action: []string{"打开巡查记录", sampleURL("/admin/moderation/")},
			Reason: "你收到这封邮件，是因为你是站点管理员或巡查提醒的收件人。",
		}),
		specimen("ask-author", "审核", "要求修改内容", "内容的作者", "队长甲", "server/internal/moderation/service.go", mail.Letter{
			Subject:    "请修改你的战队简介",
			Lead:       "社区的管理员看过你发布的一条战队简介，请你按下面的说明修改。",
			Facts:      [][2]string{{"内容类型", "战队简介"}, {"内容片段", "来的都是菜鸡"}},
			Paragraphs: []string{"管理员的说明：简介里有贬低其他玩家的说法，请改成正面的招募介绍。", "改完保存就行，不用回复这封邮件。"},
			Action:     []string{"去修改", sampleURL("/teams/3/manage/")},
			Reason:     "你收到这封邮件，是因为你在社区发布的内容需要修改。",
		}),
		specimen("ask-author-again", "审核", "再次要求修改内容", "内容的作者", "队长甲", "server/internal/moderation/service.go", mail.Letter{
			Subject:    "请修改你的文章",
			Notice:     "关于这条文章，之前已经发过 1 次修改提醒，这次可能有修改，请以这封为准。",
			Lead:       "社区的管理员看过你发布的一条文章，请你按下面的说明修改。",
			Facts:      [][2]string{{"内容类型", "文章"}, {"内容片段", "比赛录像里出现了未经同意的真实姓名。"}},
			Paragraphs: []string{"管理员的说明：请移除未经同意公开的姓名。", "改完保存就行，不用回复这封邮件。"},
			Action:     []string{"去修改", sampleURL("/admin/articles/1/")},
			Reason:     "你收到这封邮件，是因为你在社区发布的内容需要修改。",
		}),
	}
}
