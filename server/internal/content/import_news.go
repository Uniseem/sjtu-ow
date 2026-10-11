package content

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func importNewsIndexes(ctx context.Context, d *db.DB, legacy *sql.DB, now time.Time) error {
	rows, err := legacy.QueryContext(ctx, `SELECT p.id,p.slug,p.title,p.live,p.has_unpublished_changes,p.go_live_at,p.expire_at,
 p.first_published_at,p.last_published_at,p.live_revision_id,p.owner_id,p.seo_title,p.search_description,n.intro,
 (SELECT parent.id FROM wagtailcore_page parent WHERE parent.path=substr(p.path,1,length(p.path)-4)),
 NOT EXISTS (SELECT 1 FROM wagtailcore_pageviewrestriction vr JOIN wagtailcore_page restricted ON restricted.id=vr.page_id WHERE substr(p.path,1,length(restricted.path))=restricted.path)
 FROM content_articleindexpage n JOIN wagtailcore_page p ON p.id=n.page_ptr_id ORDER BY p.id`)
	if err != nil {
		return fmt.Errorf("导入 content_articleindexpage：读取失败: %w", err)
	}
	defer rows.Close()
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		for rows.Next() {
			var id int64
			var slug, title, intro string
			var live, unpub, public int
			var goLive, expire, first, last, seo, description sql.NullString
			var revision, owner, parent sql.NullInt64
			if err := rows.Scan(&id, &slug, &title, &live, &unpub, &goLive, &expire, &first, &last, &revision, &owner, &seo, &description, &intro, &parent, &public); err != nil {
				return fmt.Errorf("扫描栏目: %w", err)
			}
			date := func(v sql.NullString) any {
				if !v.Valid || v.String == "" {
					return nil
				}
				return parseAndFormatUTC(v.String, now)
			}
			_, err := tx.ExecContext(ctx, `INSERT INTO pages (id,kind,slug,title,live,has_unpublished_changes,go_live_at,expire_at,first_published_at,last_published_at,live_revision_id,latest_revision_id,owner_id,seo_title,search_description,parent_id,search_public,created_at,updated_at)
    VALUES (?,'news_index',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING`, id, slug, title, live, unpub, date(goLive), date(expire), date(first), date(last), revision, revision, owner, seo.String, description.String, parent, public, db.FormatUTC(now), db.FormatUTC(now))
			if err != nil {
				return fmt.Errorf("写栏目 %d: %w", id, err)
			}
			if _, err := tx.ExecContext(ctx, `INSERT INTO news_index (page_id,intro) VALUES (?,?) ON CONFLICT(page_id) DO NOTHING`, id, intro); err != nil {
				return fmt.Errorf("写栏目简介 %d: %w", id, err)
			}
		}
		return rows.Err()
	})
	if err != nil {
		return fmt.Errorf("导入 content_articleindexpage：%w", err)
	}
	return nil
}
