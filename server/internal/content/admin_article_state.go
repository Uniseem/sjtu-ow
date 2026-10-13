package content

import (
	"database/sql"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Read admin-only publication and announcement state in one query. Merely
// choosing a future time in a draft does not approve its scheduled revision.
func (m *Module) readArticleAdminStates(ctx *app.Ctx, articles []*Article) error {
	if len(articles) == 0 {
		return nil
	}
	byID := make(map[int64]*Article, len(articles))
	for _, article := range articles {
		byID[article.ID] = article
	}
	rows, err := m.svc.store.d.ReadPool().QueryContext(ctx.Context, `SELECT p.id,p.expired,
        EXISTS(SELECT 1 FROM page_revisions schedule WHERE schedule.page_id=p.id AND schedule.approved_go_live_at IS NOT NULL),
        latest.created_at,
        (SELECT schedule.approved_go_live_at FROM page_revisions schedule WHERE schedule.page_id=p.id AND schedule.approved_go_live_at IS NOT NULL ORDER BY schedule.id DESC LIMIT 1),
        (SELECT COUNT(*) FROM broadcasts b WHERE b.kind='article' AND b.object_id=p.id AND b.waits_for_publish=0),
        EXISTS(SELECT 1 FROM broadcasts b WHERE b.kind='article' AND b.object_id=p.id AND b.waits_for_publish=1)
        FROM pages p LEFT JOIN page_revisions latest ON latest.id=p.latest_revision_id WHERE p.kind='article'`)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var expired, scheduled, announced, waiting int
		var revised, planned sql.NullString
		if err := rows.Scan(&id, &expired, &scheduled, &revised, &planned, &announced, &waiting); err != nil {
			return err
		}
		article := byID[id]
		if article == nil {
			continue
		}
		article.Expired = expired == 1
		article.ApprovedSchedule = scheduled == 1
		if !article.Live && planned.Valid {
			if value, err := db.ParseUTC(planned.String); err == nil {
				article.GoLiveAt = &value
			}
		}
		if revised.Valid {
			if value, err := db.ParseUTC(revised.String); err == nil {
				article.LatestRevisionCreatedAt = &value
			}
		}
		if m.svc.canEditAuthor(ctx.Viewer) {
			article.Announced = announced
			article.CanAnnounce = waiting == 0 && (article.Live || article.ApprovedSchedule && article.GoLiveAt != nil && article.GoLiveAt.After(ctx.Now()))
		}
	}
	return rows.Err()
}
