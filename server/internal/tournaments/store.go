package tournaments

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

func idArg(p *int64) any {
	if p == nil {
		return nil
	}
	return *p
}

const tournamentCols = `id, title, summary, description, cover_image_id, starts_at, registration_opens_at,
	registration_closes_at, roster_min, roster_max, sjtu_only, registration_mode, auto_approve, status,
	created_by, published_at, reminder_sent_at, moved_from, participant_contact, version, created_at, updated_at`

func scanTournament(row interface{ Scan(...any) error }) (*Tournament, error) {
	var t Tournament
	var cover, by sql.NullInt64
	var starts, opens, closes, published, reminded, moved sql.NullString
	var sjtu, auto int
	var created, updated string
	if err := row.Scan(&t.ID, &t.Title, &t.Summary, &t.Description, &cover, &starts, &opens, &closes,
		&t.RosterMin, &t.RosterMax, &sjtu, &t.RegistrationMode, &auto, &t.Status, &by, &published,
		&reminded, &moved, &t.ParticipantContact, &t.Version, &created, &updated); err != nil {
		return nil, err
	}
	if cover.Valid {
		v := cover.Int64
		t.CoverImageID = &v
	}
	if by.Valid {
		v := by.Int64
		t.CreatedBy = &v
	}
	t.StartsAt, t.RegistrationOpensAt, t.RegistrationClosesAt = nullTime(starts), nullTime(opens), nullTime(closes)
	t.PublishedAt, t.ReminderSentAt, t.MovedFrom = nullTime(published), nullTime(reminded), nullTime(moved)
	t.SjtuOnly, t.AutoApprove = sjtu == 1, auto == 1
	t.CreatedAt, t.UpdatedAt = parseTime(created), parseTime(updated)
	return &t, nil
}

// GetTournament 读一项赛事；不存在返回 nil。
func GetTournament(ctx context.Context, q db.DBTX, id int64) (*Tournament, error) {
	t, err := scanTournament(q.QueryRowContext(ctx, `SELECT `+tournamentCols+` FROM tournaments WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return t, err
}

const regCols = `id, tournament_id, team_id, status, team_name, roster_version, submitted_by, submitted_at,
	status_note, created_at, updated_at`

func scanRegistration(row interface{ Scan(...any) error }) (*Registration, error) {
	var r Registration
	var team, by sql.NullInt64
	var submitted, created, updated string
	if err := row.Scan(&r.ID, &r.TournamentID, &team, &r.Status, &r.TeamName, &r.RosterVersion, &by,
		&submitted, &r.StatusNote, &created, &updated); err != nil {
		return nil, err
	}
	if team.Valid {
		v := team.Int64
		r.TeamID = &v
	}
	if by.Valid {
		v := by.Int64
		r.SubmittedBy = &v
	}
	r.SubmittedAt, r.CreatedAt, r.UpdatedAt = parseTime(submitted), parseTime(created), parseTime(updated)
	return &r, nil
}

// GetRegistration 读一条报名；不存在返回 nil。
func GetRegistration(ctx context.Context, q db.DBTX, id int64) (*Registration, error) {
	r, err := scanRegistration(q.QueryRowContext(ctx, `SELECT `+regCols+` FROM registrations WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return r, err
}

// roster 读一条报名的名单，队长在前，再按昵称。
func roster(ctx context.Context, q db.DBTX, regID int64) ([]RosterMember, error) {
	rows, err := q.QueryContext(ctx, `SELECT id, user_id, game_account_id, nickname, battletag, is_sjtu,
		rank_tank, rank_damage, rank_support, is_captain, is_active FROM registration_members
		WHERE registration_id = ? ORDER BY is_captain DESC, nickname, id`, regID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []RosterMember{}
	for rows.Next() {
		var m RosterMember
		var ga, tank, damage, support sql.NullInt64
		var sjtu, cap, active int
		if err := rows.Scan(&m.ID, &m.UserID, &ga, &m.Nickname, &m.Battletag, &sjtu, &tank, &damage, &support, &cap, &active); err != nil {
			return nil, err
		}
		if ga.Valid {
			v := ga.Int64
			m.GameAccountID = &v
		}
		for _, p := range []struct {
			n   sql.NullInt64
			dst **int
		}{{tank, &m.RankTank}, {damage, &m.RankDamage}, {support, &m.RankSupport}} {
			if p.n.Valid {
				v := int(p.n.Int64)
				*p.dst = &v
			}
		}
		m.IsSJTU, m.IsCaptain, m.Active = sjtu == 1, cap == 1, active == 1
		out = append(out, m)
	}
	return out, rows.Err()
}

func logRegistration(ctx context.Context, tx *db.Tx, regID int64, action, from, to, actorType string, actor *int64, version int64, snapshot string, note string, at time.Time) error {
	var snap any
	if snapshot != "" {
		snap = snapshot
	}
	_, err := tx.ExecContext(ctx, `INSERT INTO registration_status_logs
		(registration_id, action, from_status, to_status, actor_type, actor_user_id, roster_version, roster_snapshot, note, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		regID, action, from, to, actorType, idArg(actor), version, snap, note, db.FormatUTC(at))
	return err
}
