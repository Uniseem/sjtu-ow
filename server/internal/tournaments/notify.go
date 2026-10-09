package tournaments

import (
	"context"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

func moment(t time.Time) string { return t.In(shanghai).Format("2006-01-02 15:04") }

func contactFact(t *Tournament) [][2]string {
	if t.ParticipantContact == "" {
		return nil
	}
	return [][2]string{{"选手联系方式", t.ParticipantContact}}
}

func (s *Service) notifyCancelled(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, to []mail.Person, reason string, now time.Time) error {
	var facts [][2]string
	if reason != "" {
		facts = [][2]string{{"说明", reason}}
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "赛事已取消：" + t.Title,
		Lead:       fmt.Sprintf("「%s」已经取消，你的报名不再有效。", t.Title),
		Facts:      facts,
		Paragraphs: []string{"给你带来不便，抱歉。之后有新的赛事会在网站上公布。"},
		Action:     []string{"查看赛事页面", s.tournamentURL(t.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你报名了「%s」。", t.Title),
	}, to, now)
}

// updateLetter 「通知报名的人」（设计 10.4，规则 137）。
func (s *Service) updateLetter(t *Tournament, movedFrom *time.Time, note string) mail.Letter {
	moved := movedFrom != nil && t.StartsAt != nil && !movedFrom.Equal(*t.StartsAt)
	var lead string
	if moved {
		lead = fmt.Sprintf("「%s」的比赛时间改了：原来 %s，现在 %s。", t.Title, moment(*movedFrom), moment(*t.StartsAt))
	} else {
		lead = fmt.Sprintf("「%s」的信息有更新，请以赛事页面上的为准。", t.Title)
	}
	var paragraphs []string
	if note != "" {
		paragraphs = append(paragraphs, "管理员的说明："+note)
	}
	if moved {
		paragraphs = append(paragraphs, "开赛前会按新的时间再提醒一次。新时间来不了的话，请尽早告诉队长或赛事管理员。")
	}
	when := "待定"
	if t.StartsAt != nil {
		when = moment(*t.StartsAt)
	}
	return mail.Letter{
		Subject:    "赛事有更新：" + t.Title,
		Lead:       lead,
		Facts:      append([][2]string{{"比赛时间", when}}, contactFact(t)...),
		Paragraphs: paragraphs,
		Action:     []string{"查看赛事页面", s.tournamentURL(t.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你报名了「%s」。", t.Title),
	}
}

func (s *Service) reminderLetter(t *Tournament, regName string, adhoc bool, battletag string) mail.Letter {
	ask := "队长"
	if adhoc {
		ask = "赛事管理员"
	}
	bt := battletag
	if bt == "" {
		bt = "未填"
	}
	return mail.Letter{
		Subject: "赛事提醒：" + t.Title,
		Lead:    fmt.Sprintf("「%s」将在 %s 开始，你所在的「%s」已通过报名。", t.Title, moment(*t.StartsAt), regName),
		Facts: append([][2]string{
			{"比赛时间", moment(*t.StartsAt)},
			{"你的队伍", regName},
			{"你的游戏 ID", bt},
		}, contactFact(t)...),
		Paragraphs: []string{fmt.Sprintf("比赛安排和规则以赛事页面为准，请提前上线。临时来不了的话，请尽早告诉%s。", ask)},
		Action:     []string{"查看赛事页面", s.tournamentURL(t.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你在「%s」已通过报名的名单里。", t.Title),
	}
}

func (s *Service) unplacedReminderLetter(t *Tournament) mail.Letter {
	return mail.Letter{
		Subject:    "赛事提醒：" + t.Title,
		Lead:       fmt.Sprintf("「%s」将在 %s 开始，你还在散人池里，没有被编进队伍。", t.Title, moment(*t.StartsAt)),
		Facts:      append([][2]string{{"比赛时间", moment(*t.StartsAt)}}, contactFact(t)...),
		Paragraphs: []string{"赛事管理员可能还在编队，编进队伍时你会另外收到一封邮件。到开赛还没编进的话，这次可能没有位置；有疑问请联系赛事管理员。"},
		Action:     []string{"查看赛事页面", s.tournamentURL(t.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你个人报名了「%s」。", t.Title),
	}
}

var statusLabels = map[string]string{RegPending: "待审核", RegApproved: "已通过", RegRejected: "已驳回", RegWithdrawn: "已撤回"}

func (s *Service) regURL(id int64) string { return s.url(fmt.Sprintf("/registrations/%d/", id)) }

func (s *Service) regWhy(r *Registration) string {
	if r.Adhoc() {
		return fmt.Sprintf("你收到这封邮件，是因为你在临时队伍「%s」里。", r.TeamName)
	}
	return fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的队长。", r.TeamName)
}

// regRecipients 整队报名写给队长；临时队伍没有队长，名单上每个人都收（设计 8.8.2）。
func (s *Service) regRecipients(ctx context.Context, q db.DBTX, r *Registration) ([]mail.Person, error) {
	var query string
	var arg int64
	if r.TeamID != nil {
		query = `SELECT u.nickname, u.email FROM team_memberships m JOIN users u ON u.id = m.user_id
			WHERE m.team_id = ? AND m.role = 'captain' AND u.email <> ''`
		arg = *r.TeamID
	} else {
		query = `SELECT u.nickname, u.email FROM registration_members rm JOIN users u ON u.id = rm.user_id
			WHERE rm.registration_id = ? AND u.is_active = 1 AND u.email <> '' ORDER BY rm.id`
		arg = r.ID
	}
	rows, err := q.QueryContext(ctx, query, arg)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []mail.Person
	for rows.Next() {
		var p mail.Person
		if err := rows.Scan(&p.Name, &p.Address); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

var submitSubjects = map[string]string{ActSubmit: "报名已提交", ActResubmit: "报名已重新提交", ActSyncRoster: "报名名单已同步"}

func (s *Service) notifySubmitted(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, r *Registration, action string, now time.Time) error {
	to, err := s.regRecipients(ctx, tx, r)
	if err != nil || len(to) == 0 {
		return err
	}
	var lead string
	if r.Status == RegApproved {
		lead = fmt.Sprintf("「%s」报名「%s」的名单已提交，并且已经通过。", r.TeamName, t.Title)
	} else {
		lead = fmt.Sprintf("「%s」报名「%s」的名单已提交，等赛事管理员审核。", r.TeamName, t.Title)
	}
	var paragraphs []string
	if r.TeamID != nil {
		paragraphs = []string{"名单里新加的队员会各收到一封通知，不需要他们确认。"}
	}
	subject := submitSubjects[action]
	if subject == "" {
		subject = "报名已提交"
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject: subject + "：" + t.Title,
		Lead:    lead,
		Facts: [][2]string{{"赛事", t.Title}, {"队伍", r.TeamName}, {"名单版本", fmt.Sprint(r.RosterVersion)},
			{"当前状态", statusLabels[r.Status]}},
		Paragraphs: paragraphs,
		Action:     []string{"查看报名详情", s.regURL(r.ID)},
		Reason:     s.regWhy(r),
	}, to, now)
}

func (s *Service) notifyMemberEntered(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, r *Registration, row RosterMember, now time.Time) error {
	u, err := getUser(ctx, tx, row.UserID)
	if err != nil || u == nil {
		return err
	}
	by := "队长"
	if r.SubmittedBy != nil {
		if cu, err := getUser(ctx, tx, *r.SubmittedBy); err == nil && cu != nil {
			by = "队长 " + cu.Nickname + " "
		}
	}
	bt := row.Battletag
	if bt == "" {
		bt = "未填"
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject: "你已被报名参加：" + t.Title,
		Lead:    fmt.Sprintf("%s为战队「%s」报名了「%s」，你在名单里。", by, r.TeamName, t.Title),
		Facts: append([][2]string{{"赛事", t.Title}, {"队伍", r.TeamName}, {"你的游戏 ID", bt},
			{"当前状态", statusLabels[r.Status]}}, contactFact(t)...),
		Paragraphs: []string{"整队报名不需要你确认。不想参加的话，请在报名截止前联系队长。"},
		Action:     []string{"查看报名详情", s.regURL(r.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你是战队「%s」的队员。", r.TeamName),
	}, []mail.Person{person(u)}, now)
}

func (s *Service) notifyStatusChanged(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, r *Registration, note string, now time.Time) error {
	to, err := s.regRecipients(ctx, tx, r)
	if err != nil || len(to) == 0 {
		return err
	}
	label := statusLabels[r.Status]
	lead := fmt.Sprintf("「%s」报名「%s」的状态变成了：%s。", r.TeamName, t.Title, label)
	if r.Status == RegApproved {
		lead = fmt.Sprintf("「%s」报名「%s」已通过审核。", r.TeamName, t.Title)
	}
	var paragraphs []string
	if r.Status == RegRejected && r.TeamID != nil {
		paragraphs = append(paragraphs, "你可以按备注修改后，在报名截止前重新提交。")
	}
	facts := [][2]string{{"赛事", t.Title}, {"队伍", r.TeamName}}
	if r.Status == RegApproved {
		if t.StartsAt != nil {
			facts = append(facts, [2]string{"比赛时间", moment(*t.StartsAt)})
		}
		facts = append(facts, contactFact(t)...)
	}
	if note != "" {
		facts = append(facts, [2]string{"备注", note})
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "报名" + label + "：" + t.Title,
		Lead:       lead,
		Facts:      facts,
		Paragraphs: paragraphs,
		Action:     []string{"查看报名详情", s.regURL(r.ID)},
		Reason:     s.regWhy(r),
	}, to, now)
}
