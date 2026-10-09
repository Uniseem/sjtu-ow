package teams

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

func (s *Service) url(path string) string { return s.siteURL + path }

func (s *Service) manageURL(t *Team) string { return s.url(fmt.Sprintf("/teams/%d/manage/", t.ID)) }

func personOf(u *UserBrief) mail.Person { return mail.Person{Address: u.Email, Name: u.Nickname} }

// send 发一封信。有批次（干部操作的那种）就冻住等点头，没有就直接入队。
func (s *Service) send(ctx context.Context, tx *db.Tx, c *app.Ctx, l mail.Letter, to []mail.Person, now time.Time) error {
	var batch *app.LetterBatch
	if c != nil {
		batch = c.Letters
	}
	_, err := outbox.Send(ctx, tx, batch, s.siteURL, l, to, now)
	return err
}

func positionsText(a *Application) string {
	labels := []string{}
	for _, p := range a.Positions() {
		switch p {
		case "tank":
			labels = append(labels, "坦克")
		case "damage":
			labels = append(labels, "输出")
		case "support":
			labels = append(labels, "支援")
		}
	}
	if len(labels) == 0 {
		return "未填"
	}
	return strings.Join(labels, "、")
}

func (s *Service) notifySubmitted(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, a *Application, now time.Time) error {
	captain, err := s.store.CaptainOf(ctx, tx, t.ID)
	if err != nil || captain == nil {
		return err
	}
	cu, err := s.user(ctx, tx, captain.UserID)
	if err != nil || cu == nil {
		return err
	}
	applicant, err := s.user(ctx, tx, a.ApplicantID)
	if err != nil || applicant == nil {
		return err
	}
	msg := a.Message
	if msg == "" {
		msg = "（无）"
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject: "新的入队申请：" + t.Name,
		Lead:    fmt.Sprintf("%s 申请加入你的战队「%s」，等你审批。", applicant.Nickname, t.Name),
		Facts: [][2]string{
			{"申请人", applicant.Nickname},
			{"意向位置", positionsText(a)},
			{"留言", msg},
		},
		Action: []string{"去审批", s.manageURL(t)},
		Reason: fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的队长。", t.Name),
	}, []mail.Person{personOf(cu)}, now)
}

func (s *Service) notifyDecided(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, a *Application, applicant *UserBrief, now time.Time) error {
	if applicant == nil {
		return nil
	}
	reason := fmt.Sprintf("你收到这封邮件，是因为你申请过加入「%s」。", t.Name)
	var l mail.Letter
	if a.Status == StatusApproved {
		// 队长留了队内联系方式，通过的信里就写上（规则 93）。
		var facts [][2]string
		if t.MemberContact != "" {
			facts = [][2]string{{"队内联系方式", t.MemberContact}}
		}
		l = mail.Letter{
			Subject: "入队申请已通过：" + t.Name,
			Lead:    fmt.Sprintf("你加入「%s」的申请已通过，现在你是这支战队的队员了。", t.Name),
			Facts:   facts,
			Action:  []string{"打开战队主页", s.url(fmt.Sprintf("/teams/%d/", t.ID))},
			Reason:  reason,
		}
	} else {
		note := a.DecisionNote
		if note == "" {
			note = "（队长没有填写）"
		}
		l = mail.Letter{
			Subject:    "入队申请未通过：" + t.Name,
			Lead:       fmt.Sprintf("你加入「%s」的申请没有通过。", t.Name),
			Facts:      [][2]string{{"原因", note}},
			Paragraphs: []string{"你可以调整之后再申请，或者看看别的战队。"},
			Action:     []string{"打开战队主页", s.url(fmt.Sprintf("/teams/%d/", t.ID))},
			Reason:     reason,
		}
	}
	return s.send(ctx, tx, c, l, []mail.Person{personOf(applicant)}, now)
}

func (s *Service) notifyWaiting(ctx context.Context, tx *db.Tx, t *Team, apps []*Application, captain *UserBrief, now time.Time) error {
	left := StaleApplicationDays - RemindCaptainDays
	facts := make([][2]string, 0, len(apps))
	for _, a := range apps {
		name := fmt.Sprintf("申请人 %d", a.ApplicantID)
		if u, err := s.user(ctx, tx, a.ApplicantID); err == nil && u != nil {
			name = u.Nickname
		}
		facts = append(facts, [2]string{name, positionsText(a)})
	}
	return s.send(ctx, tx, nil, mail.Letter{
		Subject: "入队申请等你处理：" + t.Name,
		Lead: fmt.Sprintf("「%s」有 %d 个入队申请等了 %d 天以上，再过 %d 天没处理会自动关闭。",
			t.Name, len(apps), RemindCaptainDays, left),
		Facts:  facts,
		Action: []string{"去审批", s.manageURL(t)},
		Reason: fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的队长。", t.Name),
	}, []mail.Person{personOf(captain)}, now)
}

