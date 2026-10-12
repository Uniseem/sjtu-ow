package backoffice

import (
	"context"
	"database/sql"
	"encoding/csv"
	"errors"
	"fmt"
	"strconv"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/tournaments"
)

type RegistrationQuery struct {
	Query        string `query:"q"`
	Status       string `query:"status"`
	TournamentID int64  `query:"tournament_id"`
	Page         int    `query:"page"`
}
type RegistrationRow struct {
	MemberCount     int    `json:"member_count"`
	Deactivated     int    `json:"deactivated"`
	AutoApprove     bool   `json:"auto_approve"`
	CanRevoke       bool   `json:"can_revoke"`
	ID              int64  `json:"id"`
	TournamentID    int64  `json:"tournament_id"`
	TournamentTitle string `json:"tournament_title"`
	TeamID          *int64 `json:"team_id"`
	TeamName        string `json:"team_name"`
	Status          string `json:"status"`
	StatusNote      string `json:"status_note"`
	SubmittedAt     string `json:"submitted_at"`
	RosterVersion   int64  `json:"roster_version"`
	CanApprove      bool   `json:"can_approve"`
	CanReject       bool   `json:"can_reject"`
	CanDissolve     bool   `json:"can_dissolve"`
}
type TournamentChoice struct {
	ID    int64  `json:"id"`
	Title string `json:"title"`
}
type RegistrationListOut struct {
	Items       []RegistrationRow  `json:"items"`
	Total       int                `json:"total"`
	Page        int                `json:"page"`
	PageSize    int                `json:"page_size"`
	Tournaments []TournamentChoice `json:"tournaments"`
}

func registrationWhere(in RegistrationQuery) (string, []any, error) {
	where := "1 = 1"
	args := []any{}
	if in.TournamentID < 0 {
		return "", nil, api.Invalid("赛事编号不正确。")
	}
	if in.TournamentID > 0 {
		where += " AND r.tournament_id = ?"
		args = append(args, in.TournamentID)
	}
	if in.Status != "" {
		switch in.Status {
		case tournaments.RegPending, tournaments.RegApproved, tournaments.RegRejected, tournaments.RegWithdrawn:
		default:
			return "", nil, api.Invalid("报名状态不正确。")
		}
		where += " AND r.status = ?"
		args = append(args, in.Status)
	}
	if query := strings.TrimSpace(in.Query); query != "" {
		where += ` AND r.team_name LIKE ? ESCAPE '\'`
		escaped := strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`).Replace(query)
		args = append(args, "%"+escaped+"%")
	}
	return where, args, nil
}

const registrationColumns = `r.id, r.tournament_id, t.title, r.team_id, r.team_name, r.status, r.status_note, r.submitted_at, r.roster_version, t.status,t.auto_approve,
 (SELECT COUNT(*) FROM registration_members rm WHERE rm.registration_id=r.id),
 (SELECT COUNT(*) FROM registration_members rm JOIN users u ON u.id=rm.user_id WHERE rm.registration_id=r.id AND u.is_active=0)`
const registrationJoin = ` FROM registrations r JOIN tournaments t ON t.id = r.tournament_id `

func scanRegistrationRow(row interface{ Scan(...any) error }) (RegistrationRow, error) {
	var out RegistrationRow
	var tournamentStatus string
	if err := row.Scan(&out.ID, &out.TournamentID, &out.TournamentTitle, &out.TeamID, &out.TeamName, &out.Status, &out.StatusNote, &out.SubmittedAt, &out.RosterVersion, &tournamentStatus, &out.AutoApprove, &out.MemberCount, &out.Deactivated); err != nil {
		return out, err
	}
	open := tournamentStatus != tournaments.StatusCancelled && tournamentStatus != tournaments.StatusFinished
	out.CanApprove = open && out.Status == tournaments.RegPending
	out.CanRevoke = open && out.TeamID != nil && out.Status == tournaments.RegApproved
	out.CanReject = open && out.TeamID != nil && (out.Status == tournaments.RegPending || out.Status == tournaments.RegApproved)
	out.CanDissolve = open && out.TeamID == nil && (out.Status == tournaments.RegPending || out.Status == tournaments.RegApproved)
	return out, nil
}

func listRegistrations(ctx context.Context, q db.DBTX, in RegistrationQuery) (RegistrationListOut, error) {
	out := RegistrationListOut{Items: []RegistrationRow{}, Tournaments: []TournamentChoice{}, Page: in.Page, PageSize: 50}
	if out.Page < 1 {
		out.Page = 1
	}
	if out.Page > 1000000 {
		return out, api.Invalid("页码超出范围。")
	}
	where, args, err := registrationWhere(in)
	if err != nil {
		return out, err
	}
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*)`+registrationJoin+`WHERE `+where, args...).Scan(&out.Total); err != nil {
		return out, err
	}
	rowArgs := append(append([]any{}, args...), out.PageSize, (out.Page-1)*out.PageSize)
	rows, err := q.QueryContext(ctx, `SELECT `+registrationColumns+registrationJoin+`WHERE `+where+` ORDER BY r.submitted_at DESC, r.id DESC LIMIT ? OFFSET ?`, rowArgs...)
	if err != nil {
		return out, err
	}
	for rows.Next() {
		row, err := scanRegistrationRow(rows)
		if err != nil {
			rows.Close()
			return out, err
		}
		out.Items = append(out.Items, row)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	rows, err = q.QueryContext(ctx, `SELECT id, title FROM tournaments ORDER BY registration_opens_at DESC, id ASC`)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var tournament TournamentChoice
		if err := rows.Scan(&tournament.ID, &tournament.Title); err != nil {
			return out, err
		}
		out.Tournaments = append(out.Tournaments, tournament)
	}
	return out, rows.Err()
}
func (s *Service) registrations(ctx *app.Ctx, in RegistrationQuery) (RegistrationListOut, error) {
	if err := require(ctx, accounts.CapTournamentsManage, false); err != nil {
		return RegistrationListOut{}, err
	}
	return listRegistrations(ctx.Context, s.d.ReadPool(), in)
}

