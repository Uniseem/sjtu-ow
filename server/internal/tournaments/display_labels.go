package tournaments

import (
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
)

var actionLabels = map[string]string{
	ActSubmit:     "提交报名",
	ActResubmit:   "重新提交",
	ActSyncRoster: "同步名单",
	ActApprove:    "通过",
	ActReject:     "驳回",
	ActRevoke:     "撤销通过",
	ActWithdraw:   "撤回",
	ActFormTeam:   "编队",
	ActMemberLeft: "退出队伍",
	ActDissolve:   "解散队伍",
}

var actorLabels = map[string]string{
	ActorCaptain: "队长",
	ActorAdmin:   "本站管理员",
	ActorSystem:  "系统",
	ActorMember:  "队员",
}

func labeled(value string, labels map[string]string) string {
	if label, ok := labels[value]; ok {
		return label
	}
	return value
}

func rankLabels(tank, damage, support *int) []string {
	out := []string{}
	for _, item := range []struct {
		label string
		score *int
	}{{"坦克", tank}, {"输出", damage}, {"支援", support}} {
		if item.score != nil {
			out = append(out, item.label+" "+accounts.FormatRank(item.score))
		}
	}
	return out
}

func rankSummary(labels []string) string {
	if len(labels) == 0 {
		return "未定级"
	}
	return strings.Join(labels, " · ")
}
