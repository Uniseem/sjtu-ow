package content

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Preserve explicit expiry and scheduled times; expiry cannot be inferred from
// a timestamp, because a previously expired page may later be published again.
func importPlainPageState(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	expressions := []string{"0", "NULL", "NULL"}
	for i, column := range []string{"expired", "go_live_at", "expire_at"} {
		present, err := legacyColumn(ctx, legacy, "wagtailcore_page", column)
		if err != nil {
			return err
		}
		if present {
			expressions[i] = "p." + column
		}
	}
	rows, err := legacy.QueryContext(ctx, `SELECT p.id,`+expressions[0]+`,`+expressions[1]+`,`+expressions[2]+` FROM content_standardpage sp JOIN wagtailcore_page p ON p.id=sp.page_ptr_id ORDER BY p.id`)
	if err != nil {
		return fmt.Errorf("读取普通页状态: %w", err)
	}
	defer rows.Close()
	return d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		for rows.Next() {
			var id int64
			var expired int
			var goLive, expire sql.NullString
			if err := rows.Scan(&id, &expired, &goLive, &expire); err != nil {
				return err
			}
			dates := []any{nil, nil}
			for i, value := range []sql.NullString{goLive, expire} {
				if value.Valid && value.String != "" {
					parsed, err := db.ParseUTC(value.String)
					if err != nil {
						return fmt.Errorf("普通页 %d 时间无效: %w", id, err)
					}
					dates[i] = db.FormatUTC(parsed)
				}
			}
			if _, err := tx.ExecContext(c, "UPDATE pages SET expired=?,go_live_at=?,expire_at=? WHERE id=? AND kind='site_page' AND version=1", expired, dates[0], dates[1], id); err != nil {
				return err
			}
		}
		return rows.Err()
	})
}