type RosterRow struct {
	TankLabel     string   `json:"tank_label"`
	DamageLabel   string   `json:"damage_label"`
	SupportLabel  string   `json:"support_label"`
	AccountActive bool     `json:"account_active"`
	ID            int64    `json:"id"`
	UserID        int64    `json:"user_id"`
	Nickname      string   `json:"nickname"`
	Battletag     string   `json:"battletag"`
	IsSJTU        bool     `json:"is_sjtu"`
	IsCaptain     bool     `json:"is_captain"`
	IsActive      bool     `json:"is_active"`
	Ranks         string   `json:"ranks"`
	Contacts      []string `json:"contacts,omitempty"`
}
type RegistrationLog struct {
	FromStatus    string `json:"from_status"`
	ToStatus      string `json:"to_status"`
	ActorType     string `json:"actor_type"`
	ID            int64  `json:"id"`
	Action        string `json:"action"`
	ActorName     string `json:"actor_name"`
	Note          string `json:"note"`
	CreatedAt     string `json:"created_at"`
	RosterVersion int64  `json:"roster_version"`
}
type RegistrationDetailOut struct {
	Added        []string          `json:"added"`
	Removed      []string          `json:"removed"`
	ShowContacts bool              `json:"show_contacts"`
	Registration RegistrationRow   `json:"registration"`
	Roster       []RosterRow       `json:"roster"`
	Logs         []RegistrationLog `json:"logs"`
	Warnings     []string          `json:"warnings"`
}

