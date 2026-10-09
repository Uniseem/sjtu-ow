package tournaments

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

const announceWhy = "你收到这封邮件，是因为你在社区开着「活动通知」。"

var modeLabels = map[string]string{ModeIndividual: "个人报名", ModeTeam: "整队报名"}

// AnnounceKind 是赛事的「通知全体成员」（设计 10.4）：谁能发、读什么、信怎么写。
func (s *Service) AnnounceKind() notify.Kind {
	return notify.Kind{
		Key:  notify.KindTournament,
		Noun: "这场赛事",
		CanSend: func(v *app.Viewer) bool {
			return v != nil && !v.Disabled && v.HasCap(accounts.CapTournamentsManage)
		},
		Load: func(ctx context.Context, q db.DBTX, id int64) (*notify.Subject, error) {
			t, err := GetTournament(ctx, q, id)
			if err != nil || t == nil {
				return nil, err
			}
			return &notify.Subject{Title: t.Title, Live: t.Status == StatusPublished, SJTUOnly: t.SjtuOnly}, nil
		},
		Letter: func(ctx context.Context, q db.DBTX, id int64, unsubscribe string, now time.Time) (mail.Letter, error) {
			t, err := GetTournament(ctx, q, id)
			if err != nil || t == nil {
				return mail.Letter{}, err
			}
			return newTournamentLetter(t, unsubscribe, s.tournamentURL(t.ID), now), nil
		},
	}
}

func newTournamentLetter(t *Tournament, unsubscribe, link string, now time.Time) mail.Letter {
	var lead string
	if t.RegistrationOpensAt != nil && t.RegistrationOpensAt.After(now) {
		lead = "社团发布了新的赛事「" + t.Title + "」，" + moment(*t.RegistrationOpensAt) + " 开始报名。"
	} else {
		lead = "社团发布了新的赛事「" + t.Title + "」，现在可以报名了。"
	}
	var facts [][2]string
	if t.StartsAt != nil {
		facts = append(facts, [2]string{"比赛时间", moment(*t.StartsAt)})
	}
	if t.RegistrationClosesAt != nil {
		facts = append(facts, [2]string{"报名截止", moment(*t.RegistrationClosesAt)})
	}
	facts = append(facts, [2]string{"报名方式", modeLabels[t.RegistrationMode]})
	if t.SjtuOnly {
		facts = append(facts, [2]string{"参赛范围", "仅限交大成员"})
	}
	var paragraphs []string
	if t.Summary != "" {
		paragraphs = []string{t.Summary}
	}
	return mail.Letter{
		Subject:     "新赛事：" + t.Title,
		Lead:        lead,
		Facts:       facts,
		Paragraphs:  paragraphs,
		Action:      []string{"查看并报名", link},
		Reason:      announceWhy,
		Unsubscribe: unsubscribe,
	}
}
