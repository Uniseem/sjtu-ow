package scrims

import (
	"database/sql"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

type CalendarAddressReader func(*app.Ctx) (url, webcal string, err error)

type CalendarAddress struct {
	URL    string `json:"url"`
	Webcal string `json:"webcal"`
}

func (s *Service) SetCalendarAddressReader(reader CalendarAddressReader) { s.calendar = reader }

// PersonalSignup includes only the actor's own placement. Public signup rows
// intentionally use a separate DTO with no team, game ID or private rating.
type PersonalSignup struct {
	ID             int64      `json:"id"`
	ScrimID        int64      `json:"scrim_id"`
	Title          string     `json:"title"`
	StartsAt       *time.Time `json:"starts_at"`
	SignupDeadline *time.Time `json:"signup_deadline"`
	Format         string     `json:"format"`
	RoleTank       bool       `json:"role_tank"`
	RoleDamage     bool       `json:"role_damage"`
	RoleSupport    bool       `json:"role_support"`
	Placement      string     `json:"placement"`
	Status         string     `json:"status"`
	StatusLabel    string     `json:"status_label"`
	CanCancel      bool       `json:"can_cancel"`
	CanEdit        bool       `json:"can_edit"`
	GameAccountID  *int64     `json:"game_account_id"`
	Battletag      *string    `json:"battletag"`
	IsSelected     bool       `json:"is_selected"`
	Team           string     `json:"team"`
	AssignedRole   string     `json:"assigned_role"`
	CreatedAt      time.Time  `json:"created_at"`
}

type PersonalOut struct {
	Signups  []PersonalSignup `json:"signups"`
	Calendar *CalendarAddress `json:"calendar,omitempty"`
}

func (s *Service) Personal(ctx *app.Ctx) (*PersonalOut, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT signup.id,signup.scrim_id,sc.title,sc.starts_at,
		sc.signup_closes_at,sc.format,signup.role_tank,signup.role_damage,signup.role_support,
		sc.status,signup.game_account_id,account.battletag,signup.is_selected,signup.team,
		signup.assigned_role,signup.created_at,
		EXISTS(SELECT 1 FROM scrim_signups teammate WHERE teammate.scrim_id=sc.id AND teammate.team<>'')
		FROM scrim_signups signup JOIN scrims sc ON sc.id=signup.scrim_id
		LEFT JOIN game_accounts account ON account.id=signup.game_account_id
		WHERE signup.user_id=? ORDER BY sc.starts_at DESC,signup.created_at DESC,signup.id DESC`, viewer.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := &PersonalOut{Signups: []PersonalSignup{}}
	for rows.Next() {
		var item PersonalSignup
		var starts, deadline, battletag sql.NullString
		var account sql.NullInt64
		var tank, damage, support, selected, hasTeams int
		var created string
		if err := rows.Scan(&item.ID, &item.ScrimID, &item.Title, &starts, &deadline, &item.Format, &tank, &damage, &support,
			&item.Status, &account, &battletag, &selected, &item.Team, &item.AssignedRole, &created, &hasTeams); err != nil {
			return nil, err
		}
		item.StartsAt = nullTime(starts)
		item.SignupDeadline = nullTime(deadline)
		item.RoleTank, item.RoleDamage, item.RoleSupport = tank == 1, damage == 1, support == 1
		item.IsSelected = selected == 1
		item.CreatedAt = parseTime(created)
		if account.Valid {
			id := account.Int64
			item.GameAccountID = &id
		}
		if battletag.Valid {
			tag := battletag.String
			item.Battletag = &tag
		}
		scrim := &Scrim{ID: item.ScrimID, Format: item.Format, Status: item.Status, StartsAt: item.StartsAt, SignupClosesAt: item.SignupDeadline}
		signup := &Signup{IsSelected: item.IsSelected, Team: item.Team, AssignedRole: item.AssignedRole}
		item.Placement = PlacementText(scrim, signup, hasTeams == 1)
		item.CanCancel = scrim.IsPublic() && scrim.Deadline() != nil && !ctx.Now().After(*scrim.Deadline())
		item.CanEdit = scrim.SignupOpen(ctx.Now().UTC())
		switch item.Status {
		case StatusCancelled:
			item.StatusLabel = "已取消"
		case StatusFinished:
			item.StatusLabel = "已结束"
		default:
			item.StatusLabel = "已报名"
		}
		out.Signups = append(out.Signups, item)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	// Release the result set before calling agenda on the shared read pool.
	if err := rows.Close(); err != nil {
		return nil, err
	}
	if s.calendar != nil {
		url, webcal, err := s.calendar(ctx)
		if err != nil {
			return nil, err
		}
		out.Calendar = &CalendarAddress{URL: url, Webcal: webcal}
	}
	return out, nil
}

func (m *Module) personal(ctx *app.Ctx, _ struct{}) (*PersonalOut, error) { return m.svc.Personal(ctx) }
