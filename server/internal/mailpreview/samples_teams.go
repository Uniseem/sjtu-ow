package mailpreview

import "github.com/Uniseem/sjtu-ow/server/internal/platform/mail"

func teamSamples() []Sample {
	return []Sample{
		specimen("apply", "战队", "收到入队申请", "队长", captainName, "server/internal/teams/notify.go", mail.Letter{
			Subject: "新的入队申请：" + teamName,
			Lead:    memberName + " 申请加入你的战队「" + teamName + "」，等你审批。",
			Facts:   [][2]string{{"申请人", memberName}, {"意向位置", "坦克、支援"}, {"留言", "周末晚上都有空，主玩坦克。"}},
			Action:  []string{"去审批", sampleURL("/teams/1/manage/")},
			Reason:  teamReason(),
		}),
		specimen("apply-ok", "战队", "入队申请通过", "申请人", memberName, "server/internal/teams/notify.go", mail.Letter{
			Subject: "入队申请已通过：" + teamName,
			Lead:    "你加入「" + teamName + "」的申请已通过，现在你是这支战队的队员了。",
			Facts:   [][2]string{{"队内联系方式", "QQ 群（虚构）123456789"}},
			Action:  []string{"打开战队主页", sampleURL("/teams/1/")},
			Reason:  applicationReason(),
		}),
		specimen("apply-no", "战队", "入队申请未通过", "申请人", memberName, "server/internal/teams/notify.go", mail.Letter{
			Subject:    "入队申请未通过：" + teamName,
			Lead:       "你加入「" + teamName + "」的申请没有通过。",
			Facts:      [][2]string{{"原因", "这个赛季名额满了，下个赛季欢迎再来。"}},
			Paragraphs: []string{"你可以调整之后再申请，或者看看别的战队。"},
			Action:     []string{"打开战队主页", sampleURL("/teams/1/")},
			Reason:     applicationReason(),
		}),
		specimen("applications-waiting", "战队", "入队申请等你处理", "队长", captainName, "server/internal/teams/notify.go", mail.Letter{
			Subject: "入队申请等你处理：" + teamName,
			Lead:    "「" + teamName + "」有 1 个入队申请等了 7 天以上，再过 7 天没处理会自动关闭。",
			Facts:   [][2]string{{memberName, "坦克、支援"}},
			Action:  []string{"去审批", sampleURL("/teams/1/manage/")},
			Reason:  teamReason(),
		}),
		specimen("application-expired", "战队", "入队申请已自动关闭", "申请人", memberName, "server/internal/teams/notify.go", mail.Letter{
			Subject:    "入队申请已关闭：" + teamName,
			Lead:       "你加入「" + teamName + "」的申请，队长 14 天没有处理，已经自动关闭。",
			Paragraphs: []string{"队长可能最近不在。你可以过一阵再申请，或者看看别的招募中的战队。"},
			Action:     []string{"看看招募中的战队", sampleURL("/teams/?recruiting=1")},
			Reason:     applicationReason(),
		}),
		specimen("removed", "战队", "被移出战队", "被移除的人", memberName, "server/internal/teams/notify.go", mail.Letter{
			Subject:    "你已被移出战队：" + teamName,
			Lead:       "队长把你移出了战队「" + teamName + "」。",
			Paragraphs: []string{"如果有疑问，请直接联系队长。"},
			Reason:     "你收到这封邮件，是因为你曾是战队「" + teamName + "」的队员。",
		}),
		specimen("member-left", "战队", "队员退出战队", "队长", captainName, "server/internal/teams/notify.go", mail.Letter{
			Subject:    "队员退出战队：" + teamName,
			Lead:       "西瓜退出了战队「" + teamName + "」。",
			Facts:      [][2]string{{"退出的人", "西瓜"}, {"还在报名名单里", tournamentName + "（报名截止 2026-11-01 23:59）"}},
			Paragraphs: []string{"已经提交的报名名单不会跟着战队变。报名截止前可以在报名详情页同步名单，截止以后请联系赛事管理员。"},
			Action:     []string{"查看报名详情", sampleURL("/registrations/1/")},
			Reason:     teamReason(),
		}),
		specimen("captain", "战队", "成为队长", "新队长", memberName, "server/internal/teams/notify.go", mail.Letter{
			Subject:    "你已成为队长：" + teamName,
			Lead:       "你现在是战队「" + teamName + "」的队长。",
			Paragraphs: []string{"审批入队申请、管理成员、为战队报名比赛，都在战队管理页。"},
			Action:     []string{"打开战队管理", sampleURL("/teams/1/manage/")},
			Reason:     "你收到这封邮件，是因为你是战队「" + teamName + "」的成员。",
		}),
		specimen("disbanded", "战队", "战队解散", "全体成员", memberName, "server/internal/teams/notify.go", mail.Letter{
			Subject:    "战队已解散：" + teamName,
			Lead:       "战队「" + teamName + "」已经解散。",
			Paragraphs: []string{"还在等审批的入队申请也一并取消了。"},
			Reason:     "你收到这封邮件，是因为你是战队「" + teamName + "」的成员。",
		}),
	}
}
