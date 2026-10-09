package teams

import (
	"context"
	"database/sql"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Person 是战队页上一个人公开的样子：昵称、位置、各位置最高段位（规则 21 的口径）。
type Person struct {
	UserID   int64                      `json:"user_id"`
	Nickname string                     `json:"nickname"`
	Active   bool                       `json:"is_active"`
	MainRole string                     `json:"main_role"`
	Roles    []string                   `json:"roles"`
	Ranks    accounts.PublicRanksResult `json:"ranks"`
}

// MemberRow 是现役成员一行。
type MemberRow struct {
	Person
	Role     string    `json:"role"`
	JoinedAt time.Time `json:"joined_at"`
}

// AlumnusRow 是退役成员一行。
type AlumnusRow struct {
	ID int64 `json:"id"`
	Person
	Role      string    `json:"role"`
	JoinedAt  time.Time `json:"joined_at"`
	LeftAt    time.Time `json:"left_at"`
	Reason    string    `json:"reason"`
	CanRemove bool      `json:"can_remove"`
}

// TeamCard 是战队列表里的一张卡。
type TeamCard struct {
	ID          int64    `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description"`
	LogoImageID *int64   `json:"logo_image_id"`
	Recruiting  bool     `json:"is_recruiting"`
	WantedRoles []string `json:"wanted_roles"`
	MemberCount int      `json:"member_count"`
	Full        bool     `json:"is_full"`
}

// ListInput 是战队列表的筛选：只看招募中，或只看缺某个位置的（设计 7.6）。
type ListInput struct {
	RecruitingOnly bool
	Role           string
}

// ListResult 是战队列表页要的全部。
type ListResult struct {
	Teams           []TeamCard     `json:"teams"`
	TeamTotal       int            `json:"team_total"`
	RecruitingTotal int            `json:"recruiting_total"`
	RoleCounts      map[string]int `json:"role_counts"`
	MaxMembers      int            `json:"max_members"`
	RecruitingOnly  bool           `json:"recruiting_only"`
	Role            string         `json:"role"`
}

func wants(rawRoles []string, role string) bool {
	if len(rawRoles) == 0 {
		return true
	}
	for _, r := range rawRoles {
		if r == role {
			return true
		}
	}
	return false
}

// List 战队列表（公开）：未解散的战队，新的在前，成员数一次查出（规则 86 的上限用于「满员」）。
func (s *Service) List(ctx context.Context, in ListInput) (*ListResult, error) {
	lim, err := s.store.GetLimits(ctx, s.d.ReadPool())
	if err != nil {
		return nil, err
	}
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT `+prefixCols("t", teamCols)+`,
		(SELECT COUNT(*) FROM team_memberships m WHERE m.team_id = t.id)
		FROM teams t WHERE t.disbanded_at IS NULL ORDER BY t.created_at DESC, t.id DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	role := in.Role
	if _, ok := accounts.RoleLabels[role]; !ok {
		role = ""
	}
	res := &ListResult{Teams: []TeamCard{}, RoleCounts: map[string]int{}, MaxMembers: lim.MaxMembers, Role: role}
	for _, r := range accounts.RoleOrder {
		res.RoleCounts[r] = 0
	}
	res.RecruitingOnly = in.RecruitingOnly && role == ""
	for rows.Next() {
		var count int
		t, err := scanTeamPlus(rows, &count)
		if err != nil {
			return nil, err
		}
		card := TeamCard{
			ID: t.ID, Name: t.Name, Description: t.Description, LogoImageID: t.LogoImageID,
			Recruiting: t.IsRecruiting, MemberCount: count, Full: count >= lim.MaxMembers,
			WantedRoles: []string{},
		}
		if t.IsRecruiting {
			card.WantedRoles = t.RecruitingRoles
		}
		res.TeamTotal++
		if t.IsRecruiting {
			res.RecruitingTotal++
			if !card.Full {
				for _, r := range accounts.RoleOrder {
					if wants(t.RecruitingRoles, r) {
						res.RoleCounts[r]++
					}
				}
			}
		}
		if (in.RecruitingOnly || role != "") && !t.IsRecruiting {
			continue
		}
		if role != "" && !(wants(t.RecruitingRoles, role) && !card.Full) {
			continue
		}
		res.Teams = append(res.Teams, card)
	}
	return res, rows.Err()
}

func prefixCols(alias, cols string) string {
	parts := strings.Split(cols, ",")
	for i, p := range parts {
		parts[i] = alias + "." + strings.TrimSpace(p)
	}
	return strings.Join(parts, ", ")
}

// scanTeamPlus 读 teamCols 加一个整数列。
func scanTeamPlus(row interface{ Scan(...any) error }, extra *int) (*Team, error) {
	var t Team
	var logo sql.NullInt64
	var recruiting int
	var roles string
	var disbanded sql.NullString
	var created, updated string
	if err := row.Scan(&t.ID, &t.Name, &t.Description, &logo, &recruiting, &roles,
		&t.MemberContact, &disbanded, &t.Version, &created, &updated, extra); err != nil {
		return nil, err
	}
	if logo.Valid {
		v := logo.Int64
		t.LogoImageID = &v
	}
	t.IsRecruiting = recruiting == 1
	t.RecruitingRoles = accounts.ParseRoles(roles)
	t.DisbandedAt = nullTime(disbanded)
	t.CreatedAt = parseTime(created)
	t.UpdatedAt = parseTime(updated)
	return &t, nil
}

// people 一次取一批人，拼成公开的样子（不做 N+1）。
func (s *Service) people(ctx context.Context, q db.DBTX, ids []int64, now time.Time) (map[int64]Person, error) {
	out := map[int64]Person{}
	if len(ids) == 0 {
		return out, nil
	}
	gas, err := s.store.GameAccountsFor(ctx, q, ids)
	if err != nil {
		return nil, err
	}
	ph := strings.TrimSuffix(strings.Repeat("?,", len(ids)), ",")
	args := make([]any, len(ids))
	for i, id := range ids {
		args[i] = id
	}
	rows, err := q.QueryContext(ctx, `SELECT id, nickname, is_active, main_role, flex_roles, show_rank
		FROM users WHERE id IN (`+ph+`)`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var p Person
		var active, show int
		var flex string
		if err := rows.Scan(&p.UserID, &p.Nickname, &active, &p.MainRole, &flex, &show); err != nil {
			return nil, err
		}
		p.Active = active == 1
		if _, ok := accounts.RoleLabels[p.MainRole]; !ok {
			p.MainRole = ""
		}
		p.Roles = accounts.PublicPositions(p.MainRole, flex)
		p.Ranks = accounts.CalculatePublicRanks(gas[p.UserID], show == 1, now)
		out[p.UserID] = p
	}
	return out, rows.Err()
}

// ViewerState 是打开战队页的这个人和这支队的关系（访客全是 false）。
type ViewerState struct {
	IsMember         bool   `json:"is_member"`
	IsCaptain        bool   `json:"is_captain"`
	IsSuperuser      bool   `json:"is_superuser"`
	CanApply         bool   `json:"can_apply"`
	ApplyReason      string `json:"apply_reason,omitempty"`
	NeedsGameAccount bool   `json:"needs_game_account"`
}

// TeamPage 是战队详情页要的全部（公开；解散的队也看得到，只是没有退役名单）。
type TeamPage struct {
	Team       *Team        `json:"team"`
	Members    []MemberRow  `json:"members"`
	Alumni     []AlumnusRow `json:"alumni"`
	MaxMembers int          `json:"max_members"`
	Viewer     ViewerState  `json:"viewer"`
}

func (s *Service) members(ctx context.Context, q db.DBTX, teamID int64, now time.Time) ([]MemberRow, error) {
	rows, err := q.QueryContext(ctx, `SELECT user_id, role, joined_at FROM team_memberships
		WHERE team_id = ? ORDER BY role, joined_at, id`, teamID)
	if err != nil {
		return nil, err
	}
	type raw struct {
		uid  int64
		role string
		at   time.Time
	}
	var list []raw
	var ids []int64
	for rows.Next() {
		var r raw
		var at string
		if err := rows.Scan(&r.uid, &r.role, &at); err != nil {
			rows.Close()
			return nil, err
		}
		r.at = parseTime(at)
		list = append(list, r)
		ids = append(ids, r.uid)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	ppl, err := s.people(ctx, q, ids, now)
	if err != nil {
		return nil, err
	}
	out := make([]MemberRow, 0, len(list))
	for _, r := range list {
		out = append(out, MemberRow{Person: ppl[r.uid], Role: r.role, JoinedAt: r.at})
	}
	return out, nil
}

func (s *Service) alumni(ctx context.Context, q db.DBTX, v *app.Viewer, teamID int64, isManager bool, now time.Time) ([]AlumnusRow, error) {
	rows, err := q.QueryContext(ctx, `SELECT id, user_id, role, joined_at, left_at, reason
		FROM team_alumni WHERE team_id = ? ORDER BY left_at DESC, id DESC`, teamID)
	if err != nil {
		return nil, err
	}
	var out []AlumnusRow
	var ids []int64
	for rows.Next() {
		var a AlumnusRow
		var joined, left string
		if err := rows.Scan(&a.ID, &a.UserID, &a.Role, &joined, &left, &a.Reason); err != nil {
			rows.Close()
			return nil, err
		}
		a.JoinedAt, a.LeftAt = parseTime(joined), parseTime(left)
		out = append(out, a)
		ids = append(ids, a.UserID)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	ppl, err := s.people(ctx, q, ids, now)
	if err != nil {
		return nil, err
	}
	for i := range out {
		out[i].Person = ppl[out[i].UserID]
		out[i].CanRemove = isManager || (v != nil && v.ID == out[i].UserID)
	}
	if out == nil {
		out = []AlumnusRow{}
	}
	return out, nil
}

// Detail 战队详情（公开）。队内联系方式只给本队成员和超管看（设计 7.1）。
func (s *Service) Detail(ctx *app.Ctx, teamID int64) (*TeamPage, error) {
	rd := s.d.ReadPool()
	t, err := s.store.GetTeam(ctx.Context, rd, teamID)
	if err != nil {
		return nil, err
	}
	if t == nil {
		return nil, api.NotFound("战队不存在")
	}
	v := ctx.Viewer
	loggedIn := v != nil && !v.Disabled && v.ID > 0
	now := ctx.Now().UTC()
	page := &TeamPage{Team: t}
	lim, err := s.store.GetLimits(ctx.Context, rd)
	if err != nil {
		return nil, err
	}
	page.MaxMembers = lim.MaxMembers
	if page.Members, err = s.members(ctx.Context, rd, teamID, now); err != nil {
		return nil, err
	}
	var isManager bool
	if loggedIn {
		m, err := s.store.GetMembership(ctx.Context, rd, teamID, v.ID)
		if err != nil {
			return nil, err
		}
		page.Viewer.IsMember = m != nil
		page.Viewer.IsCaptain = m != nil && m.Role == RoleCaptain
		page.Viewer.IsSuperuser = v.Superuser
		isManager = page.Viewer.IsCaptain || v.Superuser
		ok, reason, err := s.canApply(ctx.Context, rd, v, t)
		if err != nil {
			return nil, err
		}
		page.Viewer.CanApply, page.Viewer.ApplyReason = ok, reason
		if !ok && reason == "请先在个人中心添加至少一个游戏 ID。" {
			page.Viewer.NeedsGameAccount = true
		}
	} else {
		page.Viewer.ApplyReason = "请先登录。"
	}
	if !t.Disbanded() {
		if page.Alumni, err = s.alumni(ctx.Context, rd, v, teamID, isManager, now); err != nil {
			return nil, err
		}
	} else {
		page.Alumni = []AlumnusRow{}
	}
	if !page.Viewer.IsMember && !(loggedIn && v.Superuser) {
		t.MemberContact = ""
	}
	return page, nil
}

// PendingRow 是队长管理页上一条待审申请（规则 96：停用账号的申请不显示）。
type PendingRow struct {
	ID        int64     `json:"id"`
	Applicant Person    `json:"applicant"`
	Roles     []string  `json:"roles"`
	Message   string    `json:"message"`
	CreatedAt time.Time `json:"created_at"`
	GameIDs   []string  `json:"game_ids"`
	Reminded  bool      `json:"reminded"`
}

// ManagePage 是队长管理页（队长或超管；别人看到的是 404）。
type ManagePage struct {
	Team            *Team        `json:"team"`
	Members         []MemberRow  `json:"members"`
	Alumni          []AlumnusRow `json:"alumni"`
	Pending         []PendingRow `json:"pending"`
	DisbandBlockers []string     `json:"disband_blockers"`
	MaxMembers      int          `json:"max_members"`
}

// Manage 队长管理页：资料、待审申请、成员、退役名单。
func (s *Service) Manage(ctx *app.Ctx, teamID int64) (*ManagePage, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	t, err := s.store.GetTeam(ctx.Context, rd, teamID)
	if err != nil {
		return nil, err
	}
	ok := false
	if t != nil {
		if ok, err = s.isManager(ctx.Context, rd, v, teamID); err != nil {
			return nil, err
		}
	}
	if !ok {
		return nil, api.NotFound("没有这个页面")
	}
	now := ctx.Now().UTC()
	lim, err := s.store.GetLimits(ctx.Context, rd)
	if err != nil {
		return nil, err
	}
	page := &ManagePage{Team: t, MaxMembers: lim.MaxMembers}
	if page.Members, err = s.members(ctx.Context, rd, teamID, now); err != nil {
		return nil, err
	}
	if page.Alumni, err = s.alumni(ctx.Context, rd, v, teamID, true, now); err != nil {
		return nil, err
	}
	if page.DisbandBlockers, err = s.disbandBlockers(ctx.Context, rd, teamID); err != nil {
		return nil, err
	}
	if page.DisbandBlockers == nil {
		page.DisbandBlockers = []string{}
	}
	if page.Pending, err = s.pending(ctx.Context, rd, teamID, now); err != nil {
		return nil, err
	}
	return page, nil
}

func (s *Service) pending(ctx context.Context, q db.DBTX, teamID int64, now time.Time) ([]PendingRow, error) {
	rows, err := q.QueryContext(ctx, `SELECT `+prefixCols("a", appCols)+` FROM team_applications a
		JOIN users u ON u.id = a.applicant_id
		WHERE a.team_id = ? AND a.status = 'pending' AND u.is_active = 1
		ORDER BY a.created_at, a.id`, teamID)
	if err != nil {
		return nil, err
	}
	var apps []*Application
	var ids []int64
	for rows.Next() {
		a, err := scanApplication(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		apps = append(apps, a)
		ids = append(ids, a.ApplicantID)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	ppl, err := s.people(ctx, q, ids, now)
	if err != nil {
		return nil, err
	}
	gas, err := s.store.GameAccountsFor(ctx, q, ids)
	if err != nil {
		return nil, err
	}
	out := make([]PendingRow, 0, len(apps))
	for _, a := range apps {
		row := PendingRow{
			ID: a.ID, Applicant: ppl[a.ApplicantID], Roles: a.Positions(), Message: a.Message,
			CreatedAt: a.CreatedAt, GameIDs: []string{}, Reminded: a.CaptainRemindedAt != nil,
		}
		for _, ga := range gas[a.ApplicantID] {
			row.GameIDs = append(row.GameIDs, ga.Battletag)
		}
		out = append(out, row)
	}
	return out, nil
}

// MyEntry / MyApplication 是个人中心「我的战队」。
type MyEntry struct {
	TeamID      int64     `json:"team_id"`
	Name        string    `json:"name"`
	LogoImageID *int64    `json:"logo_image_id"`
	Role        string    `json:"role"`
	MemberCount int       `json:"member_count"`
	JoinedAt    time.Time `json:"joined_at"`
}

// MyApplication 是我提交过的一条申请。
type MyApplication struct {
	ID           int64      `json:"id"`
	TeamID       int64      `json:"team_id"`
	TeamName     string     `json:"team_name"`
	Roles        []string   `json:"roles"`
	Status       string     `json:"status"`
	DecisionNote string     `json:"decision_note"`
	CreatedAt    time.Time  `json:"created_at"`
	DecidedAt    *time.Time `json:"decided_at,omitempty"`
}

// MyTeamsResult 是 GET /api/me/teams 的内容。
type MyTeamsResult struct {
	Teams        []MyEntry       `json:"teams"`
	Applications []MyApplication `json:"applications"`
}

// MyTeams 我所在的战队和我的申请（登录）。
func (s *Service) MyTeams(ctx *app.Ctx) (*MyTeamsResult, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	res := &MyTeamsResult{Teams: []MyEntry{}, Applications: []MyApplication{}}
	rows, err := rd.QueryContext(ctx.Context, `SELECT t.id, t.name, t.logo_image_id, m.role, m.joined_at,
		(SELECT COUNT(*) FROM team_memberships x WHERE x.team_id = t.id)
		FROM team_memberships m JOIN teams t ON t.id = m.team_id
		WHERE m.user_id = ? AND t.disbanded_at IS NULL ORDER BY m.joined_at DESC, m.id DESC`, v.ID)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var e MyEntry
		var logo sql.NullInt64
		var joined string
		if err := rows.Scan(&e.TeamID, &e.Name, &logo, &e.Role, &joined, &e.MemberCount); err != nil {
			rows.Close()
			return nil, err
		}
		if logo.Valid {
			x := logo.Int64
			e.LogoImageID = &x
		}
		e.JoinedAt = parseTime(joined)
		res.Teams = append(res.Teams, e)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	arows, err := rd.QueryContext(ctx.Context, `SELECT `+prefixCols("a", appCols)+`, t.name
		FROM team_applications a JOIN teams t ON t.id = a.team_id
		WHERE a.applicant_id = ? ORDER BY a.created_at DESC, a.id DESC`, v.ID)
	if err != nil {
		return nil, err
	}
	defer arows.Close()
	for arows.Next() {
		var a Application
		var tank, damage, support int
		var by sql.NullInt64
		var decided, reminded sql.NullString
		var created, name string
		if err := arows.Scan(&a.ID, &a.TeamID, &a.ApplicantID, &tank, &damage, &support, &a.Message, &a.Status,
			&by, &decided, &a.DecisionNote, &reminded, &created, &name); err != nil {
			return nil, err
		}
		a.RoleTank, a.RoleDamage, a.RoleSupport = tank == 1, damage == 1, support == 1
		res.Applications = append(res.Applications, MyApplication{
			ID: a.ID, TeamID: a.TeamID, TeamName: name, Roles: a.Positions(), Status: a.Status,
			DecisionNote: a.DecisionNote, CreatedAt: parseTime(created), DecidedAt: nullTime(decided),
		})
	}
	return res, arows.Err()
}

// AdminRow 是超管的战队列表一行（含卡壳状态：没有队长或队长账号停用，规则 108）。
type AdminRow struct {
	ID            int64      `json:"id"`
	Name          string     `json:"name"`
	MemberCount   int        `json:"member_count"`
	CaptainID     *int64     `json:"captain_id"`
	CaptainName   string     `json:"captain_name"`
	CaptainActive bool       `json:"captain_active"`
	NoCaptain     bool       `json:"no_captain"`
	DisbandedAt   *time.Time `json:"disbanded_at,omitempty"`
	CreatedAt     time.Time  `json:"created_at"`
}

// AdminList 后台战队列表（超管）。「无队长战队」排在待办里：未解散、没有队长或队长已停用。
func (s *Service) AdminList(ctx *app.Ctx) ([]AdminRow, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT t.id, t.name, t.disbanded_at, t.created_at,
		(SELECT COUNT(*) FROM team_memberships x WHERE x.team_id = t.id),
		c.user_id, IFNULL(u.nickname, ''), IFNULL(u.is_active, 0)
		FROM teams t
		LEFT JOIN team_memberships c ON c.team_id = t.id AND c.role = 'captain'
		LEFT JOIN users u ON u.id = c.user_id
		ORDER BY t.created_at DESC, t.id DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []AdminRow{}
	for rows.Next() {
		var r AdminRow
		var disbanded sql.NullString
		var created string
		var cid sql.NullInt64
		var active int
		if err := rows.Scan(&r.ID, &r.Name, &disbanded, &created, &r.MemberCount, &cid, &r.CaptainName, &active); err != nil {
			return nil, err
		}
		if cid.Valid {
			x := cid.Int64
			r.CaptainID = &x
		}
		r.CaptainActive = active == 1
		r.DisbandedAt = nullTime(disbanded)
		r.CreatedAt = parseTime(created)
		r.NoCaptain = r.DisbandedAt == nil && (r.CaptainID == nil || !r.CaptainActive)
		out = append(out, r)
	}
	return out, rows.Err()
}
