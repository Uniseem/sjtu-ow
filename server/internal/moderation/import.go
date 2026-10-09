package moderation

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

// ImportLegacyModeration 从现行站的 Django 库读审核记录，编号原样沿用；割接前的后台只读显示
// （决定 D5）。legacy 要以只读方式打开；反复导入同一份库得到同样的结果，出错一律报出来。
func ImportLegacyModeration(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	now := time.Now().UTC()
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		exists := func(id int64) (bool, error) {
			var n int
			err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM users WHERE id = ?`, id).Scan(&n)
			return n > 0, err
		}
		rows, err := legacy.QueryContext(ctx, `SELECT id, target_type, target_id, field, url, author_id, excerpt, full_text, text_hash, risk,
			categories, reason, quote, model, input_tokens, output_tokens, status, reviewed_by_id, reviewed_at, handling_note,
			checked_at, notified_at, attempts, last_error, failed_at, created_at FROM moderation_moderationitem ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 moderation_moderationitem：%w", err)
		}
		defer rows.Close()
		for rows.Next() {
			var id, targetID int64
			var in, out, attempts int
			var tt, field, url, excerpt, full, hash, risk, cats, reason, quote, model, status, note, lastErr string
			var author, by sql.NullInt64
			var reviewed, checked, notified, failed, created sql.NullString
			if err := rows.Scan(&id, &tt, &targetID, &field, &url, &author, &excerpt, &full, &hash, &risk, &cats, &reason, &quote,
				&model, &in, &out, &status, &by, &reviewed, &note, &checked, &notified, &attempts, &lastErr, &failed, &created); err != nil {
				return err
			}
			for _, p := range []*sql.NullInt64{&author, &by} {
				if p.Valid {
					if ok, err := exists(p.Int64); err != nil {
						return err
					} else if !ok {
						*p = sql.NullInt64{}
					}
				}
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO moderation_items
				(id, target_type, target_id, field, url, author_id, excerpt, full_text, text_hash, risk, categories, reason, quote, model,
				 input_tokens, output_tokens, status, reviewed_by, reviewed_at, handling_note, checked_at, notified_at, attempts,
				 last_error, failed_at, created_at)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET risk = excluded.risk, categories = excluded.categories, reason = excluded.reason,
					quote = excluded.quote, status = excluded.status, reviewed_by = excluded.reviewed_by,
					reviewed_at = excluded.reviewed_at, handling_note = excluded.handling_note, checked_at = excluded.checked_at,
					notified_at = excluded.notified_at, attempts = excluded.attempts, last_error = excluded.last_error,
					failed_at = excluded.failed_at`,
				id, tt, targetID, field, url, nullID(author), excerpt, full, hash, risk, cats, reason, quote, model, in, out, status,
				nullID(by), importTimeOpt(reviewed), note, importTimeOpt(checked), importTimeOpt(notified), attempts, lastErr,
				importTimeOpt(failed), importTime(created, now)); err != nil {
				return fmt.Errorf("写审核记录 %d：%w", id, err)
			}
		}
		return rows.Err()
	})
}
