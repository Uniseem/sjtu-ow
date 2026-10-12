package mailpreview

import "github.com/Uniseem/sjtu-ow/server/internal/platform/mail"

func tournamentSamples() []Sample {
	link := sampleURL("/tournaments/1/")
	details := sampleURL("/registrations/1/")
	facts := [][2]string{{"比赛时间", "2026-11-08 14:00"}, {"选手联系方式", "选手群（虚构）987654321"}}
	updated := mail.Letter{
		Subject:    "赛事有更新：" + tournamentName,
		Lead:       "「" + tournamentName + "」的比赛时间改了：原来 2026-11-07 14:00，现在 2026-11-08 14:00。",
		Facts:      facts,
		Paragraphs: []string{"管理员的说明：场地改到了线上，开赛前一小时进群看房间号。", "开赛前会按新的时间再提醒一次。新时间来不了的话，请尽早告诉队长或赛事管理员。"},
		Action:     []string{"查看赛事页面", link}, Reason: registrationReason(),
	}
	entries := []Sample{
		specimen("unplaced-reminder", "赛事", "赛事开始提醒（还没编进队伍）", "散人池里还没编进的人", "西瓜", "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "赛事提醒：" + tournamentName,
			Lead:       "「" + tournamentName + "」将在 2026-11-08 14:00 开始，你还在散人池里，没有被编进队伍。",
			Facts:      facts,
			Paragraphs: []string{"赛事管理员可能还在编队，编进队伍时你会另外收到一封邮件。到开赛还没编进的话，这次可能没有位置；有疑问请联系赛事管理员。"},
			Action:     []string{"查看赛事页面", link},
			Reason:     "你收到这封邮件，是因为你个人报名了「" + tournamentName + "」。",
		}),
		specimen("tournament-update", "赛事", "赛事有更新（管理员点「通知报名的人」，时间改过）", "报了名的人（名单里的、散人池里的）", memberName, "server/internal/tournaments/notify.go", updated),
		specimen("tournament-update-again", "赛事", "赛事有更新（第二封起：开头写明之前发过几次）", "报了名的人（名单里的、散人池里的）", memberName, "server/internal/notify/announce.go", repeat(updated, "这场赛事", "1")),
		specimen("submitted", "赛事", "报名已提交", "队长", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "报名已提交：" + tournamentName,
			Lead:       "「" + teamName + "」报名「" + tournamentName + "」的名单已提交，等赛事管理员审核。",
			Facts:      append(registrationFacts(), [2]string{"名单版本", "1"}, [2]string{"当前状态", "待审核"}),
			Paragraphs: []string{"名单里新加的队员会各收到一封通知，不需要他们确认。"},
			Action:     []string{"查看报名详情", details}, Reason: teamReason(),
		}),
		specimen("resubmitted", "赛事", "报名已重新提交", "队长", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "报名已重新提交：" + tournamentName,
			Lead:       "「" + teamName + "」报名「" + tournamentName + "」的名单已提交，等赛事管理员审核。",
			Facts:      append(registrationFacts(), [2]string{"名单版本", "2"}, [2]string{"当前状态", "待审核"}),
			Paragraphs: []string{"名单里新加的队员会各收到一封通知，不需要他们确认。"},
			Action:     []string{"查看报名详情", details}, Reason: teamReason(),
		}),
		specimen("roster-synced", "赛事", "报名名单已同步", "队长", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "报名名单已同步：" + tournamentName,
			Lead:       "「" + teamName + "」报名「" + tournamentName + "」的名单已提交，并且已经通过。",
			Facts:      append(registrationFacts(), [2]string{"名单版本", "3"}, [2]string{"当前状态", "已通过"}),
			Paragraphs: []string{"名单里新加的队员会各收到一封通知，不需要他们确认。"},
			Action:     []string{"查看报名详情", details}, Reason: teamReason(),
		}),
		specimen("entered", "赛事", "你已被报名参加", "名单里的队员", memberName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "你已被报名参加：" + tournamentName,
			Lead:       "队长 " + captainName + " 为战队「" + teamName + "」报名了「" + tournamentName + "」，你在名单里。",
			Facts:      append(registrationFacts(), [2]string{"你的游戏 ID", "小天使#5123"}, [2]string{"当前状态", "待审核"}, [2]string{"选手联系方式", "选手群（虚构）987654321"}),
			Paragraphs: []string{"整队报名不需要你确认。不想参加的话，请在报名截止前联系队长。"},
			Action:     []string{"查看报名详情", details},
			Reason:     "你收到这封邮件，是因为你是战队「" + teamName + "」的队员。",
		}),
		specimen("approved", "赛事", "报名通过", "队长", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject: "报名已通过：" + tournamentName,
			Lead:    "「" + teamName + "」报名「" + tournamentName + "」已通过审核。",
			Facts:   append(registrationFacts(), facts...), Action: []string{"查看报名详情", details}, Reason: teamReason(),
		}),
		specimen("rejected", "赛事", "报名驳回", "队长", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "报名已驳回：" + tournamentName,
			Lead:       "「" + teamName + "」报名「" + tournamentName + "」的状态变成了：已驳回。",
			Facts:      append(registrationFacts(), [2]string{"备注", "名单里有两位队员没有填联系方式。"}),
			Paragraphs: []string{"你可以按备注修改后，在报名截止前重新提交。"},
			Action:     []string{"查看报名详情", details}, Reason: teamReason(),
		}),
		specimen("withdrawn", "赛事", "报名已撤回", "队长", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject: "报名已撤回：" + tournamentName,
			Lead:    "「" + teamName + "」报名「" + tournamentName + "」的状态变成了：已撤回。",
			Facts:   registrationFacts(), Action: []string{"查看报名详情", details}, Reason: teamReason(),
		}),
		specimen("cancelled", "赛事", "赛事取消", "队长、临时队伍成员", captainName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "赛事已取消：" + tournamentName,
			Lead:       "「" + tournamentName + "」已经取消，你的报名不再有效。",
			Facts:      [][2]string{{"说明", "场地临时不能用，改期另行通知。"}},
			Paragraphs: []string{"给你带来不便，抱歉。之后有新的赛事会在网站上公布。"},
			Action:     []string{"查看赛事页面", link}, Reason: registrationReason(),
		}),
		specimen("formed", "赛事", "已编入临时队伍", "被编入的成员", "西瓜", "server/internal/tournaments/individual.go", mail.Letter{
			Subject:    "已编入临时队伍：" + tournamentName,
			Lead:       "赛事管理员把你编入了「" + tournamentName + "」的临时队伍「新生一队」，报名已通过。",
			Facts:      [][2]string{{"赛事", tournamentName}, {"队伍", "新生一队"}, {"队友", "小天使、白露、西瓜"}, {"选手联系方式", "选手群（虚构）987654321"}},
			Paragraphs: []string{"报名截止前，你可以在报名详情页退出队伍，回到散人池。"},
			Action:     []string{"查看报名详情", details},
			Reason:     "你收到这封邮件，是因为你个人报名了「" + tournamentName + "」。",
		}),
		specimen("returned", "赛事", "移出临时队伍 / 队伍解散", "受影响的成员", "西瓜", "server/internal/tournaments/individual.go", mail.Letter{
			Subject:    "临时队伍有变化：" + tournamentName,
			Lead:       "临时队伍「新生一队」已由赛事管理员解散，你回到了散人池。",
			Facts:      [][2]string{{"赛事", tournamentName}, {"原来的队伍", "新生一队"}},
			Paragraphs: []string{"你的个人报名还在，重新编队后会再通知你。"},
			Action:     []string{"查看赛事页面", link},
			Reason:     "你收到这封邮件，是因为你个人报名了「" + tournamentName + "」。",
		}),
		specimen("left", "赛事", "临时队伍成员退出", "赛事管理员", "赛事管理员", "server/internal/tournaments/individual.go", mail.Letter{
			Subject: "临时队伍成员退出：" + tournamentName,
			Lead:    "西瓜退出了「" + tournamentName + "」的临时队伍「新生一队」，回到散人池。",
			Facts:   [][2]string{{"赛事", tournamentName}, {"队伍", "新生一队"}, {"退出的人", "西瓜"}},
			Action:  []string{"打开队伍编排", sampleURL("/admin/tournaments/1/teams/")},
			Reason:  "你收到这封邮件，是因为你是赛事管理员。",
		}),
		specimen("tournament-reminder", "赛事", "赛事开始提醒", "已通过报名的队员，每人一封", memberName, "server/internal/tournaments/notify.go", mail.Letter{
			Subject:    "赛事提醒：" + tournamentName,
			Lead:       "「" + tournamentName + "」将在 2026-11-08 14:00 开始，你所在的「" + teamName + "」已通过报名。",
			Facts:      append([][2]string{{"比赛时间", "2026-11-08 14:00"}, {"你的队伍", teamName}, {"你的游戏 ID", "小天使#5123"}}, [2]string{"选手联系方式", "选手群（虚构）987654321"}),
			Paragraphs: []string{"比赛安排和规则以赛事页面为准，请提前上线。临时来不了的话，请尽早告诉队长。"},
			Action:     []string{"查看赛事页面", link},
			Reason:     "你收到这封邮件，是因为你在「" + tournamentName + "」已通过报名的名单里。",
		}),
	}
	return entries
}