func rankText(tank, damage, support sql.NullInt64) string {
	items := []struct {
		label string
		value sql.NullInt64
	}{{"坦克", tank}, {"输出", damage}, {"支援", support}}
	out := []string{}
	for _, item := range items {
		if !item.value.Valid {
			continue
		}
		score := int(item.value.Int64)
		out = append(out, item.label+" "+accounts.FormatRank(&score))
	}
	return strings.Join(out, "、")
}
func actionText(action string) string {
	names := map[string]string{"submit": "提交报名", "resubmit": "重新提交", "approve": "通过", "reject": "驳回", "revoke": "撤销通过", "withdraw": "撤回", "dissolve": "解散临时队伍", "form": "组成临时队伍", "join": "加入名单", "leave": "退出名单"}
	if label, ok := names[action]; ok {
		return label
	}
	return action
}
func (s *Service) registration(ctx *app.Ctx, in IDIn) (RegistrationDetailOut, error) {
	out := RegistrationDetailOut{Roster: []RosterRow{}, Logs: []RegistrationLog{}, Warnings: []string{}, Added: []string{}, Removed: []string{}, ShowContacts: ctx.Viewer != nil && ctx.Viewer.HasCap(accounts.CapContactsView)}
	if err := require(ctx, accounts.CapTournamentsManage, false); err != nil {
		return out, err
	}
	q := s.d.ReadPool()
	row, err := scanRegistrationRow(q.QueryRowContext(ctx.Context, `SELECT `+registrationColumns+registrationJoin+`WHERE r.id = ?`, int64(in.ID)))
	if err == sql.ErrNoRows {
		return out, api.NotFound("报名不存在")
	}
	if err != nil {
		return out, err
	}
	out.Registration = row
	rows, err := q.QueryContext(ctx.Context, `SELECT rm.id, rm.user_id, rm.nickname, rm.battletag, rm.is_sjtu, rm.is_captain, rm.is_active, rm.rank_tank, rm.rank_damage, rm.rank_support, u.is_active FROM registration_members rm JOIN users u ON u.id = rm.user_id WHERE rm.registration_id = ? ORDER BY rm.is_captain DESC, rm.id`, int64(in.ID))
	if err != nil {
		return out, err
	}
	for rows.Next() {
		var member RosterRow
		var tank, damage, support sql.NullInt64
		var accountActive bool
		if err := rows.Scan(&member.ID, &member.UserID, &member.Nickname, &member.Battletag, &member.IsSJTU, &member.IsCaptain, &member.IsActive, &tank, &damage, &support, &accountActive); err != nil {
			rows.Close()
			return out, err
		}
		member.Ranks = rankText(tank, damage, support)
		rank := func(value sql.NullInt64) string {
			if !value.Valid {
				return accounts.FormatRank(nil)
			}
			score := int(value.Int64)
			return accounts.FormatRank(&score)
		}
		member.TankLabel, member.DamageLabel, member.SupportLabel = rank(tank), rank(damage), rank(support)
		member.AccountActive = accountActive
		if !accountActive {
			out.Warnings = append(out.Warnings, member.Nickname+"的账号已停用。")
		}
		out.Roster = append(out.Roster, member)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	if row.TeamID != nil {
		current, err := q.QueryContext(ctx.Context, `SELECT u.nickname FROM team_memberships m JOIN users u ON u.id=m.user_id WHERE m.team_id=? AND NOT EXISTS(SELECT 1 FROM registration_members rm WHERE rm.registration_id=? AND rm.user_id=m.user_id) ORDER BY m.id`, *row.TeamID, int64(in.ID))
		if err != nil {
			return out, err
		}
		for current.Next() {
			var name string
			if err := current.Scan(&name); err != nil {
				current.Close()
				return out, err
			}
			out.Added = append(out.Added, name)
		}
		current.Close()
		if err := current.Err(); err != nil {
			return out, err
		}
		removed, err := q.QueryContext(ctx.Context, `SELECT rm.nickname FROM registration_members rm WHERE rm.registration_id=? AND NOT EXISTS(SELECT 1 FROM team_memberships m WHERE m.team_id=? AND m.user_id=rm.user_id) ORDER BY rm.id`, int64(in.ID), *row.TeamID)
		if err != nil {
			return out, err
		}
		for removed.Next() {
			var name string
			if err := removed.Scan(&name); err != nil {
				removed.Close()
				return out, err
			}
			out.Removed = append(out.Removed, name)
		}
		removed.Close()
		if err := removed.Err(); err != nil {
			return out, err
		}
	}
	if ctx.Viewer.HasCap(accounts.CapContactsView) {
		contacts, err := q.QueryContext(ctx.Context, `SELECT c.user_id, c.type, c.value FROM contacts c WHERE EXISTS (SELECT 1 FROM registration_members rm WHERE rm.registration_id = ? AND rm.user_id = c.user_id) ORDER BY c.id`, int64(in.ID))
		if err != nil {
			return out, err
		}
		byUser := map[int64][]string{}
		for contacts.Next() {
			var user int64
			var kind, value string
			if err := contacts.Scan(&user, &kind, &value); err != nil {
				contacts.Close()
				return out, err
			}
			byUser[user] = append(byUser[user], contactLabel(kind)+" "+value)
		}
		contacts.Close()
		if err := contacts.Err(); err != nil {
			return out, err
		}
		for index := range out.Roster {
			out.Roster[index].Contacts = byUser[out.Roster[index].UserID]
		}
	}
	rows, err = q.QueryContext(ctx.Context, `SELECT l.id, l.action, COALESCE(u.nickname, CASE WHEN l.actor_type = 'system' THEN '系统' ELSE '已注销用户' END), l.note, l.created_at, l.roster_version,l.from_status,l.to_status,l.actor_type FROM registration_status_logs l LEFT JOIN users u ON u.id = l.actor_user_id WHERE l.registration_id = ? ORDER BY l.created_at, l.id`, int64(in.ID))
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var log RegistrationLog
		if err := rows.Scan(&log.ID, &log.Action, &log.ActorName, &log.Note, &log.CreatedAt, &log.RosterVersion, &log.FromStatus, &log.ToStatus, &log.ActorType); err != nil {
			return out, err
		}
		log.Action = actionText(log.Action)
		out.Logs = append(out.Logs, log)
	}
	return out, rows.Err()
}

