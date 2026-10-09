package tournaments

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ViewerBuilder 按用户编号组出他的 Viewer（can_use 的判定要它）。main 里接 accounts.Service.BuildViewer。
type ViewerBuilder func(ctx context.Context, userID int64) (*app.Viewer, error)

// SetViewerBuilder 接上 Viewer 的组装。
func (s *Service) SetViewerBuilder(b ViewerBuilder) { s.viewers = b }

// 现行站的固定文案。
const (
	TeamsRefused       = "这项赛事是个人报名，不接受战队报名"
	IndividualsRefused = "这项赛事只接受战队报名"
	NotInWindow        = "当前不在报名时间内"
)

func problems(list []string) error {
	return api.InvalidFields(map[string][]string{"__all__": list})
}

// canRegister 这个人能不能用赛事报名这项功能（规则 116：对队长隐藏原因）。
func (s *Service) canRegister(ctx context.Context, userID int64) (bool, error) {
	if s.viewers == nil {
		return true, nil
	}
	v, err := s.viewers(ctx, userID)
	if err != nil {
		return false, err
	}
	return v != nil && !v.Disabled && v.CanUse(accounts.FeatureTournamentRegister), nil
}

// memberProblems 一个人自己的问题（规则 116）：功能被限制、资料不完整、仅限交大。
func (s *Service) memberProblems(ctx context.Context, q db.DBTX, t *Tournament, userID int64, asSelf bool) ([]string, error) {
	u, err := getUser(ctx, q, userID)
	if err != nil {
		return nil, err
	}
	if u == nil {
		return []string{"成员不存在"}, nil
	}
	var out []string
	ok, err := s.canRegister(ctx, userID)
	if err != nil {
		return nil, err
	}
	who := u.Nickname + " "
	if asSelf {
		who = "你"
	}
	if !ok {
		if asSelf {
			out = append(out, accounts.FeatureDeniedMessage)
		} else {
			out = append(out, u.Nickname+" 暂时无法参加赛事报名")
		}
	}
	var games, contacts int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM game_accounts WHERE user_id = ?`, userID).Scan(&games); err != nil {
		return nil, err
	}
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM contacts WHERE user_id = ?`, userID).Scan(&contacts); err != nil {
		return nil, err
	}
	var gaps []string
	if games < 1 {
		gaps = append(gaps, "游戏 ID")
	}
	if contacts < 1 {
		gaps = append(gaps, "联系方式")
	}
	if len(gaps) > 0 {
		out = append(out, fmt.Sprintf("%s的资料不完整（缺少%s）", who, strings.Join(gaps, "、")))
	}
	if t.SjtuOnly && !u.IsSJTU {
		out = append(out, fmt.Sprintf("该赛事仅限交大用户参加，%s不符合", strings.TrimSpace(who)))
	}
	return out, nil
}

// rosterConflict 这个人已经在别的活跃名单上（规则 117）。
func (s *Service) rosterConflict(ctx context.Context, q db.DBTX, tournamentID, userID, excludeReg int64) (string, error) {
	var name string
	err := q.QueryRowContext(ctx, `SELECT r.team_name FROM registration_members rm
		JOIN registrations r ON r.id = rm.registration_id
		WHERE rm.tournament_id = ? AND rm.user_id = ? AND rm.is_active = 1 AND rm.registration_id <> ?
		ORDER BY rm.id LIMIT 1`, tournamentID, userID, excludeReg).Scan(&name)
	if err == sql.ErrNoRows {
		return "", nil
	}
	if err != nil {
		return "", err
	}
	u, err := getUser(ctx, q, userID)
	if err != nil || u == nil {
		return "", err
	}
	return fmt.Sprintf("%s 已经在该赛事的战队「%s」名单中", u.Nickname, name), nil
}

type teamMember struct {
	UserID    int64
	IsCaptain bool
	Nickname  string
	IsSJTU    bool
}

