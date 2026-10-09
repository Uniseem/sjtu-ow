package scrims

import (
	"context"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// AnnounceKind 是内战的「通知全体成员」（设计 10.4）。
func (s *Service) AnnounceKind() notify.Kind {
	return notify.Kind{
		Key:  notify.KindScrim,
		Noun: "这场内战",
		CanSend: func(v *app.Viewer) bool {
			return v != nil && !v.Disabled && v.HasCap(accounts.CapScrimsManage)
		},
		Load: func(ctx context.Context, q db.DBTX, id int64) (*notify.Subject, error) {
			sc, err := GetScrim(ctx, q, id)
			if err != nil || sc == nil {
				return nil, err
			}
			return &notify.Subject{Title: sc.Title, Live: sc.Status == StatusPublished, SJTUOnly: sc.SjtuOnly}, nil
		},
		Letter: func(ctx context.Context, q db.DBTX, id int64, unsubscribe string, _ time.Time) (mail.Letter, error) {
			sc, err := GetScrim(ctx, q, id)
			if err != nil || sc == nil {
				return mail.Letter{}, err
			}
			var plain string
			if err := q.QueryRowContext(ctx, `SELECT description_plain FROM scrims WHERE id = ?`, id).Scan(&plain); err != nil {
				return mail.Letter{}, err
			}
			return newScrimLetter(sc, plain, unsubscribe, s.scrimURL(sc.ID)), nil
		},
	}
}

func newScrimLetter(sc *Scrim, plain, unsubscribe, link string) mail.Letter {
	when := "时间未定"
	if sc.StartsAt != nil {
		when = moment(*sc.StartsAt)
	}
	facts := [][2]string{{"开始时间", when}, {"规格", FormatLabels[sc.Format]}}
	if d := sc.Deadline(); d != nil {
		facts = append(facts, [2]string{"报名截止", moment(*d)})
	}
	if sc.SjtuOnly {
		facts = append(facts, [2]string{"参加范围", "仅限交大成员"})
	}
	// 读者看到的纯文本，截到 300 字（现行站同）。
	if utf8.RuneCountInString(plain) > 300 {
		plain = string([]rune(plain)[:300]) + "……"
	}
	var paragraphs []string
	if plain != "" {
		paragraphs = []string{plain}
	}
	return mail.Letter{
		Subject:     "新内战：" + sc.Title,
		Lead:        "社团发布了新的内战「" + sc.Title + "」，现在可以报名了。",
		Facts:       facts,
		Paragraphs:  paragraphs,
		Action:      []string{"查看并报名", link},
		Reason:      "你收到这封邮件，是因为你在社区开着「活动通知」。",
		Unsubscribe: unsubscribe,
	}
}