type BulkApproveIn struct {
	IDs []int64 `json:"ids"`
}
type BulkFailed struct {
	ID      int64  `json:"id"`
	Message string `json:"message"`
}
type BulkApproveOut struct {
	Approved []int64      `json:"approved"`
	Failed   []BulkFailed `json:"failed"`
}

func (s *Service) bulkApprove(ctx *app.Ctx, in BulkApproveIn) (BulkApproveOut, error) {
	out := BulkApproveOut{Approved: []int64{}, Failed: []BulkFailed{}}
	if err := require(ctx, accounts.CapTournamentsManage, false); err != nil {
		return out, err
	}
	if len(in.IDs) == 0 || len(in.IDs) > 50 {
		return out, api.InvalidFields(map[string][]string{"ids": {"请选择1至50份报名。"}})
	}
	seen := map[int64]bool{}
	for _, id := range in.IDs {
		if id <= 0 || id > 999999999999999999 {
			return out, api.InvalidFields(map[string][]string{"ids": {"报名编号不正确。"}})
		}
		if seen[id] {
			return out, api.InvalidFields(map[string][]string{"ids": {"报名编号不能重复。"}})
		}
		seen[id] = true
	}
	if s.tournaments == nil {
		return out, api.NewErr(503, "unavailable", "报名审核暂时不可用。")
	}
	for _, id := range in.IDs {
		_, err := s.tournaments.Approve(ctx, id)
		if err == nil {
			out.Approved = append(out.Approved, id)
			continue
		}
		var problem *api.Error
		message := "暂时无法处理，请稍后重试。"
		if errors.As(err, &problem) && problem.Status < 500 {
			message = problem.Message
		}
		out.Failed = append(out.Failed, BulkFailed{ID: id, Message: message})
	}
	return out, nil
}

type CSVOut struct {
	Filename string `json:"filename"`
	CSV      string `json:"csv"`
}