func teamMembers(ctx context.Context, q db.DBTX, teamID int64) ([]teamMember, error) {
	rows, err := q.QueryContext(ctx, `SELECT m.user_id, m.role = 'captain', u.nickname, u.is_sjtu
		FROM team_memberships m JOIN users u ON u.id = m.user_id WHERE m.team_id = ?
		ORDER BY m.role, m.joined_at, m.id`, teamID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []teamMember
	for rows.Next() {
		var m teamMember
		var cap, sjtu int
		if err := rows.Scan(&m.UserID, &cap, &m.Nickname, &sjtu); err != nil {
			return nil, err
		}
		m.IsCaptain, m.IsSJTU = cap == 1, sjtu == 1
		out = append(out, m)
	}
	return out, rows.Err()
}

func isTeamCaptain(ctx context.Context, q db.DBTX, teamID, userID int64) (bool, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM team_memberships m JOIN teams t ON t.id = m.team_id
		WHERE m.team_id = ? AND m.user_id = ? AND m.role = 'captain' AND t.disbanded_at IS NULL`, teamID, userID).Scan(&n)
	return n > 0, err
}

// precheck 提交前的预检，所有问题一次列出（规则 115）。
func (s *Service) precheck(ctx context.Context, q db.DBTX, t *Tournament, teamID, actorID, excludeReg int64, now time.Time) ([]string, error) {
	var out []string
	if !t.TakesTeams() {
		out = append(out, TeamsRefused)
	}
	if t.Status != StatusPublished || t.RegistrationOpensAt == nil || t.RegistrationClosesAt == nil ||
		now.Before(*t.RegistrationOpensAt) || now.After(*t.RegistrationClosesAt) {
		out = append(out, NotInWindow)
	}
	captain, err := isTeamCaptain(ctx, q, teamID, actorID)
	if err != nil {
		return nil, err
	}
	if !captain {
		out = append(out, "只有队长可以为战队报名")
	}
	members, err := teamMembers(ctx, q, teamID)
	if err != nil {
		return nil, err
	}
	if n := len(members); n < t.RosterMin || n > t.RosterMax {
		out = append(out, fmt.Sprintf("该赛事要求 %d 到 %d 人，你的战队现在有 %d 人", t.RosterMin, t.RosterMax, n))
	}
	for _, m := range members {
		ps, err := s.memberProblems(ctx, q, t, m.UserID, false)
		if err != nil {
			return nil, err
		}
		out = append(out, ps...)
		c, err := s.rosterConflict(ctx, q, t.ID, m.UserID, excludeReg)
		if err != nil {
			return nil, err
		}
		if c != "" {
			out = append(out, c)
		}
	}
	return out, nil
}

type chosenAccount struct {
	ID        int64
	Battletag string
	Tank      *int
	Damage    *int
	Support   *int
}

// resolveAccounts 每个成员选的游戏 ID 必须是自己的；没选或无效回落到第一个（规则 118）。
func resolveAccounts(ctx context.Context, q db.DBTX, members []teamMember, selections map[string]int64) (map[int64]*chosenAccount, []string, error) {
	out := map[int64]*chosenAccount{}
	var probs []string
	for _, m := range members {
		var acc *chosenAccount
		if id := selections[strconv.FormatInt(m.UserID, 10)]; id > 0 {
			a, err := loadAccount(ctx, q, `SELECT id, battletag, rank_tank, rank_damage, rank_support FROM game_accounts WHERE id = ? AND user_id = ?`, id, m.UserID)
			if err != nil {
				return nil, nil, err
			}
			if a == nil {
				probs = append(probs, "游戏 ID 选择有误，请刷新页面重试")
			}
			acc = a
		}
		if acc == nil {
			a, err := loadAccount(ctx, q, `SELECT id, battletag, rank_tank, rank_damage, rank_support FROM game_accounts WHERE user_id = ? ORDER BY id LIMIT 1`, m.UserID)
			if err != nil {
				return nil, nil, err
			}
			acc = a
		}
		if acc == nil {
			probs = append(probs, m.Nickname+" 还没有填写游戏 ID")
		}
		out[m.UserID] = acc
	}
	return out, probs, nil
}

func loadAccount(ctx context.Context, q db.DBTX, query string, args ...any) (*chosenAccount, error) {
	var a chosenAccount
	var tank, damage, support sql.NullInt64
	err := q.QueryRowContext(ctx, query, args...).Scan(&a.ID, &a.Battletag, &tank, &damage, &support)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	for _, p := range []struct {
		n   sql.NullInt64
		dst **int
	}{{tank, &a.Tank}, {damage, &a.Damage}, {support, &a.Support}} {
		if p.n.Valid {
			v := int(p.n.Int64)
			*p.dst = &v
		}
	}
	return &a, nil
}

func intArg(p *int) any {
	if p == nil {
		return nil
	}
	return *p
}

// writeRoster 名单是快照：昵称、游戏 ID、段位、是否交大、是否队长，提交时定格（规则 119）。
func writeRoster(ctx context.Context, tx *db.Tx, reg *Registration, members []teamMember, chosen map[int64]*chosenAccount) ([]RosterMember, error) {
	if _, err := tx.ExecContext(ctx, `DELETE FROM registration_members WHERE registration_id = ?`, reg.ID); err != nil {
		return nil, err
	}
	active := b2i(reg.Active())
	for _, m := range members {
		a := chosen[m.UserID]
		var gaID any
		battletag := ""
		var tank, damage, support any
		if a != nil {
			gaID, battletag = a.ID, a.Battletag
			tank, damage, support = intArg(a.Tank), intArg(a.Damage), intArg(a.Support)
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO registration_members
			(registration_id, tournament_id, user_id, game_account_id, nickname, battletag, is_sjtu,
			 rank_tank, rank_damage, rank_support, is_captain, is_active)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
			reg.ID, reg.TournamentID, m.UserID, gaID, m.Nickname, battletag, b2i(m.IsSJTU),
			tank, damage, support, b2i(m.IsCaptain), active); err != nil {
			return nil, err
		}
	}
	return roster(ctx, tx, reg.ID)
}

func snapshotJSON(rows []RosterMember) string {
	type item struct {
		Nickname    string `json:"nickname"`
		Battletag   string `json:"battletag"`
		IsSJTU      bool   `json:"is_sjtu"`
		IsCaptain   bool   `json:"is_captain"`
		RankTank    *int   `json:"rank_tank"`
		RankDamage  *int   `json:"rank_damage"`
		RankSupport *int   `json:"rank_support"`
	}
	list := make([]item, 0, len(rows))
	for _, r := range rows {
		list = append(list, item{r.Nickname, r.Battletag, r.IsSJTU, r.IsCaptain, r.RankTank, r.RankDamage, r.RankSupport})
	}
	b, _ := json.Marshal(list)
	return string(b)
}

// SubmitInput 是整队报名的入参。Accounts 是 用户编号 → 所选游戏 ID 编号。
type SubmitInput struct {
	TournamentID int64
	TeamID       int64
	Accounts     map[string]int64
}

// Submit 首次提交、重新提交、同步名单都走这里（规则 115–121）。
func (s *Service) Submit(ctx *app.Ctx, in SubmitInput) (*Registration, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *Registration
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, in.TournamentID)
		if err != nil {
			return err
		}
		if t == nil || !t.IsPublic() {
			return api.NotFound("赛事不存在")
		}
		var team struct{ ID int64 }
		var teamName string
		if err := tx.QueryRowContext(txCtx, `SELECT id, name FROM teams WHERE id = ? AND disbanded_at IS NULL`, in.TeamID).Scan(&team.ID, &teamName); err != nil {
			if err == sql.ErrNoRows {
				return api.NotFound("战队不存在")
			}
			return err
		}
		var existing *Registration
		{
			r, err := scanRegistration(tx.QueryRowContext(txCtx, `SELECT `+regCols+` FROM registrations WHERE tournament_id = ? AND team_id = ?`, t.ID, team.ID))
			if err != nil && err != sql.ErrNoRows {
				return err
			}
			if err == nil {
				existing = r
			}
		}
		action, fromStatus := ActSubmit, ""
		var excl int64
		if existing != nil {
			fromStatus, excl = existing.Status, existing.ID
			if existing.Active() {
				action = ActSyncRoster
			} else {
				action = ActResubmit
			}
		}
		probs, err := s.precheck(txCtx, tx, t, team.ID, v.ID, excl, now)
		if err != nil {
			return err
		}
		members, err := teamMembers(txCtx, tx, team.ID)
		if err != nil {
			return err
		}
		chosen, accProbs, err := resolveAccounts(txCtx, tx, members, in.Accounts)
		if err != nil {
			return err
		}
		probs = append(probs, accProbs...)
		if len(probs) > 0 {
			return problems(probs)
		}

		// 新进活跃名单的非队长队员各收一封「你已被报名参加」（规则 121）；被驳回/撤回的名单不占名额，重新提交时全员再通知。
		alreadyOn := map[int64]bool{}
		if existing != nil {
			rows, err := tx.QueryContext(txCtx, `SELECT user_id FROM registration_members WHERE registration_id = ? AND is_active = 1`, existing.ID)
			if err != nil {
				return err
			}
			for rows.Next() {
				var uid int64
				if err := rows.Scan(&uid); err != nil {
					rows.Close()
					return err
				}
				alreadyOn[uid] = true
			}
			rows.Close()
		}
		var reg *Registration
		if existing == nil {
			res, err := tx.ExecContext(txCtx, `INSERT INTO registrations
				(tournament_id, team_id, status, team_name, roster_version, submitted_by, submitted_at, status_note, created_at, updated_at)
				VALUES (?, ?, 'pending', ?, 1, ?, ?, '', ?, ?)`,
				t.ID, team.ID, teamName, v.ID, db.FormatUTC(now), db.FormatUTC(now), db.FormatUTC(now))
			if err != nil {
				return err
			}
			id, err := res.LastInsertId()
			if err != nil {
				return err
			}
			reg, err = GetRegistration(txCtx, tx, id)
			if err != nil {
				return err
			}
		} else {
			if _, err := tx.ExecContext(txCtx, `UPDATE registrations SET team_name = ?, status = 'pending', submitted_by = ?,
				submitted_at = ?, status_note = '', roster_version = roster_version + 1, updated_at = ? WHERE id = ?`,
				teamName, v.ID, db.FormatUTC(now), db.FormatUTC(now), existing.ID); err != nil {
				return err
			}
			reg, err = GetRegistration(txCtx, tx, existing.ID)
			if err != nil {
				return err
			}
		}
		rows, err := writeRoster(txCtx, tx, reg, members, chosen)
		if err != nil {
			return err
		}
		if err := logRegistration(txCtx, tx, reg.ID, action, fromStatus, reg.Status, ActorCaptain, &v.ID, reg.RosterVersion, snapshotJSON(rows), "", now); err != nil {
			return err
		}
		if t.AutoApprove {
			// 同一个事务里由系统通过；状态变更信不发，提交信里已写「已经通过」（规则 120）。
			reg, err = s.setStatus(txCtx, tx, ctx, t, reg, ActApprove, RegApproved, ActorSystem, nil, AutoApproveNote, false, now)
			if err != nil {
				return err
			}
		}
		if err := s.notifySubmitted(txCtx, tx, ctx, t, reg, action, now); err != nil {
			return err
		}
		for _, row := range rows {
			if !row.IsCaptain && !alreadyOn[row.UserID] {
				if err := s.notifyMemberEntered(txCtx, tx, ctx, t, reg, row, now); err != nil {
					return err
				}
			}
		}
		out = reg
		return nil
	})
	if isUnique(err) {
		return nil, problems([]string{"名单里有人刚被别的队报名了，请刷新页面再试"})
	}
	return out, err
}

func isUnique(err error) bool {
	return err != nil && strings.Contains(err.Error(), "UNIQUE constraint failed")
}

// setStatus 改状态：写状态、让名单占不占名额跟着变（规则 122）、写日志（规则 123）、通知。
func (s *Service) setStatus(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, reg *Registration, action, to, actorType string, actor *int64, note string, snapshot bool, now time.Time) (*Registration, error) {
	from := reg.Status
	if _, err := tx.ExecContext(ctx, `UPDATE registrations SET status = ?, status_note = ?, updated_at = ? WHERE id = ?`,
		to, note, db.FormatUTC(now), reg.ID); err != nil {
		return nil, err
	}
	active := to == RegPending || to == RegApproved
	if _, err := tx.ExecContext(ctx, `UPDATE registration_members SET is_active = ? WHERE registration_id = ?`, b2i(active), reg.ID); err != nil {
		return nil, err
	}
	reg.Status, reg.StatusNote = to, note
	snap := ""
	if snapshot {
		rows, err := roster(ctx, tx, reg.ID)
		if err != nil {
			return nil, err
		}
		snap = snapshotJSON(rows)
	}
	if err := logRegistration(ctx, tx, reg.ID, action, from, to, actorType, actor, reg.RosterVersion, snap, note, now); err != nil {
		return nil, err
	}
	// 队长收到每一次管理员变更的通知；系统操作不发（规则 123）
	if actorType != ActorSystem {
		if err := s.notifyStatusChanged(ctx, tx, c, t, reg, note, now); err != nil {
			return nil, err
		}
	}
	return reg, nil
}

// stillOpen 赛事已取消或已结束后不能再审核、不能再编队（规则 126）。
func stillOpen(t *Tournament) error {
	switch t.Status {
	case StatusCancelled:
		return refuse("赛事已取消，不能再审核或编队。")
	case StatusFinished:
		return refuse("赛事已结束，不能再审核或编队。")
	}
	return nil
}

func (s *Service) withRegistration(ctx *app.Ctx, regID int64, fn func(txCtx context.Context, tx *db.Tx, t *Tournament, r *Registration, now time.Time) error) (*Registration, error) {
	now := ctx.Now().UTC()
	var out *Registration
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		r, err := GetRegistration(txCtx, tx, regID)
		if err != nil {
			return err
		}
		if r == nil {
			return api.NotFound("报名不存在")
		}
		t, err := GetTournament(txCtx, tx, r.TournamentID)
		if err != nil {
			return err
		}
		if err := fn(txCtx, tx, t, r, now); err != nil {
			return err
		}
		out, err = GetRegistration(txCtx, tx, regID)
		return err
	})
	return out, err
}

// Approve 管理员通过一条待审报名（规则 122）。
func (s *Service) Approve(ctx *app.Ctx, regID int64) (*Registration, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	return s.withRegistration(ctx, regID, func(txCtx context.Context, tx *db.Tx, t *Tournament, r *Registration, now time.Time) error {
		if err := stillOpen(t); err != nil {
			return err
		}
		if r.Status != RegPending {
			return refuse("当前状态不能通过")
		}
		_, err := s.setStatus(txCtx, tx, ctx, t, r, ActApprove, RegApproved, ActorAdmin, &v.ID, "", false, now)
		return err
	})
}

// Reject 驳回待审的，或撤销已通过的（规则 125）：必须填备注（≤300 字）；临时队伍不能在这里驳回。
func (s *Service) Reject(ctx *app.Ctx, regID int64, note string) (*Registration, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	return s.withRegistration(ctx, regID, func(txCtx context.Context, tx *db.Tx, t *Tournament, r *Registration, now time.Time) error {
		if r.Adhoc() {
			return refuse("临时队伍请在「队伍编排」里调整，这里不能驳回。")
		}
		if err := stillOpen(t); err != nil {
			return err
		}
		note = strings.TrimSpace(note)
		if note == "" {
			return api.InvalidFields(map[string][]string{"note": {"驳回必须填写备注"}})
		}
		action := ActReject
		switch r.Status {
		case RegApproved:
			action = ActRevoke
		case RegPending:
		default:
			return refuse("当前状态不能驳回")
		}
		if utf8.RuneCountInString(note) > NoteMax {
			note = string([]rune(note)[:NoteMax])
		}
		_, err := s.setStatus(txCtx, tx, ctx, t, r, action, RegRejected, ActorAdmin, &v.ID, note, false, now)
		return err
	})
}

// Withdraw 队长撤回报名：仅限活跃状态、报名截止前（规则 124）。
func (s *Service) Withdraw(ctx *app.Ctx, regID int64) (*Registration, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	return s.withRegistration(ctx, regID, func(txCtx context.Context, tx *db.Tx, t *Tournament, r *Registration, now time.Time) error {
		if r.TeamID == nil {
			return refuse("临时队伍由管理员解散，队员可以退出队伍")
		}
		if ok, err := isTeamCaptain(txCtx, tx, *r.TeamID, v.ID); err != nil {
			return err
		} else if !ok {
			return deny("只有队长可以撤回报名")
		}
		if !r.Active() {
			return refuse("当前状态不能撤回")
		}
		if t.RegistrationClosesAt != nil && now.After(*t.RegistrationClosesAt) {
			return refuse("报名已截止，不能再修改")
		}
		_, err := s.setStatus(txCtx, tx, ctx, t, r, ActWithdraw, RegWithdrawn, ActorCaptain, &v.ID, "", false, now)
		return err
	})
}
