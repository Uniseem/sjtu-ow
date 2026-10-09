package tournaments

import (
	"context"
	"database/sql"
	"sort"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

var phaseLabels = map[string]string{
	"open": "报名中", "upcoming": "即将开始报名", "closed": "已截止", "finished": "已结束", "cancelled": "已取消",
}

// Card 是赛事列表里的一张卡。
type Card struct {
	ID                   int64      `json:"id"`
	Title                string     `json:"title"`
	Summary              string     `json:"summary"`
	CoverImageID         *int64     `json:"cover_image_id"`
	StartsAt             *time.Time `json:"starts_at"`
	RegistrationOpensAt  *time.Time `json:"registration_opens_at"`
	RegistrationClosesAt *time.Time `json:"registration_closes_at"`
	RegistrationMode     string     `json:"registration_mode"`
	SjtuOnly             bool       `json:"sjtu_only"`
	Status               string     `json:"status"`
	Phase                string     `json:"phase"`
	ApprovedCount        int        `json:"approved_count"`
}

// Group 是列表页的一组。
type Group struct {
	Phase       string `json:"phase"`
	Label       string `json:"label"`
	Tournaments []Card `json:"tournaments"`
}

func cardOf(t *Tournament, now time.Time, approved int) Card {
	return Card{ID: t.ID, Title: t.Title, Summary: t.Summary, CoverImageID: t.CoverImageID, StartsAt: t.StartsAt,
		RegistrationOpensAt: t.RegistrationOpensAt, RegistrationClosesAt: t.RegistrationClosesAt,
		RegistrationMode: t.RegistrationMode, SjtuOnly: t.SjtuOnly, Status: t.Status, Phase: t.Phase(now), ApprovedCount: approved}
}

func (s *Service) loadTournaments(ctx context.Context, q db.DBTX, where string, args ...any) ([]*Tournament, error) {
	rows, err := q.QueryContext(ctx, `SELECT `+tournamentCols+` FROM tournaments `+where, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Tournament
	for rows.Next() {
		t, err := scanTournament(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func approvedCounts(ctx context.Context, q db.DBTX) (map[int64]int, error) {
	rows, err := q.QueryContext(ctx, `SELECT tournament_id, COUNT(*) FROM registrations WHERE status = 'approved' GROUP BY tournament_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64]int{}
	for rows.Next() {
		var id int64
		var n int
		if err := rows.Scan(&id, &n); err != nil {
			return nil, err
		}
		out[id] = n
	}
	return out, rows.Err()
}

// List 赛事列表（公开）：已发布和已结束的，分成四组（设计 8.2）。
func (s *Service) List(ctx context.Context, now time.Time) ([]Group, error) {
	rd := s.d.ReadPool()
	ts, err := s.loadTournaments(ctx, rd, `WHERE status IN ('published', 'finished')`)
	if err != nil {
		return nil, err
	}
	counts, err := approvedCounts(ctx, rd)
	if err != nil {
		return nil, err
	}
	order := []string{"open", "upcoming", "closed", "finished"}
	groups := map[string][]*Tournament{}
	for _, t := range ts {
		p := t.Phase(now)
		groups[p] = append(groups[p], t)
	}
	less := map[string]func(a, b *Tournament) bool{
		"open":     func(a, b *Tournament) bool { return a.RegistrationClosesAt.Before(*b.RegistrationClosesAt) },
		"upcoming": func(a, b *Tournament) bool { return a.RegistrationOpensAt.Before(*b.RegistrationOpensAt) },
		"closed":   func(a, b *Tournament) bool { return a.RegistrationClosesAt.After(*b.RegistrationClosesAt) },
		"finished": func(a, b *Tournament) bool { return sortKey(a).After(sortKey(b)) },
	}
	out := make([]Group, 0, len(order))
	for _, p := range order {
		list := groups[p]
		sort.SliceStable(list, func(i, j int) bool { return less[p](list[i], list[j]) })
		g := Group{Phase: p, Label: phaseLabels[p], Tournaments: []Card{}}
		for _, t := range list {
			g.Tournaments = append(g.Tournaments, cardOf(t, now, counts[t.ID]))
		}
		out = append(out, g)
	}
	return out, nil
}

func sortKey(t *Tournament) time.Time {
	if t.StartsAt != nil {
		return *t.StartsAt
	}
	return t.CreatedAt
}

// ApprovedTeam 是公开页上已通过的队伍和人数。
type ApprovedTeam struct {
	RegistrationID int64  `json:"registration_id"`
	TeamID         *int64 `json:"team_id"`
	TeamName       string `json:"team_name"`
	MemberCount    int    `json:"member_count"`
	Adhoc          bool   `json:"is_adhoc"`
}

// CaptainTeam 是登录的队长能用来报名的战队，附带预检的结果（整队报名）。
type CaptainTeam struct {
	TeamID       int64    `json:"team_id"`
	Name         string   `json:"name"`
	Registration *RegRef  `json:"registration"`
	Problems     []string `json:"problems"`
}

// RegRef 是一条报名的简要。
type RegRef struct {
	ID     int64  `json:"id"`
	Status string `json:"status"`
}

// ViewerState 是打开赛事页的这个人和这项赛事的关系。
type ViewerState struct {
	RegistrationOpen   bool          `json:"registration_open"`
	CaptainTeams       []CaptainTeam `json:"captain_teams"`
	OnRoster           *RegRef       `json:"on_roster"`
	MySignup           *SignupView   `json:"my_signup"`
	IndividualProblems []string      `json:"individual_problems"`
	IsManager          bool          `json:"is_manager"`
}

// Page 是赛事详情页要的全部。
type Page struct {
	Tournament    *Tournament    `json:"tournament"`
	Phase         string         `json:"phase"`
	PhaseLabel    string         `json:"phase_label"`
	ApprovedTeams []ApprovedTeam `json:"approved_teams"`
	Pool          *PoolView      `json:"pool,omitempty"`
	Viewer        ViewerState    `json:"viewer"`
}

func (s *Service) takesPart(ctx context.Context, q db.DBTX, tournamentID, userID int64) (bool, error) {
	var n int
	err := q.QueryRowContext(ctx, `SELECT (SELECT COUNT(*) FROM registration_members WHERE tournament_id = ? AND user_id = ? AND is_active = 1)
		+ (SELECT COUNT(*) FROM individual_signups WHERE tournament_id = ? AND user_id = ?)`,
		tournamentID, userID, tournamentID, userID).Scan(&n)
	return n > 0, err
}

// Detail 赛事详情（公开；草稿只有赛事管理员看得到，对别人是 404）。选手联系方式只给参赛的人
// 和管理员（设计 8.1）。
func (s *Service) Detail(ctx *app.Ctx, id int64) (*Page, error) {
	rd := s.d.ReadPool()
	t, err := GetTournament(ctx.Context, rd, id)
	if err != nil {
		return nil, err
	}
	v := ctx.Viewer
	loggedIn := v != nil && !v.Disabled && v.ID > 0
	manager := loggedIn && v.HasCap("tournaments.manage")
	if t == nil || (!t.IsPublic() && !manager) {
		return nil, api.NotFound("赛事不存在")
	}
	now := ctx.Now().UTC()
	page := &Page{Tournament: t, Phase: t.Phase(now), PhaseLabel: phaseLabels[t.Phase(now)], ApprovedTeams: []ApprovedTeam{}}
	page.Viewer.RegistrationOpen = t.RegistrationOpen(now)
	page.Viewer.IsManager = manager
	page.Viewer.CaptainTeams = []CaptainTeam{}
	page.Viewer.IndividualProblems = []string{}

	rows, err := rd.QueryContext(ctx.Context, `SELECT r.id, r.team_id, r.team_name,
		(SELECT COUNT(*) FROM registration_members m WHERE m.registration_id = r.id)
		FROM registrations r WHERE r.tournament_id = ? AND r.status = 'approved' ORDER BY r.submitted_at, r.id`, id)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var a ApprovedTeam
		var team sql.NullInt64
		if err := rows.Scan(&a.RegistrationID, &team, &a.TeamName, &a.MemberCount); err != nil {
			rows.Close()
			return nil, err
		}
		if team.Valid {
			x := team.Int64
			a.TeamID = &x
		}
		a.Adhoc = !team.Valid
		page.ApprovedTeams = append(page.ApprovedTeams, a)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	showContact := false
	if loggedIn {
		showContact = manager
		if !showContact {
			if showContact, err = s.takesPart(ctx.Context, rd, id, v.ID); err != nil {
				return nil, err
			}
		}
		if t.TakesTeams() {
			if err := s.fillCaptainState(ctx, rd, t, v, now, &page.Viewer); err != nil {
				return nil, err
			}
		}
		if t.TakesIndividuals() {
			if err := s.fillIndividualState(ctx, rd, t, v, now, &page.Viewer); err != nil {
				return nil, err
			}
		}
	}
	if t.TakesIndividuals() {
		if page.Pool, err = s.pool(ctx.Context, rd, id); err != nil {
			return nil, err
		}
	}
	if !showContact {
		t.ParticipantContact = ""
	}
	return page, nil
}

func (s *Service) fillCaptainState(ctx *app.Ctx, rd db.DBTX, t *Tournament, v *app.Viewer, now time.Time, vs *ViewerState) error {
	rows, err := rd.QueryContext(ctx.Context, `SELECT tm.id, tm.name FROM team_memberships m JOIN teams tm ON tm.id = m.team_id
		WHERE m.user_id = ? AND m.role = 'captain' AND tm.disbanded_at IS NULL ORDER BY tm.name`, v.ID)
	if err != nil {
		return err
	}
	var teams []CaptainTeam
	for rows.Next() {
		var ct CaptainTeam
		if err := rows.Scan(&ct.TeamID, &ct.Name); err != nil {
			rows.Close()
			return err
		}
		teams = append(teams, ct)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for i := range teams {
		var ref RegRef
		err := rd.QueryRowContext(ctx.Context, `SELECT id, status FROM registrations WHERE tournament_id = ? AND team_id = ?`,
			t.ID, teams[i].TeamID).Scan(&ref.ID, &ref.Status)
		var excl int64
		if err == nil {
			teams[i].Registration = &ref
			excl = ref.ID
		} else if err != sql.ErrNoRows {
			return err
		}
		if t.RegistrationOpen(now) {
			p, err := s.precheck(ctx.Context, rd, t, teams[i].TeamID, v.ID, excl, now)
			if err != nil {
				return err
			}
			teams[i].Problems = p
		}
		if teams[i].Problems == nil {
			teams[i].Problems = []string{}
		}
	}
	if teams != nil {
		vs.CaptainTeams = teams
	}
	if len(teams) == 0 {
		var ref RegRef
		err := rd.QueryRowContext(ctx.Context, `SELECT r.id, r.status FROM registrations r JOIN registration_members m ON m.registration_id = r.id
			WHERE r.tournament_id = ? AND m.user_id = ? AND m.is_active = 1 ORDER BY r.submitted_at DESC LIMIT 1`, t.ID, v.ID).Scan(&ref.ID, &ref.Status)
		if err == nil {
			vs.OnRoster = &ref
		} else if err != sql.ErrNoRows {
			return err
		}
	}
	return nil
}

// RegistrationPage 是报名详情页：只有队长和名单上的人看得到（规则 127）。
type RegistrationPage struct {
	Registration       *Registration  `json:"registration"`
	Tournament         *Card          `json:"tournament"`
	Roster             []RosterMember `json:"roster"`
	Logs               []StatusLog    `json:"logs"`
	IsCaptain          bool           `json:"is_captain"`
	CanWithdraw        bool           `json:"can_withdraw"`
	CanResubmit        bool           `json:"can_resubmit"`
	RosterDiffers      bool           `json:"roster_differs"`
	CanLeave           bool           `json:"can_leave"`
	ParticipantContact string         `json:"participant_contact,omitempty"`
}

func logsOf(ctx context.Context, q db.DBTX, regID int64) ([]StatusLog, error) {
	rows, err := q.QueryContext(ctx, `SELECT id, action, from_status, to_status, actor_type, actor_user_id, roster_version, note, created_at
		FROM registration_status_logs WHERE registration_id = ? ORDER BY created_at, id`, regID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []StatusLog{}
	for rows.Next() {
		var l StatusLog
		var actor sql.NullInt64
		var at string
		if err := rows.Scan(&l.ID, &l.Action, &l.FromStatus, &l.ToStatus, &l.ActorType, &actor, &l.RosterVersion, &l.Note, &at); err != nil {
			return nil, err
		}
		if actor.Valid {
			x := actor.Int64
			l.ActorUserID = &x
		}
		l.CreatedAt = parseTime(at)
		out = append(out, l)
	}
	return out, rows.Err()
}

// RegistrationDetail 报名详情（规则 127）。
func (s *Service) RegistrationDetail(ctx *app.Ctx, id int64) (*RegistrationPage, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	r, err := GetRegistration(ctx.Context, rd, id)
	if err != nil {
		return nil, err
	}
	if r == nil {
		return nil, api.NotFound("报名不存在")
	}
	captain := false
	if r.TeamID != nil {
		if captain, err = isTeamCaptain(ctx.Context, rd, *r.TeamID, v.ID); err != nil {
			return nil, err
		}
	}
	var onRoster, active int
	if err := rd.QueryRowContext(ctx.Context, `SELECT COUNT(*), COALESCE(SUM(is_active), 0) FROM registration_members WHERE registration_id = ? AND user_id = ?`,
		id, v.ID).Scan(&onRoster, &active); err != nil {
		return nil, err
	}
	if !captain && onRoster == 0 {
		return nil, api.NotFound("报名不存在")
	}
	t, err := GetTournament(ctx.Context, rd, r.TournamentID)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	page := &RegistrationPage{Registration: r, IsCaptain: captain}
	c := cardOf(t, now, 0)
	page.Tournament = &c
	if page.Roster, err = roster(ctx.Context, rd, id); err != nil {
		return nil, err
	}
	if page.Logs, err = logsOf(ctx.Context, rd, id); err != nil {
		return nil, err
	}
	beforeClose := t.RegistrationClosesAt != nil && !now.After(*t.RegistrationClosesAt)
	page.CanWithdraw = captain && r.Active() && beforeClose
	page.CanResubmit = captain && t.RegistrationOpen(now)
	page.CanLeave = r.Adhoc() && active > 0 && r.Active() && beforeClose
	if r.TeamID != nil {
		if page.RosterDiffers, err = rosterDiffers(ctx.Context, rd, r); err != nil {
			return nil, err
		}
	}
	if active > 0 {
		page.ParticipantContact = t.ParticipantContact
	}
	return page, nil
}

// rosterDiffers 队伍在锁定名单之后变过（设计 8.4）：提示队长同步。
func rosterDiffers(ctx context.Context, q db.DBTX, r *Registration) (bool, error) {
	var diff int
	err := q.QueryRowContext(ctx, `SELECT
		(SELECT COUNT(*) FROM registration_members WHERE registration_id = ? AND user_id NOT IN (SELECT user_id FROM team_memberships WHERE team_id = ?))
		+ (SELECT COUNT(*) FROM team_memberships WHERE team_id = ? AND user_id NOT IN (SELECT user_id FROM registration_members WHERE registration_id = ?))`,
		r.ID, *r.TeamID, *r.TeamID, r.ID).Scan(&diff)
	return diff > 0, err
}

// MyRegistration 是个人中心里「我所在的有效报名」一行。
type MyRegistration struct {
	RegistrationID int64     `json:"registration_id"`
	TournamentID   int64     `json:"tournament_id"`
	Title          string    `json:"title"`
	TeamName       string    `json:"team_name"`
	Status         string    `json:"status"`
	SubmittedAt    time.Time `json:"submitted_at"`
}

// MyRegistrations 我现在名单上的有效报名（设计 13.5）。
func (s *Service) MyRegistrations(ctx *app.Ctx) ([]MyRegistration, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT DISTINCT r.id, r.tournament_id, t.title, r.team_name, r.status, r.submitted_at
		FROM registrations r JOIN registration_members m ON m.registration_id = r.id JOIN tournaments t ON t.id = r.tournament_id
		WHERE m.user_id = ? AND m.is_active = 1 ORDER BY r.submitted_at DESC`, v.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []MyRegistration{}
	for rows.Next() {
		var m MyRegistration
		var at string
		if err := rows.Scan(&m.RegistrationID, &m.TournamentID, &m.Title, &m.TeamName, &m.Status, &at); err != nil {
			return nil, err
		}
		m.SubmittedAt = parseTime(at)
		out = append(out, m)
	}
	return out, rows.Err()
}

// AdminRow 是后台赛事列表的一行。
type AdminRow struct {
	Card
	PendingCount int      `json:"pending_count"`
	WaitingTeam  int      `json:"waiting_for_team"`
	Missing      []string `json:"missing"`
}

// AdminList 后台赛事列表（含草稿）。
func (s *Service) AdminList(ctx *app.Ctx) ([]AdminRow, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	ts, err := s.loadTournaments(ctx.Context, rd, `ORDER BY COALESCE(registration_opens_at, created_at) DESC, id DESC`)
	if err != nil {
		return nil, err
	}
	counts, err := approvedCounts(ctx.Context, rd)
	if err != nil {
		return nil, err
	}
	pending := map[int64]int{}
	rows, err := rd.QueryContext(ctx.Context, `SELECT tournament_id, COUNT(*) FROM registrations WHERE status = 'pending' GROUP BY tournament_id`)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var id int64
		var n int
		if err := rows.Scan(&id, &n); err != nil {
			rows.Close()
			return nil, err
		}
		pending[id] = n
	}
	rows.Close()
	waiting := map[int64]int{}
	rows, err = rd.QueryContext(ctx.Context, `SELECT tournament_id, COUNT(*) FROM individual_signups WHERE registration_id IS NULL GROUP BY tournament_id`)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var id int64
		var n int
		if err := rows.Scan(&id, &n); err != nil {
			rows.Close()
			return nil, err
		}
		waiting[id] = n
	}
	rows.Close()
	now := ctx.Now().UTC()
	out := make([]AdminRow, 0, len(ts))
	for _, t := range ts {
		miss := Missing(t)
		if miss == nil {
			miss = []string{}
		}
		out = append(out, AdminRow{Card: cardOf(t, now, counts[t.ID]), PendingCount: pending[t.ID], WaitingTeam: waiting[t.ID], Missing: miss})
	}
	return out, nil
}

// AdminDetail 是后台编辑一项赛事要的全部。
type AdminDetail struct {
	Tournament *Tournament `json:"tournament"`
	Missing    []string    `json:"missing"`
	HasEntries bool        `json:"has_entries"`
	HasRegs    bool        `json:"has_registrations"`
	CanDelete  bool        `json:"can_delete"`
	TeamMax    int         `json:"team_max_members"`
}

// AdminGet 后台读一项赛事（含草稿和选手联系方式）。
func (s *Service) AdminGet(ctx *app.Ctx, id int64) (*AdminDetail, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	t, err := GetTournament(ctx.Context, rd, id)
	if err != nil {
		return nil, err
	}
	if t == nil {
		return nil, api.NotFound("赛事不存在")
	}
	d := &AdminDetail{Tournament: t, Missing: Missing(t), TeamMax: teamMaxMembers(ctx.Context, rd)}
	if d.Missing == nil {
		d.Missing = []string{}
	}
	if d.HasEntries, err = hasEntries(ctx.Context, rd, id); err != nil {
		return nil, err
	}
	if d.HasRegs, err = hasRegistrations(ctx.Context, rd, id); err != nil {
		return nil, err
	}
	d.CanDelete = t.PublishedAt == nil && t.Status == StatusDraft
	return d, nil
}

// ReviewRow 是审核页的一条报名。
type ReviewRow struct {
	Registration Registration   `json:"registration"`
	Roster       []RosterMember `json:"roster"`
	Logs         []StatusLog    `json:"logs"`
}

// ReviewList 审核页：一项赛事的全部整队报名（可按状态筛）。
func (s *Service) ReviewList(ctx *app.Ctx, tournamentID int64, status string) ([]ReviewRow, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	q := `SELECT ` + regCols + ` FROM registrations WHERE tournament_id = ?`
	args := []any{tournamentID}
	if status != "" {
		q += ` AND status = ?`
		args = append(args, status)
	}
	rows, err := rd.QueryContext(ctx.Context, q+` ORDER BY submitted_at DESC, id DESC`, args...)
	if err != nil {
		return nil, err
	}
	var regs []*Registration
	for rows.Next() {
		r, err := scanRegistration(rows)
		if err != nil {
			rows.Close()
			return nil, err
		}
		regs = append(regs, r)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	out := make([]ReviewRow, 0, len(regs))
	for _, r := range regs {
		ro, err := roster(ctx.Context, rd, r.ID)
		if err != nil {
			return nil, err
		}
		lg, err := logsOf(ctx.Context, rd, r.ID)
		if err != nil {
			return nil, err
		}
		out = append(out, ReviewRow{Registration: *r, Roster: ro, Logs: lg})
	}
	return out, nil
}
