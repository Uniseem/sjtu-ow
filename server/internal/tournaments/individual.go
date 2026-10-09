package tournaments

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

// SignupView 是一个人自己的个人报名。
type SignupView struct {
	ID             int64     `json:"id"`
	GameAccountID  *int64    `json:"game_account_id"`
	Roles          []string  `json:"roles"`
	Placed         bool      `json:"placed"`
	RegistrationID *int64    `json:"registration_id"`
	CreatedAt      time.Time `json:"created_at"`
}

func rolesOf(tank, damage, support bool) []string {
	out := []string{}
	if tank {
		out = append(out, "tank")
	}
	if damage {
		out = append(out, "damage")
	}
	if support {
		out = append(out, "support")
	}
	return out
}

func getSignup(ctx context.Context, q db.DBTX, tournamentID, userID int64) (*IndividualSignup, error) {
	return scanSignupRow(q.QueryRowContext(ctx, `SELECT id, tournament_id, user_id, game_account_id, role_tank, role_damage,
		role_support, registration_id, created_at, updated_at FROM individual_signups WHERE tournament_id = ? AND user_id = ?`,
		tournamentID, userID))
}

func scanSignupRow(row interface{ Scan(...any) error }) (*IndividualSignup, error) {
	var s IndividualSignup
	var ga, reg sql.NullInt64
	var tank, damage, support int
	var created, updated string
	err := row.Scan(&s.ID, &s.TournamentID, &s.UserID, &ga, &tank, &damage, &support, &reg, &created, &updated)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if ga.Valid {
		x := ga.Int64
		s.GameAccountID = &x
	}
	if reg.Valid {
		x := reg.Int64
		s.RegistrationID = &x
	}
	s.RoleTank, s.RoleDamage, s.RoleSupport = tank == 1, damage == 1, support == 1
	s.CreatedAt, s.UpdatedAt = parseTime(created), parseTime(updated)
	return &s, nil
}

func viewOf(s *IndividualSignup) *SignupView {
	return &SignupView{ID: s.ID, GameAccountID: s.GameAccountID, Roles: rolesOf(s.RoleTank, s.RoleDamage, s.RoleSupport),
		Placed: s.Placed(), RegistrationID: s.RegistrationID, CreatedAt: s.CreatedAt}
}

// individualProblems 这个人个人报名为什么现在不行（规则 128）。
func (s *Service) individualProblems(ctx context.Context, q db.DBTX, t *Tournament, userID int64, now time.Time) ([]string, error) {
	var out []string
	if !t.TakesIndividuals() {
		out = append(out, IndividualsRefused)
	}
	if !t.RegistrationOpen(now) {
		out = append(out, NotInWindow)
	}
	ps, err := s.memberProblems(ctx, q, t, userID, true)
	if err != nil {
		return nil, err
	}
	out = append(out, ps...)
	c, err := s.rosterConflict(ctx, q, t.ID, userID, 0)
	if err != nil {
		return nil, err
	}
	if c != "" {
		out = append(out, c)
	}
	return out, nil
}

func (s *Service) fillIndividualState(ctx *app.Ctx, rd db.DBTX, t *Tournament, v *app.Viewer, now time.Time, vs *ViewerState) error {
	sg, err := getSignup(ctx.Context, rd, t.ID, v.ID)
	if err != nil {
		return err
	}
	if sg != nil {
		vs.MySignup = viewOf(sg)
		return nil
	}
	p, err := s.individualProblems(ctx.Context, rd, t, v.ID, now)
	if err != nil {
		return err
	}
	if p != nil {
		vs.IndividualProblems = p
	}
	return nil
}

// PoolEntry 是散人池里的一个人。
type PoolEntry struct {
	SignupID int64    `json:"signup_id"`
	UserID   int64    `json:"user_id"`
	Nickname string   `json:"nickname"`
	Roles    []string `json:"roles"`
}

// PoolView 是还在等编队的人和各位置的人数。
type PoolView struct {
	Total   int         `json:"total"`
	Tank    int         `json:"tank"`
	Damage  int         `json:"damage"`
	Support int         `json:"support"`
	Entries []PoolEntry `json:"entries"`
}

