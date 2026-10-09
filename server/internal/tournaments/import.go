package tournaments

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func importTime(ns sql.NullString, fallback time.Time) string {
	if ns.Valid && ns.String != "" {
		if t, err := db.ParseUTC(ns.String); err == nil {
			return db.FormatUTC(t)
		}
	}
	return db.FormatUTC(fallback)
}

func importTimeOpt(ns sql.NullString) any {
	if !ns.Valid || ns.String == "" {
		return nil
	}
	if t, err := db.ParseUTC(ns.String); err == nil {
		return db.FormatUTC(t)
	}
	return nil
}

func nullID(n sql.NullInt64) any {
	if !n.Valid {
		return nil
	}
	return n.Int64
}

// ImportLegacyTournaments 从现行站的 Django 库读赛事五张表，编号原样沿用（导入顺序「战队 → 赛事」）。
// legacy 要以只读方式打开；反复导入同一份库得到同样的结果，出错一律报出来。
func ImportLegacyTournaments(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	now := time.Now().UTC()
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		exists := func(table string, id int64) (bool, error) {
			var n int
			err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM `+table+` WHERE id = ?`, id).Scan(&n)
			return n > 0, err
		}
		tournCols := make(map[string]bool)
		{
			tRows, err := legacy.QueryContext(ctx, `PRAGMA table_info(tournaments_tournament)`)
			if err == nil {
				defer tRows.Close()
				for tRows.Next() {
					var cid, notnull, pk int
					var name, ctype string
					var dflt any
					if err := tRows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err == nil {
						tournCols[name] = true
					}
				}
			}
		}
		plainCol := "'' AS description_plain"
		if tournCols["description_plain"] {
			plainCol = "description_plain"
		}
		modeCol := "'team' AS registration_mode"
		if tournCols["registration_mode"] {
			modeCol = "registration_mode"
		}
		autoCol := "0 AS auto_approve"
		if tournCols["auto_approve"] {
			autoCol = "auto_approve"
		} else if tournCols["review_mode"] {
			autoCol = "CASE WHEN review_mode = 'auto' THEN 1 ELSE 0 END AS auto_approve"
		}
		remindedCol := "NULL AS reminder_sent_at"
		if tournCols["reminder_sent_at"] {
			remindedCol = "reminder_sent_at"
		}
		movedCol := "NULL AS moved_from"
		if tournCols["moved_from"] {
			movedCol = "moved_from"
		}
		contactCol := "'' AS participant_contact"
		if tournCols["participant_contact"] {
			contactCol = "participant_contact"
		}

		rows, err := legacy.QueryContext(ctx, fmt.Sprintf(`SELECT id, title, summary, description, %s, cover_id, starts_at,
			registration_opens_at, registration_closes_at, roster_min, roster_max, sjtu_only, %s, %s,
			status, created_by_id, published_at, %s, %s, %s, created_at, updated_at
			FROM tournaments_tournament ORDER BY id`, plainCol, modeCol, autoCol, remindedCol, movedCol, contactCol))
		if err != nil {
			return fmt.Errorf("读旧库 tournaments_tournament：%w", err)
		}
		for rows.Next() {
			var id int64
			var title, summary, desc, plain, mode, status, contact string
			var cover, by sql.NullInt64
			var starts, opens, closes, published, reminded, moved, created, updated sql.NullString
			var min, max, sjtu, auto int
			if err := rows.Scan(&id, &title, &summary, &desc, &plain, &cover, &starts, &opens, &closes, &min, &max, &sjtu,
				&mode, &auto, &status, &by, &published, &reminded, &moved, &contact, &created, &updated); err != nil {
				rows.Close()
				return err
			}
			if cover.Valid {
				if ok, err := exists("images", cover.Int64); err != nil {
					rows.Close()
					return err
				} else if !ok {
					cover = sql.NullInt64{}
				}
			}
			if by.Valid {
				if ok, err := exists("users", by.Int64); err != nil {
					rows.Close()
					return err
				} else if !ok {
					by = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO tournaments
				(id, title, summary, description, description_plain, cover_image_id, starts_at, registration_opens_at,
				 registration_closes_at, roster_min, roster_max, sjtu_only, registration_mode, auto_approve, status,
				 created_by, published_at, reminder_sent_at, moved_from, participant_contact, version, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
				ON CONFLICT (id) DO UPDATE SET title = excluded.title, summary = excluded.summary,
					description = excluded.description, description_plain = excluded.description_plain,
					cover_image_id = excluded.cover_image_id, starts_at = excluded.starts_at,
					registration_opens_at = excluded.registration_opens_at, registration_closes_at = excluded.registration_closes_at,
					roster_min = excluded.roster_min, roster_max = excluded.roster_max, sjtu_only = excluded.sjtu_only,
					registration_mode = excluded.registration_mode, auto_approve = excluded.auto_approve, status = excluded.status,
					created_by = excluded.created_by, published_at = excluded.published_at,
					reminder_sent_at = excluded.reminder_sent_at, moved_from = excluded.moved_from,
					participant_contact = excluded.participant_contact, updated_at = excluded.updated_at`,
				id, title, summary, desc, plain, nullID(cover), importTimeOpt(starts), importTimeOpt(opens), importTimeOpt(closes),
				min, max, sjtu, mode, auto, status, nullID(by), importTimeOpt(published), importTimeOpt(reminded), importTimeOpt(moved),
				contact, importTime(created, now), importTime(updated, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写赛事 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, tournament_id, team_id, status, team_name, roster_version, submitted_by_id,
			submitted_at, status_note, created_at, updated_at FROM tournaments_registration ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 tournaments_registration：%w", err)
		}
		for rows.Next() {
			var id, tid int64
			var team, by sql.NullInt64
			var status, name, note string
			var version int
			var submitted, created, updated sql.NullString
			if err := rows.Scan(&id, &tid, &team, &status, &name, &version, &by, &submitted, &note, &created, &updated); err != nil {
				rows.Close()
				return err
			}
			if by.Valid {
				if ok, err := exists("users", by.Int64); err != nil {
					rows.Close()
					return err
				} else if !ok {
					by = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO registrations
				(id, tournament_id, team_id, status, team_name, roster_version, submitted_by, submitted_at, status_note, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET status = excluded.status, team_name = excluded.team_name,
					roster_version = excluded.roster_version, status_note = excluded.status_note, updated_at = excluded.updated_at`,
				id, tid, nullID(team), status, name, version, nullID(by), importTime(submitted, now), note,
				importTime(created, now), importTime(updated, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写报名 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, registration_id, tournament_id, user_id, game_account_id, nickname, battletag,
			is_sjtu, rank_tank, rank_damage, rank_support, is_captain, is_active FROM tournaments_registrationmember ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 tournaments_registrationmember：%w", err)
		}
		for rows.Next() {
			var id, regID, tid, uid int64
			var ga, tank, damage, support sql.NullInt64
			var nick, bt string
			var sjtu, cap, active int
			if err := rows.Scan(&id, &regID, &tid, &uid, &ga, &nick, &bt, &sjtu, &tank, &damage, &support, &cap, &active); err != nil {
				rows.Close()
				return err
			}
			if ga.Valid {
				if ok, err := exists("game_accounts", ga.Int64); err != nil {
					rows.Close()
					return err
				} else if !ok {
					ga = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO registration_members
				(id, registration_id, tournament_id, user_id, game_account_id, nickname, battletag, is_sjtu,
				 rank_tank, rank_damage, rank_support, is_captain, is_active)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET game_account_id = excluded.game_account_id, nickname = excluded.nickname,
					battletag = excluded.battletag, is_sjtu = excluded.is_sjtu, rank_tank = excluded.rank_tank,
					rank_damage = excluded.rank_damage, rank_support = excluded.rank_support,
					is_captain = excluded.is_captain, is_active = excluded.is_active`,
				id, regID, tid, uid, nullID(ga), nick, bt, sjtu, nullID(tank), nullID(damage), nullID(support), cap, active); err != nil {
				rows.Close()
				return fmt.Errorf("写名单成员 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, registration_id, action, from_status, to_status, actor_type, actor_user_id,
			roster_version, roster_snapshot, note, created_at FROM tournaments_registrationstatuslog ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 tournaments_registrationstatuslog：%w", err)
		}
		for rows.Next() {
			var id, regID int64
			var action, from, to, actorType, note string
			var actor sql.NullInt64
			var version int
			var snap, created sql.NullString
			if err := rows.Scan(&id, &regID, &action, &from, &to, &actorType, &actor, &version, &snap, &note, &created); err != nil {
				rows.Close()
				return err
			}
			if actor.Valid {
				if ok, err := exists("users", actor.Int64); err != nil {
					rows.Close()
					return err
				} else if !ok {
					actor = sql.NullInt64{}
				}
			}
			var snapArg any
			if snap.Valid {
				snapArg = snap.String
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO registration_status_logs
				(id, registration_id, action, from_status, to_status, actor_type, actor_user_id, roster_version, roster_snapshot, note, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING`,
				id, regID, action, from, to, actorType, nullID(actor), version, snapArg, note, importTime(created, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写状态日志 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, tournament_id, user_id, game_account_id, role_tank, role_damage, role_support,
			registration_id, created_at, updated_at FROM tournaments_individualsignup ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 tournaments_individualsignup：%w", err)
		}
		defer rows.Close()
		for rows.Next() {
			var id, tid, uid int64
			var ga, reg sql.NullInt64
			var tank, damage, support int
			var created, updated sql.NullString
			if err := rows.Scan(&id, &tid, &uid, &ga, &tank, &damage, &support, &reg, &created, &updated); err != nil {
				return err
			}
			if ga.Valid {
				if ok, err := exists("game_accounts", ga.Int64); err != nil {
					return err
				} else if !ok {
					ga = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO individual_signups
				(id, tournament_id, user_id, game_account_id, role_tank, role_damage, role_support, registration_id, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET game_account_id = excluded.game_account_id, role_tank = excluded.role_tank,
					role_damage = excluded.role_damage, role_support = excluded.role_support,
					registration_id = excluded.registration_id, updated_at = excluded.updated_at`,
				id, tid, uid, nullID(ga), tank, damage, support, nullID(reg), importTime(created, now), importTime(updated, now)); err != nil {
				return fmt.Errorf("写个人报名 %d：%w", id, err)
			}
		}
		return rows.Err()
	})
}