func (s *Service) notifyExpired(ctx context.Context, tx *db.Tx, t *Team, applicant *UserBrief, now time.Time) error {
	return s.send(ctx, tx, nil, mail.Letter{
		Subject: "入队申请已关闭：" + t.Name,
		Lead: fmt.Sprintf("你加入「%s」的申请，队长 %d 天没有处理，已经自动关闭。",
			t.Name, StaleApplicationDays),
		Paragraphs: []string{"队长可能最近不在。你可以过一阵再申请，或者看看别的招募中的战队。"},
		Action:     []string{"看看招募中的战队", s.url("/teams/?recruiting=1")},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你申请过加入「%s」。", t.Name),
	}, []mail.Person{personOf(applicant)}, now)
}

func (s *Service) notifyRemoved(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, userID int64, now time.Time) error {
	u, err := s.user(ctx, tx, userID)
	if err != nil || u == nil {
		return err
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "你已被移出战队：" + t.Name,
		Lead:       fmt.Sprintf("队长把你移出了战队「%s」。", t.Name),
		Paragraphs: []string{"如果有疑问，请直接联系队长。"},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你曾是战队「%s」的队员。", t.Name),
	}, []mail.Person{personOf(u)}, now)
}

func (s *Service) notifyLeft(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, leaverID int64, now time.Time) error {
	captain, err := s.store.CaptainOf(ctx, tx, t.ID)
	if err != nil || captain == nil {
		return err
	}
	cu, err := s.user(ctx, tx, captain.UserID)
	if err != nil || cu == nil {
		return err
	}
	leaver, err := s.user(ctx, tx, leaverID)
	if err != nil || leaver == nil {
		return err
	}
	facts := [][2]string{{"退出的人", leaver.Nickname}}
	var paragraphs []string
	action := []string{"打开战队管理", s.manageURL(t)}
	if s.rosters != nil {
		entries, err := s.rosters.EntriesStillListing(ctx, tx, t.ID, leaverID)
		if err != nil {
			return err
		}
		for _, e := range entries {
			closes := "未定"
			if e.ClosesAt != nil {
				closes = e.ClosesAt.In(shanghai).Format("2006-01-02 15:04")
			}
			facts = append(facts, [2]string{"还在报名名单里", fmt.Sprintf("%s（报名截止 %s）", e.Title, closes)})
		}
		if len(entries) > 0 {
			paragraphs = append(paragraphs, "已经提交的报名名单不会跟着战队变。报名截止前可以在报名详情页同步名单，截止以后请联系赛事管理员。")
			action = []string{"查看报名详情", s.url(entries[0].DetailURL)}
		}
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "队员退出战队：" + t.Name,
		Lead:       fmt.Sprintf("%s 退出了战队「%s」。", leaver.Nickname, t.Name),
		Facts:      facts,
		Paragraphs: paragraphs,
		Action:     action,
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的队长。", t.Name),
	}, []mail.Person{personOf(cu)}, now)
}

func (s *Service) notifyCaptainChanged(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, newCaptain *UserBrief, now time.Time) error {
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "你已成为队长：" + t.Name,
		Lead:       fmt.Sprintf("你现在是战队「%s」的队长。", t.Name),
		Paragraphs: []string{"审批入队申请、管理成员、为战队报名比赛，都在战队管理页。"},
		Action:     []string{"打开战队管理", s.manageURL(t)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的成员。", t.Name),
	}, []mail.Person{personOf(newCaptain)}, now)
}

func (s *Service) notifyDisbanded(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Team, memberIDs []int64, now time.Time) error {
	var people []mail.Person
	for _, id := range memberIDs {
		u, err := s.user(ctx, tx, id)
		if err != nil {
			return err
		}
		if u != nil {
			people = append(people, personOf(u))
		}
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "战队已解散：" + t.Name,
		Lead:       fmt.Sprintf("战队「%s」已经解散。", t.Name),
		Paragraphs: []string{"还在等审批的入队申请也一并取消了。"},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的成员。", t.Name),
	}, people, now)
}