func (s *Service) pool(ctx context.Context, q db.DBTX, tournamentID int64) (*PoolView, error) {
	rows, err := q.QueryContext(ctx, `SELECT g.id, g.user_id, u.nickname, g.role_tank, g.role_damage, g.role_support
		FROM individual_signups g JOIN users u ON u.id = g.user_id
		WHERE g.tournament_id = ? AND g.registration_id IS NULL ORDER BY g.created_at, g.id`, tournamentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	pv := &PoolView{Entries: []PoolEntry{}}
	for rows.Next() {
		var e PoolEntry
		var tank, damage, support int
		if err := rows.Scan(&e.SignupID, &e.UserID, &e.Nickname, &tank, &damage, &support); err != nil {
			return nil, err
		}
		e.Roles = rolesOf(tank == 1, damage == 1, support == 1)
		pv.Total++
		pv.Tank += tank
		pv.Damage += damage
		pv.Support += support
		pv.Entries = append(pv.Entries, e)
	}
	return pv, rows.Err()
}

// SignupInput 是个人报名的入参。
type SignupInput struct {
	TournamentID  int64
	GameAccountID int64
	Roles         []string
}

// SignUpIndividual 建立或更新自己的散人池条目（规则 128、129）。
func (s *Service) SignUpIndividual(ctx *app.Ctx, in SignupInput) (*SignupView, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var out *SignupView
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, in.TournamentID)
		if err != nil {
			return err
		}
		if t == nil || !t.IsPublic() {
			return api.NotFound("赛事不存在")
		}
		probs, err := s.individualProblems(txCtx, tx, t, v.ID, now)
		if err != nil {
			return err
		}
		var acc *chosenAccount
		if in.GameAccountID > 0 {
			acc, err = loadAccount(txCtx, tx, `SELECT id, battletag, rank_tank, rank_damage, rank_support FROM game_accounts WHERE id = ? AND user_id = ?`, in.GameAccountID, v.ID)
			if err != nil {
				return err
			}
		}
		if acc == nil {
			probs = append(probs, "请选择你自己的游戏 ID")
		}
		var tank, damage, support int
		for _, r := range in.Roles {
			switch r {
			case "tank":
				tank = 1
			case "damage":
				damage = 1
			case "support":
				support = 1
			}
		}
		if tank+damage+support == 0 {
			probs = append(probs, "至少要勾选一个能打的位置")
		}
		// 已有条目且已被编队：不能自己改（规则 129）。放在窗口检查之后也一样要拦。
		existing, err := getSignup(txCtx, tx, t.ID, v.ID)
		if err != nil {
			return err
		}
		if existing != nil && existing.Placed() {
			return refuse("你已经被编入队伍，要改动请联系赛事管理员")
		}
		if len(probs) > 0 {
			return problems(probs)
		}
		if existing == nil {
			if _, err := tx.ExecContext(txCtx, `INSERT INTO individual_signups
				(tournament_id, user_id, game_account_id, role_tank, role_damage, role_support, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
				t.ID, v.ID, acc.ID, tank, damage, support, db.FormatUTC(now), db.FormatUTC(now)); err != nil {
				return err
			}
		} else if _, err := tx.ExecContext(txCtx, `UPDATE individual_signups SET game_account_id = ?, role_tank = ?, role_damage = ?,
			role_support = ?, updated_at = ? WHERE id = ?`, acc.ID, tank, damage, support, db.FormatUTC(now), existing.ID); err != nil {
			return err
		}
		sg, err := getSignup(txCtx, tx, t.ID, v.ID)
		if err != nil {
			return err
		}
		out = viewOf(sg)
		return nil
	})
	if isUnique(err) {
		return nil, refuse("你已经报名过这项赛事了")
	}
	return out, err
}

// CancelIndividual 报名截止前退出散人池（规则 129）；已编队的要先退出队伍。
func (s *Service) CancelIndividual(ctx *app.Ctx, tournamentID int64) error {
	v, err := requireLogin(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, tournamentID)
		if err != nil {
			return err
		}
		if t == nil || !t.IsPublic() {
			return api.NotFound("赛事不存在")
		}
		sg, err := getSignup(txCtx, tx, tournamentID, v.ID)
		if err != nil {
			return err
		}
		if sg == nil {
			return refuse("你还没有个人报名这项赛事")
		}
		if sg.Placed() {
			return refuse("你已经被编入队伍，要退出请在报名详情页操作")
		}
		if t.RegistrationClosesAt != nil && now.After(*t.RegistrationClosesAt) {
			return refuse("报名已截止，不能再取消")
		}
		_, err = tx.ExecContext(txCtx, `DELETE FROM individual_signups WHERE id = ?`, sg.ID)
		return err
	})
}

// BoardEntry 是编队板上的一个人。
type BoardEntry struct {
	SignupID       int64    `json:"signup_id"`
	UserID         int64    `json:"user_id"`
	Nickname       string   `json:"nickname"`
	Battletag      string   `json:"battletag"`
	Roles          []string `json:"roles"`
	RankTank       *int     `json:"rank_tank"`
	RankDamage     *int     `json:"rank_damage"`
	RankSupport    *int     `json:"rank_support"`
	RegistrationID *int64   `json:"registration_id"`
	Conflict       string   `json:"conflict,omitempty"`
}

// BoardTeam 是编队板上的一支临时队伍。
type BoardTeam struct {
	RegistrationID int64   `json:"registration_id"`
	Name           string  `json:"name"`
	Version        int64   `json:"roster_version"`
	SignupIDs      []int64 `json:"signup_ids"`
}

// Board 是队伍编排页要的全部。
type Board struct {
	Tournament *Card        `json:"tournament"`
	RosterMax  int          `json:"roster_max"`
	Entries    []BoardEntry `json:"entries"`
	Teams      []BoardTeam  `json:"teams"`
}

// GetBoard 读编队板：全部个人报名（含已编队的）和活跃的临时队伍。
func (s *Service) GetBoard(ctx *app.Ctx, tournamentID int64) (*Board, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	t, err := GetTournament(ctx.Context, rd, tournamentID)
	if err != nil {
		return nil, err
	}
	if t == nil {
		return nil, api.NotFound("赛事不存在")
	}
	c := cardOf(t, ctx.Now().UTC(), 0)
	b := &Board{Tournament: &c, RosterMax: t.RosterMax, Entries: []BoardEntry{}, Teams: []BoardTeam{}}
	rows, err := rd.QueryContext(ctx.Context, `SELECT g.id, g.user_id, u.nickname, COALESCE(a.battletag, ''), g.role_tank, g.role_damage,
		g.role_support, a.rank_tank, a.rank_damage, a.rank_support, g.registration_id
		FROM individual_signups g JOIN users u ON u.id = g.user_id LEFT JOIN game_accounts a ON a.id = g.game_account_id
		WHERE g.tournament_id = ? ORDER BY g.created_at, g.id`, tournamentID)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var e BoardEntry
		var tank, damage, support int
		var rt, rd2, rs, reg sql.NullInt64
		if err := rows.Scan(&e.SignupID, &e.UserID, &e.Nickname, &e.Battletag, &tank, &damage, &support, &rt, &rd2, &rs, &reg); err != nil {
			rows.Close()
			return nil, err
		}
		e.Roles = rolesOf(tank == 1, damage == 1, support == 1)
		for _, p := range []struct {
			n   sql.NullInt64
			dst **int
		}{{rt, &e.RankTank}, {rd2, &e.RankDamage}, {rs, &e.RankSupport}} {
			if p.n.Valid {
				x := int(p.n.Int64)
				*p.dst = &x
			}
		}
		if reg.Valid {
			x := reg.Int64
			e.RegistrationID = &x
		}
		b.Entries = append(b.Entries, e)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	for i := range b.Entries {
		var excl int64
		if b.Entries[i].RegistrationID != nil {
			excl = *b.Entries[i].RegistrationID
		}
		c, err := s.rosterConflict(ctx.Context, rd, tournamentID, b.Entries[i].UserID, excl)
		if err != nil {
			return nil, err
		}
		b.Entries[i].Conflict = c
	}
	regs, err := s.adhocRegistrations(ctx.Context, rd, tournamentID)
	if err != nil {
		return nil, err
	}
	for _, r := range regs {
		bt := BoardTeam{RegistrationID: r.ID, Name: r.TeamName, Version: r.RosterVersion, SignupIDs: []int64{}}
		srows, err := rd.QueryContext(ctx.Context, `SELECT id FROM individual_signups WHERE registration_id = ? ORDER BY id`, r.ID)
		if err != nil {
			return nil, err
		}
		for srows.Next() {
			var id int64
			if err := srows.Scan(&id); err != nil {
				srows.Close()
				return nil, err
			}
			bt.SignupIDs = append(bt.SignupIDs, id)
		}
		srows.Close()
		b.Teams = append(b.Teams, bt)
	}
	return b, nil
}

func (s *Service) adhocRegistrations(ctx context.Context, q db.DBTX, tournamentID int64) ([]*Registration, error) {
	rows, err := q.QueryContext(ctx, `SELECT `+regCols+` FROM registrations WHERE tournament_id = ? AND team_id IS NULL
		AND status IN ('pending', 'approved') ORDER BY submitted_at, id`, tournamentID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Registration
	for rows.Next() {
		r, err := scanRegistration(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// LayoutTeam 是编队板上一支队伍的新布局；RegistrationID 为空是新队。
type LayoutTeam struct {
	RegistrationID *int64  `json:"registration_id"`
	Name           string  `json:"name"`
	SignupIDs      []int64 `json:"signup_ids"`
	BaseVersion    int64   `json:"base_version"`
}

// FormResult 是编队的结果。
type FormResult struct {
	Created   int `json:"created"`
	Updated   int `json:"updated"`
	Dissolved int `json:"dissolved"`
	Returned  int `json:"returned"`
}

type plan struct {
	reg  *Registration
	name string
	ids  []int64
}

func nameProblems(ctx context.Context, q db.DBTX, tournamentID int64, name string, exclude int64) ([]string, error) {
	if name == "" {
		return []string{"队伍要有名字"}, nil
	}
	if n := len([]rune(name)); n > TeamNameMax {
		return []string{fmt.Sprintf("队名「%s…」超过 %d 字", string([]rune(name)[:TeamNameMax]), TeamNameMax)}, nil
	}
	var n int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM registrations WHERE tournament_id = ?
		AND status IN ('pending', 'approved') AND lower(team_name) = lower(?) AND id <> ?`, tournamentID, name, exclude).Scan(&n); err != nil {
		return nil, err
	}
	if n > 0 {
		return []string{fmt.Sprintf("队名「%s」在这项赛事里已经有了", name)}, nil
	}
	return nil, nil
}

// FormTeams 应用编队板（规则 130–133）：先全部校验，任何一条错误整个操作不生效；先从原队移出
// 再写入，避免一人一活跃名单的约束在移动时触发；布局里缺席的现有临时队全员回散人池并解散。
func (s *Service) FormTeams(ctx *app.Ctx, tournamentID int64, layout []LayoutTeam) (*FormResult, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	res := &FormResult{}
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := GetTournament(txCtx, tx, tournamentID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("赛事不存在")
		}
		if err := stillOpen(t); err != nil {
			return err
		}
		liveList, err := s.adhocRegistrations(txCtx, tx, tournamentID)
		if err != nil {
			return err
		}
		live := map[int64]*Registration{}
		for _, r := range liveList {
			live[r.ID] = r
		}
		entries := map[int64]*IndividualSignup{}
		erows, err := tx.QueryContext(txCtx, `SELECT id, tournament_id, user_id, game_account_id, role_tank, role_damage,
			role_support, registration_id, created_at, updated_at FROM individual_signups WHERE tournament_id = ?`, tournamentID)
		if err != nil {
			return err
		}
		for erows.Next() {
			sg, err := scanSignupRow(erows)
			if err != nil {
				erows.Close()
				return err
			}
			entries[sg.ID] = sg
		}
		erows.Close()

		var probs []string
		seen := map[int64]bool{}
		mentioned := map[int64]bool{}
		var plans []plan
		nick := func(userID int64) string {
			u, _ := getUser(txCtx, tx, userID)
			if u == nil {
				return fmt.Sprint(userID)
			}
			return u.Nickname
		}
		for _, lt := range layout {
			var reg *Registration
			if lt.RegistrationID != nil {
				reg = live[*lt.RegistrationID]
				if reg == nil {
					probs = append(probs, "有一支队伍已经不存在了，请刷新页面再试")
					continue
				}
				if lt.BaseVersion != 0 && lt.BaseVersion != reg.RosterVersion {
					return api.NewErr(409, "stale", "另一个人刚改过这支队伍，请刷新页面再试")
				}
				mentioned[reg.ID] = true
			}
			var ids []int64
			for _, sid := range lt.SignupIDs {
				e := entries[sid]
				if e == nil {
					probs = append(probs, "名单里有不属于这项赛事的人，请刷新页面再试")
					continue
				}
				if seen[sid] {
					probs = append(probs, nick(e.UserID)+" 被放进了两支队伍")
					continue
				}
				seen[sid] = true
				ids = append(ids, sid)
			}
			name := strings.TrimSpace(lt.Name)
			if len(ids) == 0 && reg == nil {
				continue // 空的新队什么都不是
			}
			if len(ids) > 0 {
				if len(ids) > t.RosterMax {
					n := name
					if n == "" {
						n = "新队伍"
					}
					probs = append(probs, fmt.Sprintf("「%s」有 %d 人，超过上限 %d", n, len(ids), t.RosterMax))
				}
				var excl int64
				if reg != nil {
					excl = reg.ID
				}
				np, err := nameProblems(txCtx, tx, tournamentID, name, excl)
				if err != nil {
					return err
				}
				probs = append(probs, np...)
			}
			plans = append(plans, plan{reg, name, ids})
		}
		for _, r := range liveList {
			if !mentioned[r.ID] {
				plans = append(plans, plan{r, r.TeamName, nil})
			}
		}
		names := map[string]bool{}
		for _, p := range plans {
			if len(p.ids) == 0 {
				continue
			}
			k := strings.ToLower(p.name)
			if names[k] {
				probs = append(probs, "两支队伍不能同名")
				break
			}
			names[k] = true
		}
		if len(probs) > 0 {
			return problems(probs)
		}

		// 阶段一：把要离开原队的人先移出
		desired := map[int64]map[int64]bool{}
		for _, p := range plans {
			if p.reg != nil {
				set := map[int64]bool{}
				for _, id := range p.ids {
					set[entries[id].UserID] = true
				}
				desired[p.reg.ID] = set
			}
		}
		before := map[int64]map[int64]bool{}
		type returnedTeam struct {
			name  string
			users []int64
		}
		var returned []returnedTeam
		for _, r := range liveList {
			cur := map[int64]bool{}
			rows, err := roster(txCtx, tx, r.ID)
			if err != nil {
				return err
			}
			for _, m := range rows {
				cur[m.UserID] = true
			}
			before[r.ID] = cur
			keep := desired[r.ID]
			var leaving []int64
			for uid := range cur {
				if !keep[uid] {
					leaving = append(leaving, uid)
				}
			}
			if len(leaving) > 0 {
				for _, uid := range leaving {
					if _, err := tx.ExecContext(txCtx, `DELETE FROM registration_members WHERE registration_id = ? AND user_id = ?`, r.ID, uid); err != nil {
						return err
					}
					if _, err := tx.ExecContext(txCtx, `UPDATE individual_signups SET registration_id = NULL WHERE registration_id = ? AND user_id = ?`, r.ID, uid); err != nil {
						return err
					}
				}
				returned = append(returned, returnedTeam{r.TeamName, leaving})
			}
		}

		// 阶段二：校验并写入每支队
		type formedTeam struct {
			reg   *Registration
			users []int64
		}
		var formed []formedTeam
		for _, p := range plans {
			if p.reg != nil && len(p.ids) == 0 {
				if err := s.dissolve(txCtx, tx, ctx, t, p.reg, v.ID, ActorAdmin, "管理员调整", now); err != nil {
					return err
				}
				res.Dissolved++
				continue
			}
			var issues []string
			for _, id := range p.ids {
				e := entries[id]
				ps, err := s.memberProblems(txCtx, tx, t, e.UserID, false)
				if err != nil {
					return err
				}
				issues = append(issues, ps...)
				var excl int64
				if p.reg != nil {
					excl = p.reg.ID
				}
				c, err := s.rosterConflict(txCtx, tx, tournamentID, e.UserID, excl)
				if err != nil {
					return err
				}
				if c != "" {
					issues = append(issues, c)
				}
			}
			if len(issues) > 0 {
				return problems(issues)
			}
			if p.reg == nil {
				r, err := s.createAdhoc(txCtx, tx, t, p.name, v.ID, now)
				if err != nil {
					return err
				}
				users, err := s.placeMembers(txCtx, tx, r, entries, p.ids)
				if err != nil {
					return err
				}
				rows, _ := roster(txCtx, tx, r.ID)
				if err := logRegistration(txCtx, tx, r.ID, ActFormTeam, "", r.Status, ActorAdmin, &v.ID, r.RosterVersion, snapshotJSON(rows), "", now); err != nil {
					return err
				}
				res.Created++
				formed = append(formed, formedTeam{r, users})
				continue
			}
			cur := before[p.reg.ID]
			want := desired[p.reg.ID]
			same := len(cur) == len(want)
			for uid := range want {
				if !cur[uid] {
					same = false
				}
			}
			// 阶段一已经把离开的人删了，所以 cur 里有、want 里没有的算变化
			unchanged := same && p.reg.TeamName == p.name
			if unchanged {
				continue
			}
			if _, err := tx.ExecContext(txCtx, `UPDATE registrations SET team_name = ?, roster_version = roster_version + 1, updated_at = ? WHERE id = ?`,
				p.name, db.FormatUTC(now), p.reg.ID); err != nil {
				return err
			}
			users, err := s.placeMembers(txCtx, tx, p.reg, entries, p.ids)
			if err != nil {
				return err
			}
			updated, err := GetRegistration(txCtx, tx, p.reg.ID)
			if err != nil {
				return err
			}
			rows, _ := roster(txCtx, tx, p.reg.ID)
			if err := logRegistration(txCtx, tx, p.reg.ID, ActSyncRoster, updated.Status, updated.Status, ActorAdmin, &v.ID, updated.RosterVersion, snapshotJSON(rows), "管理员调整", now); err != nil {
				return err
			}
			res.Updated++
			var added []int64
			for _, uid := range users {
				if !cur[uid] {
					added = append(added, uid)
				}
			}
			if len(added) > 0 {
				formed = append(formed, formedTeam{updated, added})
			}
		}

		// 通知
		for _, f := range formed {
			if err := s.notifyAdhocFormed(txCtx, tx, ctx, t, f.reg, f.users, now); err != nil {
				return err
			}
		}
		// 从一队移到另一队的人是「换队」，不是「回到散人池」：只通知真正回池的（现行站会两封都发）。
		placed := map[int64]bool{}
		for _, set := range desired {
			for uid := range set {
				placed[uid] = true
			}
		}
		for _, r := range returned {
			var back []int64
			for _, uid := range r.users {
				if !placed[uid] {
					back = append(back, uid)
				}
			}
			res.Returned += len(back)
			if len(back) == 0 {
				continue
			}
			if err := s.notifyAdhocReturned(txCtx, tx, ctx, t, r.name, back, false, now); err != nil {
				return err
			}
		}
		return nil
	})
	if isUnique(err) {
		return nil, problems([]string{"有人刚被别的队伍占用了，请刷新页面再试"})
	}
	if err != nil {
		return nil, err
	}
	return res, nil
}