func spreadsheetCell(value string) string {
	// Excel treats several first characters as formulas even when CSV quotes the cell.
	trimmed := strings.TrimLeft(value, " \t\r\n")
	if strings.HasPrefix(trimmed, "=") || strings.HasPrefix(trimmed, "+") || strings.HasPrefix(trimmed, "-") || strings.HasPrefix(trimmed, "@") {
		return "'" + value
	}
	if strings.HasPrefix(value, "\t") || strings.HasPrefix(value, "\r") || strings.HasPrefix(value, "\n") {
		return "'" + value
	}
	return value
}
func (s *Service) exportRegistrations(ctx *app.Ctx, in RegistrationQuery) (CSVOut, error) {
	if err := require(ctx, accounts.CapTournamentsManage, false); err != nil {
		return CSVOut{}, err
	}
	where, args, err := registrationWhere(in)
	if err != nil {
		return CSVOut{}, err
	}
	q := s.d.ReadPool()
	var total int
	if err := q.QueryRowContext(ctx.Context, `SELECT COUNT(*)`+registrationJoin+`WHERE `+where, args...).Scan(&total); err != nil {
		return CSVOut{}, err
	}
	if total > 5000 {
		return CSVOut{}, api.InvalidFields(map[string][]string{"__all__": {"导出超过5000份，请先按赛事或状态筛选。"}})
	}
	showContacts := ctx.Viewer.HasCap(accounts.CapContactsView)
	contacts := map[int64][]string{}
	if showContacts {
		contactRows, err := q.QueryContext(ctx.Context, `SELECT DISTINCT c.user_id,c.id,c.type,c.value FROM contacts c JOIN registration_members rm ON rm.user_id=c.user_id JOIN registrations r ON r.id=rm.registration_id JOIN tournaments t ON t.id=r.tournament_id WHERE `+where+` ORDER BY c.id`, args...)
		if err != nil {
			return CSVOut{}, err
		}
		for contactRows.Next() {
			var user, id int64
			var kind, value string
			if err := contactRows.Scan(&user, &id, &kind, &value); err != nil {
				contactRows.Close()
				return CSVOut{}, err
			}
			contacts[user] = append(contacts[user], contactLabel(kind)+" "+value)
		}
		contactRows.Close()
		if err := contactRows.Err(); err != nil {
			return CSVOut{}, err
		}
	}
	rows, err := q.QueryContext(ctx.Context, `SELECT r.id, t.title, r.team_name, r.status, r.submitted_at, r.roster_version, COALESCE(rm.nickname,''), COALESCE(rm.battletag,''), COALESCE(rm.is_sjtu,0), COALESCE(rm.is_captain,0), rm.rank_tank, rm.rank_damage, rm.rank_support, r.status_note,rm.user_id,r.tournament_id`+registrationJoin+`JOIN registration_members rm ON rm.registration_id = r.id WHERE `+where+` ORDER BY r.submitted_at DESC, r.id DESC, rm.is_captain DESC, rm.id`, args...)
	if err != nil {
		return CSVOut{}, err
	}
	defer rows.Close()
	var body strings.Builder
	body.WriteString("\ufeff")
	writer := csv.NewWriter(&body)
	writer.UseCRLF = true
	if err := writer.Write(func() []string {
		header := []string{"赛事", "战队", "状态", "名单版本", "提交时间", "昵称", "游戏 ID", "是否交大", "是否队长"}
		if showContacts {
			header = append(header, "联系方式")
		}
		return header
	}()); err != nil {
		return CSVOut{}, err
	}
	exportedEvents := map[int64]bool{}
	for rows.Next() {
		var id, version, user, event int64
		var title, team, status, submitted, nickname, tag, note string
		var sjtu, captain bool
		var tank, damage, support sql.NullInt64
		if err := rows.Scan(&id, &title, &team, &status, &submitted, &version, &nickname, &tag, &sjtu, &captain, &tank, &damage, &support, &note, &user, &event); err != nil {
			return CSVOut{}, err
		}
		statusNames := map[string]string{"pending": "待审核", "approved": "已通过", "rejected": "已驳回", "withdrawn": "已撤回"}
		sjtuText, captainText := "否", "否"
		if sjtu {
			sjtuText = "是"
		}
		if captain {
			captainText = "是"
		}
		when := submitted
		if parsed, err := db.ParseUTC(submitted); err == nil {
			when = parsed.In(shanghai).Format("2006-01-02 15:04")
		}
		line := []string{title, team, statusNames[status], strconv.FormatInt(version, 10), when, nickname, tag, sjtuText, captainText}
		if showContacts {
			line = append(line, strings.Join(contacts[user], "；"))
		}
		exportedEvents[event] = true
		for i := range line {
			line[i] = spreadsheetCell(line[i])
		}
		if err := writer.Write(line); err != nil {
			return CSVOut{}, err
		}
	}
	if err := rows.Err(); err != nil {
		return CSVOut{}, err
	}
	writer.Flush()
	if err := writer.Error(); err != nil {
		return CSVOut{}, err
	}
	if in.TournamentID > 0 {
		exportedEvents[in.TournamentID] = true
	}
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		for event := range exportedEvents {
			if err := audit.Record(txCtx, tx, ctx.Viewer.ID, "registration.export", "tournament", event, map[string]any{"status": in.Status, "count": total, "contacts": showContacts}, ctx.Now()); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return CSVOut{}, err
	}
	return CSVOut{Filename: fmt.Sprintf("registrations-%s.csv", ctx.Now().In(shanghai).Format("20060102-1504")), CSV: body.String()}, nil
}

func contactLabel(kind string) string {
	if label, ok := accounts.AllContactTypes[kind]; ok {
		return label
	}
	return kind
}
