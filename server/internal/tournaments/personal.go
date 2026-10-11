package tournaments

import (
	"database/sql"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// CalendarAddressReader delegates token construction to agenda's sole signer.
// The callback keeps each activity package independent of calendar internals.
type CalendarAddressReader func(*app.Ctx) (url, webcal string, err error)

type CalendarAddress struct {
	URL    string `json:"url"`
	Webcal string `json:"webcal"`
}

func (s *Service) SetCalendarAddressReader(reader CalendarAddressReader) { s.calendar = reader }

// PersonalIndividualSignup is a private projection of the actor's own signup.
// No user id query parameter is accepted, and other people's game IDs never
// enter this response.
type PersonalIndividualSignup struct {
	ID                   int64      `json:"id"`
	TournamentID         int64      `json:"tournament_id"`
	Title                string     `json:"title"`
	StartsAt             *time.Time `json:"starts_at"`
	StartsLabel          string     `json:"starts_label"`
	Battletag            *string    `json:"battletag"`
	RoleTank             bool       `json:"role_tank"`
	RoleDamage           bool       `json:"role_damage"`
	RoleSupport          bool       `json:"role_support"`
	RegistrationID       *int64     `json:"registration_id"`
	RegistrationTeamName string     `json:"registration_team_name"`
	TournamentStatus     string     `json:"tournament_status"`
	RegistrationOpen     bool       `json:"registration_open"`
	CanCancel            bool       `json:"can_cancel"`
	CanEdit              bool       `json:"can_edit"`
	GameAccountID        *int64     `json:"game_account_id"`
	CreatedAt            time.Time  `json:"created_at"`
}

func startsLabel(value *time.Time) string {
	if value == nil {
		return "待定"
	}
	return value.In(shanghai).Format("2006.01.02 15:04")
}

func (s *Service) PersonalIndividualSignups(ctx *app.Ctx) ([]PersonalIndividualSignup, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	q := s.d.ReadPool()
	rows, err := q.QueryContext(ctx.Context, `SELECT signup.id,signup.tournament_id,t.title,t.starts_at,
		account.battletag,signup.role_tank,signup.role_damage,signup.role_support,
		signup.registration_id,COALESCE(registration.team_name,''),t.status,
		t.registration_opens_at,t.registration_closes_at,signup.game_account_id,signup.created_at
		FROM individual_signups signup JOIN tournaments t ON t.id=signup.tournament_id
		LEFT JOIN game_accounts account ON account.id=signup.game_account_id
		LEFT JOIN registrations registration ON registration.id=signup.registration_id
		WHERE signup.user_id=? ORDER BY signup.created_at DESC,signup.id DESC`, viewer.ID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []PersonalIndividualSignup{}
	for rows.Next() {
		var item PersonalIndividualSignup
		var starts, battletag, opens, closes sql.NullString
		var registration, account sql.NullInt64
		var tank, damage, support int
		var created string
		if err := rows.Scan(&item.ID, &item.TournamentID, &item.Title, &starts, &battletag, &tank, &damage, &support,
			&registration, &item.RegistrationTeamName, &item.TournamentStatus, &opens, &closes, &account, &created); err != nil {
			return nil, err
		}
		item.StartsAt = nullTime(starts)
		item.StartsLabel = startsLabel(item.StartsAt)
		item.RoleTank, item.RoleDamage, item.RoleSupport = tank == 1, damage == 1, support == 1
		item.CreatedAt = parseTime(created)
		if battletag.Valid {
			tag := battletag.String
			item.Battletag = &tag
		}
		if registration.Valid {
			id := registration.Int64
			item.RegistrationID = &id
		}
		if account.Valid {
			id := account.Int64
			item.GameAccountID = &id
		}
		tournament := &Tournament{Status: item.TournamentStatus, RegistrationOpensAt: nullTime(opens), RegistrationClosesAt: nullTime(closes)}
		item.RegistrationOpen = tournament.RegistrationOpen(ctx.Now().UTC())
		item.CanCancel = item.RegistrationID == nil && item.RegistrationOpen
		item.CanEdit = item.CanCancel
		out = append(out, item)
	}
	return out, rows.Err()
}

func (s *Service) PersonalRegistrations(ctx *app.Ctx) (*MineOut, error) {
	if _, err := requireLogin(ctx); err != nil {
		return nil, err
	}
	registrations, err := s.MyRegistrations(ctx)
	if err != nil {
		return nil, err
	}
	individuals, err := s.PersonalIndividualSignups(ctx)
	if err != nil {
		return nil, err
	}
	out := &MineOut{Registrations: registrations, IndividualSignups: individuals}
	if s.calendar != nil {
		url, webcal, err := s.calendar(ctx)
		if err != nil {
			return nil, err
		}
		out.Calendar = &CalendarAddress{URL: url, Webcal: webcal}
	}
	return out, nil
}
