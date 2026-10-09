package scrims

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func nullTime(ns sql.NullString) *time.Time {
	if !ns.Valid || ns.String == "" {
		return nil
	}
	t, err := db.ParseUTC(ns.String)
	if err != nil {
		return nil
	}
	return &t
}

func parseTime(s string) time.Time {
	t, _ := db.ParseUTC(s)
	return t
}

func timeArg(t *time.Time) any {
	if t == nil {
		return nil
	}
	return db.FormatUTC(*t)
}

func b2i(b bool) int {
	if b {
		return 1
	}
	return 0
}

const scrimCols = `id, title, description, starts_at, signup_closes_at, format, sjtu_only, status, teams_generated_at,
	roster_changed_at, reminder_sent_at, moved_from, created_by, version, board_version, created_at, updated_at`

func scanScrim(row interface{ Scan(...any) error }) (*Scrim, error) {
	var s Scrim
	var starts, closes, gen, changed, reminded, moved sql.NullString
	var by sql.NullInt64
	var sjtu int
	var created, updated string
	if err := row.Scan(&s.ID, &s.Title, &s.Description, &starts, &closes, &s.Format, &sjtu, &s.Status, &gen, &changed,
		&reminded, &moved, &by, &s.Version, &s.BoardVersion, &created, &updated); err != nil {
		return nil, err
	}
	s.StartsAt, s.SignupClosesAt = nullTime(starts), nullTime(closes)
	s.TeamsGeneratedAt, s.RosterChangedAt = nullTime(gen), nullTime(changed)
	s.ReminderSentAt, s.MovedFrom = nullTime(reminded), nullTime(moved)
	if by.Valid {
		v := by.Int64
		s.CreatedBy = &v
	}
	s.SjtuOnly = sjtu == 1
	s.CreatedAt, s.UpdatedAt = parseTime(created), parseTime(updated)
	return &s, nil
}

// GetScrim 读一场内战；不存在返回 nil。
func GetScrim(ctx context.Context, q db.DBTX, id int64) (*Scrim, error) {
	s, err := scanScrim(q.QueryRowContext(ctx, `SELECT `+scrimCols+` FROM scrims WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return s, err
}

const signupCols = `id, scrim_id, user_id, game_account_id, role_tank, role_damage, role_support, is_selected,
	team, assigned_role, rating_used, created_at, updated_at`

func scanSignup(row interface{ Scan(...any) error }) (*Signup, error) {
	var s Signup
	var ga, rating sql.NullInt64
	var tank, damage, support, selected int
	var created, updated string
	if err := row.Scan(&s.ID, &s.ScrimID, &s.UserID, &ga, &tank, &damage, &support, &selected, &s.Team, &s.AssignedRole,
		&rating, &created, &updated); err != nil {
		return nil, err
	}
	if ga.Valid {
		v := ga.Int64
		s.GameAccountID = &v
	}
	if rating.Valid {
		v := int(rating.Int64)
		s.RatingUsed = &v
	}
	s.RoleTank, s.RoleDamage, s.RoleSupport, s.IsSelected = tank == 1, damage == 1, support == 1, selected == 1
	s.CreatedAt, s.UpdatedAt = parseTime(created), parseTime(updated)
	return &s, nil
}

// GetSignup 读某人的报名；没有返回 nil。
func GetSignup(ctx context.Context, q db.DBTX, scrimID, userID int64) (*Signup, error) {
	s, err := scanSignup(q.QueryRowContext(ctx, `SELECT `+signupCols+` FROM scrim_signups WHERE scrim_id = ? AND user_id = ?`, scrimID, userID))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return s, err
}

// listSignups 一场内战的全部报名，按报名先后。
func listSignups(ctx context.Context, q db.DBTX, scrimID int64) ([]*Signup, error) {
	rows, err := q.QueryContext(ctx, `SELECT `+signupCols+` FROM scrim_signups WHERE scrim_id = ? ORDER BY created_at, id`, scrimID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Signup
	for rows.Next() {
		s, err := scanSignup(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// Account 是报名时选的游戏 ID 和它的段位。
type Account struct {
	ID        int64
	Battletag string
	Tank      *int
	Damage    *int
	Support   *int
}

// Rank 某位置的段位。
func (a *Account) Rank(role string) *int {
	if a == nil {
		return nil
	}
	switch role {
	case Tank:
		return a.Tank
	case Damage:
		return a.Damage
	case Support:
		return a.Support
	}
	return nil
}

func loadAccount(ctx context.Context, q db.DBTX, query string, args ...any) (*Account, error) {
	var a Account
	var tank, damage, support sql.NullInt64
	err := q.QueryRowContext(ctx, query, args...).Scan(&a.ID, &a.Battletag, &tank, &damage, &support)
	if errors.Is(err, sql.ErrNoRows) {
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

func getAccount(ctx context.Context, q db.DBTX, id int64) (*Account, error) {
	return loadAccount(ctx, q, `SELECT id, battletag, rank_tank, rank_damage, rank_support FROM game_accounts WHERE id = ?`, id)
}
