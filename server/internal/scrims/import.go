package scrims

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

// ImportLegacyScrims 从现行站的 Django 库读内战两张表，编号原样沿用（导入顺序「赛事 → 内战」）。
// legacy 要以只读方式打开；反复导入同一份库得到同样的结果，出错一律报出来。
func ImportLegacyScrims(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	now := time.Now().UTC()
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		exists := func(table string, id int64) (bool, error) {
			var n int
			err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM `+table+` WHERE id = ?`, id).Scan(&n)
			return n > 0, err
		}
		var group sql.NullString
		if err := legacy.QueryRowContext(ctx, `SELECT qq_group_url FROM core_sitesettings LIMIT 1`).Scan(&group); err == nil && group.Valid {
			if _, err := tx.ExecContext(txCtx, `UPDATE site_settings SET qq_group_url = ? WHERE id = 1`, group.String); err != nil {
				return err
			}
		}
		scrimCols := make(map[string]bool)
		{
			sRows, err := legacy.QueryContext(ctx, `PRAGMA table_info(scrims_scrim)`)
			if err == nil {
				defer sRows.Close()
				for sRows.Next() {
					var cid, notnull, pk int
					var name, ctype string
					var dflt any
					if err := sRows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err == nil {
						scrimCols[name] = true
					}
				}
			}
		}
		plainCol := "'' AS description_plain"
		if scrimCols["description_plain"] {
			plainCol = "description_plain"
		}
		remindedCol := "NULL AS reminder_sent_at"
		if scrimCols["reminder_sent_at"] {
			remindedCol = "reminder_sent_at"
		}
		movedCol := "NULL AS moved_from"
		if scrimCols["moved_from"] {
			movedCol = "moved_from"
		}

		rows, err := legacy.QueryContext(ctx, fmt.Sprintf(`SELECT id, title, description, %s, starts_at, signup_closes_at, format,
			sjtu_only, status, teams_generated_at, roster_changed_at, %s, %s, created_by_id, created_at, updated_at
			FROM scrims_scrim ORDER BY id`, plainCol, remindedCol, movedCol))
		if err != nil {
			return fmt.Errorf("读旧库 scrims_scrim：%w", err)
		}
		for rows.Next() {
			var id int64
			var title, desc, plain, format, status string
			var sjtu int
			var by sql.NullInt64
			var starts, closes, gen, changed, reminded, moved, created, updated sql.NullString
			if err := rows.Scan(&id, &title, &desc, &plain, &starts, &closes, &format, &sjtu, &status, &gen, &changed, &reminded, &moved,
				&by, &created, &updated); err != nil {
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
			if _, err := tx.ExecContext(txCtx, `INSERT INTO scrims
				(id, title, description, description_plain, starts_at, signup_closes_at, format, sjtu_only, status, teams_generated_at,
				 roster_changed_at, reminder_sent_at, moved_from, created_by, version, board_version, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
				ON CONFLICT (id) DO UPDATE SET title = excluded.title, description = excluded.description,
					description_plain = excluded.description_plain, starts_at = excluded.starts_at,
					signup_closes_at = excluded.signup_closes_at, format = excluded.format, sjtu_only = excluded.sjtu_only,
					status = excluded.status, teams_generated_at = excluded.teams_generated_at,
					roster_changed_at = excluded.roster_changed_at, reminder_sent_at = excluded.reminder_sent_at,
					moved_from = excluded.moved_from, created_by = excluded.created_by, updated_at = excluded.updated_at`,
				id, title, desc, plain, importTimeOpt(starts), importTimeOpt(closes), format, sjtu, status, importTimeOpt(gen),
				importTimeOpt(changed), importTimeOpt(reminded), importTimeOpt(moved), nullID(by),
				importTime(created, now), importTime(updated, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写内战 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, scrim_id, user_id, game_account_id, role_tank, role_damage, role_support,
			is_selected, team, assigned_role, rating_used, created_at, updated_at FROM scrims_scrimsignup ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 scrims_scrimsignup：%w", err)
		}
		defer rows.Close()
		for rows.Next() {
			var id, sid, uid int64
			var ga, rating sql.NullInt64
			var tank, damage, support, selected int
			var team, role string
			var created, updated sql.NullString
			if err := rows.Scan(&id, &sid, &uid, &ga, &tank, &damage, &support, &selected, &team, &role, &rating, &created, &updated); err != nil {
				return err
			}
			if ga.Valid {
				if ok, err := exists("game_accounts", ga.Int64); err != nil {
					return err
				} else if !ok {
					ga = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO scrim_signups
				(id, scrim_id, user_id, game_account_id, role_tank, role_damage, role_support, is_selected, team, assigned_role,
				 rating_used, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET game_account_id = excluded.game_account_id, role_tank = excluded.role_tank,
					role_damage = excluded.role_damage, role_support = excluded.role_support, is_selected = excluded.is_selected,
					team = excluded.team, assigned_role = excluded.assigned_role, rating_used = excluded.rating_used,
					updated_at = excluded.updated_at`,
				id, sid, uid, nullID(ga), tank, damage, support, selected, team, role, nullID(rating),
				importTime(created, now), importTime(updated, now)); err != nil {
				return fmt.Errorf("写内战报名 %d：%w", id, err)
			}
		}
		return rows.Err()
	})
}
