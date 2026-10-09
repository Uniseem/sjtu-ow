package teams

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func importTime(s string, fallback time.Time) string {
	if t, err := db.ParseUTC(s); s != "" && err == nil {
		return db.FormatUTC(t)
	}
	return db.FormatUTC(fallback)
}

func importTimeOpt(ns sql.NullString, fallback time.Time) any {
	if !ns.Valid || ns.String == "" {
		return nil
	}
	return importTime(ns.String, fallback)
}

func idOpt(n sql.NullInt64) any {
	if !n.Valid {
		return nil
	}
	return n.Int64
}

// ImportLegacyTeams 从现行站的 Django 库读战队四张表和全站设置里的两个上限，编号原样沿用
// （12 号文档 8.1，导入顺序「图片 → 战队」）。legacy 要以只读方式打开；反复导入同一份库
// 得到同样的结果。读写出错一律报出来，不吞。
func ImportLegacyTeams(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	now := time.Now().UTC()
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		// 全站设置里战队的两个上限。表或行不在就保留默认的 10 和 3。
		var maxMembers, maxCaptained sql.NullInt64
		err := legacy.QueryRowContext(ctx, `SELECT team_max_members, team_max_captained FROM core_sitesettings LIMIT 1`).
			Scan(&maxMembers, &maxCaptained)
		if err == nil {
			if maxMembers.Valid && maxMembers.Int64 > 0 {
				if _, err := tx.ExecContext(txCtx, `UPDATE site_settings SET team_max_members = ? WHERE id = 1`, maxMembers.Int64); err != nil {
					return err
				}
			}
			if maxCaptained.Valid && maxCaptained.Int64 > 0 {
				if _, err := tx.ExecContext(txCtx, `UPDATE site_settings SET team_max_captained = ? WHERE id = 1`, maxCaptained.Int64); err != nil {
					return err
				}
			}
		}

		rows, err := legacy.QueryContext(ctx, `SELECT id, name, description, logo_id, is_recruiting, recruiting_roles,
			member_contact, disbanded_at, created_at, updated_at FROM teams_team ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 teams_team：%w", err)
		}
		for rows.Next() {
			var id int64
			var name, desc, roles, contact, created, updated string
			var logo sql.NullInt64
			var recruiting int
			var disbanded sql.NullString
			if err := rows.Scan(&id, &name, &desc, &logo, &recruiting, &roles, &contact, &disbanded, &created, &updated); err != nil {
				rows.Close()
				return err
			}
			if logo.Valid {
				var n int
				if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM images WHERE id = ?`, logo.Int64).Scan(&n); err != nil {
					rows.Close()
					return err
				}
				if n == 0 {
					logo = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO teams
				(id, name, description, logo_image_id, is_recruiting, recruiting_roles, member_contact,
				 disbanded_at, version, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
				ON CONFLICT (id) DO UPDATE SET
					name = excluded.name, description = excluded.description,
					logo_image_id = excluded.logo_image_id, is_recruiting = excluded.is_recruiting,
					recruiting_roles = excluded.recruiting_roles, member_contact = excluded.member_contact,
					disbanded_at = excluded.disbanded_at, updated_at = excluded.updated_at`,
				id, name, desc, idOpt(logo), recruiting, roles, contact, importTimeOpt(disbanded, now),
				importTime(created, now), importTime(updated, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写战队 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, team_id, user_id, role, joined_at FROM teams_teammembership ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 teams_teammembership：%w", err)
		}
		for rows.Next() {
			var id, teamID, userID int64
			var role, joined string
			if err := rows.Scan(&id, &teamID, &userID, &role, &joined); err != nil {
				rows.Close()
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO team_memberships (id, team_id, user_id, role, joined_at)
				VALUES (?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET team_id = excluded.team_id, user_id = excluded.user_id,
					role = excluded.role, joined_at = excluded.joined_at`,
				id, teamID, userID, role, importTime(joined, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写战队成员 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, team_id, applicant_id, role_tank, role_damage, role_support,
			message, status, decided_by_id, decided_at, decision_note, captain_reminded_at, created_at
			FROM teams_teamapplication ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 teams_teamapplication：%w", err)
		}
		for rows.Next() {
			var id, teamID, applicant int64
			var tank, damage, support int
			var message, status, note, created string
			var by sql.NullInt64
			var decided, reminded sql.NullString
			if err := rows.Scan(&id, &teamID, &applicant, &tank, &damage, &support, &message, &status,
				&by, &decided, &note, &reminded, &created); err != nil {
				rows.Close()
				return err
			}
			if by.Valid {
				var n int
				if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM users WHERE id = ?`, by.Int64).Scan(&n); err != nil {
					rows.Close()
					return err
				}
				if n == 0 {
					by = sql.NullInt64{}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO team_applications
				(id, team_id, applicant_id, role_tank, role_damage, role_support, message, status,
				 decided_by, decided_at, decision_note, captain_reminded_at, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET
					status = excluded.status, decided_by = excluded.decided_by, decided_at = excluded.decided_at,
					decision_note = excluded.decision_note, captain_reminded_at = excluded.captain_reminded_at`,
				id, teamID, applicant, tank, damage, support, message, status, idOpt(by),
				importTimeOpt(decided, now), note, importTimeOpt(reminded, now), importTime(created, now)); err != nil {
				rows.Close()
				return fmt.Errorf("写入队申请 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, team_id, user_id, role, joined_at, left_at, reason
			FROM teams_teamalumnus ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 teams_teamalumnus：%w", err)
		}
		defer rows.Close()
		for rows.Next() {
			var id, teamID, userID int64
			var role, joined, left, reason string
			if err := rows.Scan(&id, &teamID, &userID, &role, &joined, &left, &reason); err != nil {
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO team_alumni (id, team_id, user_id, role, joined_at, left_at, reason)
				VALUES (?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET role = excluded.role, joined_at = excluded.joined_at,
					left_at = excluded.left_at, reason = excluded.reason`,
				id, teamID, userID, role, importTime(joined, now), importTime(left, now), reason); err != nil {
				return fmt.Errorf("写退役记录 %d：%w", id, err)
			}
		}
		return rows.Err()
	})
}