func (s *Service) createAdhoc(ctx context.Context, tx *db.Tx, t *Tournament, name string, actor int64, now time.Time) (*Registration, error) {
	res, err := tx.ExecContext(ctx, `INSERT INTO registrations
		(tournament_id, team_id, status, team_name, roster_version, submitted_by, submitted_at, status_note, created_at, updated_at)
		VALUES (?, NULL, 'approved', ?, 1, ?, ?, '', ?, ?)`, t.ID, name, actor, db.FormatUTC(now), db.FormatUTC(now), db.FormatUTC(now))
	if err != nil {
		return nil, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return nil, err
	}
	return GetRegistration(ctx, tx, id)
}

// placeMembers 把个人报名快照成这支临时队的名单，并标上归属。
func (s *Service) placeMembers(ctx context.Context, tx *db.Tx, r *Registration, entries map[int64]*IndividualSignup, ids []int64) ([]int64, error) {
	if _, err := tx.ExecContext(ctx, `DELETE FROM registration_members WHERE registration_id = ?`, r.ID); err != nil {
		return nil, err
	}
	var users []int64
	for _, id := range ids {
		e := entries[id]
		u, err := getUser(ctx, tx, e.UserID)
		if err != nil {
			return nil, err
		}
		var acc *chosenAccount
		if e.GameAccountID != nil {
			acc, err = loadAccount(ctx, tx, `SELECT id, battletag, rank_tank, rank_damage, rank_support FROM game_accounts WHERE id = ?`, *e.GameAccountID)
			if err != nil {
				return nil, err
			}
		}
		var gaID any
		bt := ""
		var tank, damage, support any
		if acc != nil {
			gaID, bt = acc.ID, acc.Battletag
			tank, damage, support = intArg(acc.Tank), intArg(acc.Damage), intArg(acc.Support)
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO registration_members
			(registration_id, tournament_id, user_id, game_account_id, nickname, battletag, is_sjtu,
			 rank_tank, rank_damage, rank_support, is_captain, is_active)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)`,
			r.ID, r.TournamentID, e.UserID, gaID, u.Nickname, bt, b2i(u.IsSJTU), tank, damage, support, b2i(r.Active())); err != nil {
			return nil, err
		}
		if _, err := tx.ExecContext(ctx, `UPDATE individual_signups SET registration_id = ? WHERE id = ?`, r.ID, id); err != nil {
			return nil, err
		}
		users = append(users, e.UserID)
	}
	return users, nil
}

// dissolve 全员回散人池，报名置为已撤回（规则 135）；不发状态信，另有回池信。
func (s *Service) dissolve(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, r *Registration, actor int64, actorType, note string, now time.Time) error {
	if _, err := tx.ExecContext(ctx, `UPDATE individual_signups SET registration_id = NULL WHERE registration_id = ?`, r.ID); err != nil {
		return err
	}
	from := r.Status
	if _, err := tx.ExecContext(ctx, `UPDATE registrations SET status = 'withdrawn', status_note = ?, updated_at = ? WHERE id = ?`,
		note, db.FormatUTC(now), r.ID); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE registration_members SET is_active = 0 WHERE registration_id = ?`, r.ID); err != nil {
		return err
	}
	rows, err := roster(ctx, tx, r.ID)
	if err != nil {
		return err
	}
	var by *int64
	if actor > 0 {
		by = &actor
	}
	return logRegistration(ctx, tx, r.ID, ActDissolve, from, RegWithdrawn, actorType, by, r.RosterVersion, snapshotJSON(rows), note, now)
}

