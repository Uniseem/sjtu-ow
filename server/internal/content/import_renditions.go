package content

import (
	"context"
	"database/sql"
	"fmt"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

// Keep the old inline-body thumbnail addresses, associated with their image so
// deletion can retire only that image's files. Originals are never public.
func importLegacyRenditions(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	var exists int
	if err := legacy.QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='wagtailimages_rendition'`).Scan(&exists); err != nil {
		return err
	}
	if exists == 0 {
		return nil
	}
	rows, err := legacy.QueryContext(ctx, `SELECT image_id,file FROM wagtailimages_rendition ORDER BY id`)
	if err != nil {
		return err
	}
	defer rows.Close()
	return d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		for rows.Next() {
			var id int64
			var file string
			if err := rows.Scan(&id, &file); err != nil {
				return err
			}
			if !media.LegacyRenditionPath(file) {
				return fmt.Errorf("旧缩略图路径无效，图片编号%d", id)
			}
			// Deleted/orphan images are not resurrected by a cached rendition.
			if _, err := tx.ExecContext(c, `INSERT INTO legacy_image_renditions(file_name,image_id) SELECT ?,id FROM images WHERE id=? ON CONFLICT(file_name) DO NOTHING`, file, id); err != nil {
				return err
			}
		}
		return rows.Err()
	})
}