// DissolveTeam 管理员解散一支临时队伍：全员回散人池（规则 135）。
func (s *Service) DissolveTeam(ctx *app.Ctx, regID int64) error {
	v, err := requireManager(ctx)
	if err != nil {
		return err
	}
	now := ctx.Now().UTC()
	_, err = s.withRegistration(ctx, regID, func(txCtx context.Context, tx *db.Tx, t *Tournament, r *Registration, _ time.Time) error {
		if r.TeamID != nil {
			return refuse("只有临时队伍能解散，战队报名请驳回")
		}
		if !r.Active() {
			return refuse("这支队伍已经不在报名中")
		}
		if err := stillOpen(t); err != nil {
			return err
		}
		rows, err := roster(txCtx, tx, regID)
		if err != nil {
			return err
		}
		var users []int64
		for _, m := range rows {
			users = append(users, m.UserID)
		}
		if err := s.dissolve(txCtx, tx, ctx, t, r, v.ID, ActorAdmin, "", now); err != nil {
			return err
		}
		return s.notifyAdhocReturned(txCtx, tx, ctx, t, r.TeamName, users, true, now)
	})
	return err
}

const autoDissolveNote = "最后一名成员退出，队伍自动解散"

// LeaveAdhoc 队员在截止前自行退出临时队（规则 134）：成员行硬删除；最后一人退出时队伍自动解散
// 并通知赛事管理员。
func (s *Service) LeaveAdhoc(ctx *app.Ctx, regID int64) (bool, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return false, err
	}
	dissolved := false
	_, err = s.withRegistration(ctx, regID, func(txCtx context.Context, tx *db.Tx, t *Tournament, r *Registration, now time.Time) error {
		if r.TeamID != nil {
			return refuse("战队报名由队长撤回，不能单独退出")
		}
		if !r.Active() {
			return refuse("这支队伍已经不在报名中")
		}
		var n int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM registration_members WHERE registration_id = ? AND user_id = ?`, regID, v.ID).Scan(&n); err != nil {
			return err
		}
		if n == 0 {
			return refuse("你不在这支队伍的名单里")
		}
		if t.RegistrationClosesAt != nil && now.After(*t.RegistrationClosesAt) {
			return refuse("报名已截止，不能再退出")
		}
		// 成员行硬删除：状态改写会把所有行的 is_active 重算，打标记的会复活。
		if _, err := tx.ExecContext(txCtx, `DELETE FROM registration_members WHERE registration_id = ? AND user_id = ?`, regID, v.ID); err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE individual_signups SET registration_id = NULL WHERE registration_id = ? AND user_id = ?`, regID, v.ID); err != nil {
			return err
		}
		var left int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM registration_members WHERE registration_id = ?`, regID).Scan(&left); err != nil {
			return err
		}
		dissolved = left == 0
		if dissolved {
			if err := s.dissolve(txCtx, tx, ctx, t, r, v.ID, ActorSystem, autoDissolveNote, now); err != nil {
				return err
			}
		} else {
			if _, err := tx.ExecContext(txCtx, `UPDATE registrations SET roster_version = roster_version + 1, updated_at = ? WHERE id = ?`, db.FormatUTC(now), regID); err != nil {
				return err
			}
			rows, _ := roster(txCtx, tx, regID)
			if err := logRegistration(txCtx, tx, regID, ActMemberLeft, r.Status, r.Status, ActorMember, &v.ID, r.RosterVersion+1, snapshotJSON(rows), "", now); err != nil {
				return err
			}
		}
		return s.notifyAdhocLeft(txCtx, tx, ctx, t, r, v.ID, dissolved, now)
	})
	return dissolved, err
}

// 编队相关的信（设计 8.8.2）。

func (s *Service) peopleOf(ctx context.Context, q db.DBTX, ids []int64) ([]mail.Person, error) {
	var out []mail.Person
	for _, id := range ids {
		u, err := getUser(ctx, q, id)
		if err != nil {
			return nil, err
		}
		if u != nil && u.Email != "" {
			out = append(out, person(u))
		}
	}
	return out, nil
}

func (s *Service) notifyAdhocFormed(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, r *Registration, users []int64, now time.Time) error {
	to, err := s.peopleOf(ctx, tx, users)
	if err != nil || len(to) == 0 {
		return err
	}
	facts := [][2]string{{"赛事", t.Title}, {"队伍", r.TeamName}}
	if t.StartsAt != nil {
		facts = append(facts, [2]string{"比赛时间", moment(*t.StartsAt)})
	}
	facts = append(facts, contactFact(t)...)
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "已编入临时队伍：" + t.Title,
		Lead:       fmt.Sprintf("赛事管理员把你编入了「%s」的临时队伍「%s」，报名已通过。", t.Title, r.TeamName),
		Facts:      facts,
		Paragraphs: []string{"报名截止前，你可以在报名详情页退出队伍，回到散人池。"},
		Action:     []string{"查看报名详情", s.regURL(r.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你个人报名了「%s」。", t.Title),
	}, to, now)
}

func (s *Service) notifyAdhocReturned(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, teamName string, users []int64, dissolved bool, now time.Time) error {
	to, err := s.peopleOf(ctx, tx, users)
	if err != nil || len(to) == 0 {
		return err
	}
	lead := fmt.Sprintf("赛事管理员把你从临时队伍「%s」移回了散人池。", teamName)
	if dissolved {
		lead = fmt.Sprintf("临时队伍「%s」已由赛事管理员解散，你回到了散人池。", teamName)
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "临时队伍有变化：" + t.Title,
		Lead:       lead,
		Facts:      [][2]string{{"赛事", t.Title}, {"原来的队伍", teamName}},
		Paragraphs: []string{"你的个人报名还在，重新编队后会再通知你。"},
		Action:     []string{"查看赛事页面", s.tournamentURL(t.ID)},
		Reason:     fmt.Sprintf("你收到这封邮件，是因为你个人报名了「%s」。", t.Title),
	}, to, now)
}

func (s *Service) notifyAdhocLeft(ctx context.Context, tx *db.Tx, c *app.Ctx, t *Tournament, r *Registration, userID int64, dissolved bool, now time.Time) error {
	u, err := getUser(ctx, tx, userID)
	if err != nil || u == nil {
		return err
	}
	rows, err := tx.QueryContext(ctx, `SELECT u.nickname, u.email FROM user_roles ur JOIN users u ON u.id = ur.user_id
		WHERE ur.role = ? AND u.is_active = 1 AND u.email <> '' ORDER BY u.id`, accounts.RoleTournamentAdmin)
	if err != nil {
		return err
	}
	var admins []mail.Person
	for rows.Next() {
		var p mail.Person
		if err := rows.Scan(&p.Name, &p.Address); err != nil {
			rows.Close()
			return err
		}
		admins = append(admins, p)
	}
	rows.Close()
	if len(admins) == 0 {
		return nil
	}
	var paragraphs []string
	if dissolved {
		paragraphs = []string{"队伍里没有人了，已自动解散。"}
	}
	return s.send(ctx, tx, c, mail.Letter{
		Subject:    "临时队伍成员退出：" + t.Title,
		Lead:       fmt.Sprintf("%s 退出了「%s」的临时队伍「%s」，回到散人池。", u.Nickname, t.Title, r.TeamName),
		Facts:      [][2]string{{"赛事", t.Title}, {"队伍", r.TeamName}, {"退出的人", u.Nickname}},
		Paragraphs: paragraphs,
		Action:     []string{"打开队伍编排", s.url(fmt.Sprintf("/admin/tournaments/%d/teams/", t.ID))},
		Reason:     "你收到这封邮件，是因为你是赛事管理员。",
	}, admins, now)
}
