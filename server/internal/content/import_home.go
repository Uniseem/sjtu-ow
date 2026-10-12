package content

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"sort"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// The homepage is a separate aggregate: pages.kind deliberately excludes it.
// Retain its original state and revision JSON without converting live pins to drafts.
func importHomeState(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	var exists int
	if err := legacy.QueryRowContext(ctx, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='content_homepage'").Scan(&exists); err != nil {
		return err
	}
	if exists == 0 {
		return nil
	}
	var id int64
	var live, unpublished int
	var published, latestCreated sql.NullString
	var latestID, author sql.NullInt64
	err := legacy.QueryRowContext(ctx, `SELECT p.id,p.live,p.has_unpublished_changes,p.last_published_at
 FROM content_homepage h JOIN wagtailcore_page p ON p.id=h.page_ptr_id ORDER BY p.id LIMIT 1`).Scan(&id, &live, &unpublished, &published)
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("读取首页状态: %w", err)
	}
	var publishedUTC any
	if published.Valid && published.String != "" {
		parsed, err := db.ParseUTC(published.String)
		if err != nil {
			return fmt.Errorf("首页发布时间无效: %w", err)
		}
		publishedUTC = db.FormatUTC(parsed)
	}
	return d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		rows, err := legacy.QueryContext(c, `SELECT r.id,r.user_id,r.content,r.created_at FROM wagtailcore_revision r
   JOIN django_content_type t ON t.id=r.content_type_id WHERE t.app_label='content' AND t.model='homepage' AND r.object_id=? ORDER BY r.created_at,r.id`, id)
		if err != nil {
			return fmt.Errorf("读取首页修订: %w", err)
		}
		defer rows.Close()
		var latest string
		for rows.Next() {
			var revisionID int64
			var actor sql.NullInt64
			var content, stamp string
			if err := rows.Scan(&revisionID, &actor, &content, &stamp); err != nil {
				return err
			}
			parsed, err := db.ParseUTC(stamp)
			if err != nil {
				return fmt.Errorf("首页修订 %d 时间无效: %w", revisionID, err)
			}
			if _, err := readHomeRevisionContent(content, HomeDraft{ArticleIDs: []int64{}}); err != nil {
				return fmt.Errorf("首页修订 %d 无效: %w", revisionID, err)
			}
			if _, err := tx.ExecContext(c, `INSERT INTO content_home_revisions(id,home_id,author_id,content,created_at) VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING`, revisionID, id, actor, content, db.FormatUTC(parsed)); err != nil {
				return err
			}
			latest = content
			latestID = sql.NullInt64{Int64: revisionID, Valid: true}
			latestCreated = sql.NullString{String: db.FormatUTC(parsed), Valid: true}
			author = actor
		}
		if err := rows.Err(); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, `INSERT INTO content_home_state(id,live,has_unpublished_changes,last_published_at,latest_revision_id) VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING`, id, live, unpublished, publishedUTC, latestID); err != nil {
			return err
		}
		if latest == "" {
			return nil
		}
		liveDraft := HomeDraft{ArticleIDs: []int64{}}
		pins, err := tx.QueryContext(c, "SELECT article_page_id FROM home_pins ORDER BY sort_order,article_page_id")
		if err != nil {
			return err
		}
		for pins.Next() {
			var article int64
			if err := pins.Scan(&article); err != nil {
				pins.Close()
				return err
			}
			liveDraft.ArticleIDs = append(liveDraft.ArticleIDs, article)
		}
		err = pins.Err()
		pins.Close()
		if err != nil {
			return err
		}
		draft, err := readHomeRevisionContent(latest, liveDraft)
		if err != nil {
			return err
		}
		raw, err := json.Marshal(draft)
		if err != nil {
			return err
		}
		liveRaw, err := json.Marshal(liveDraft)
		if err != nil {
			return err
		}
		_, err = tx.ExecContext(c, `INSERT INTO content_editor_drafts(scope,version,content,live_content,updated_at,author_id) VALUES('home_pins',1,?,?,?,?) ON CONFLICT(scope) DO NOTHING`, string(raw), string(liveRaw), latestCreated.String, author)
		return err
	})
}

func readHomeRevisionContent(content string, fallback HomeDraft) (HomeDraft, error) {
	object, err := revisionObject(content)
	if err != nil {
		return fallback, err
	}
	if raw, ok := revisionField(object, "article_ids"); ok {
		var ids []int64
		if err := json.Unmarshal(raw, &ids); err != nil {
			return fallback, err
		}
		for _, id := range ids {
			if id <= 0 {
				return fallback, fmt.Errorf("置顶文章编号无效")
			}
		}
		return HomeDraft{ArticleIDs: ids}, nil
	}
	raw, present := revisionField(object, "pinned_articles")
	if !present {
		return fallback, nil
	}
	var pins []struct {
		Article   int64 `json:"article"`
		SortOrder int   `json:"sort_order"`
	}
	if err := json.Unmarshal(raw, &pins); err != nil {
		return fallback, err
	}
	sort.SliceStable(pins, func(i, j int) bool { return pins[i].SortOrder < pins[j].SortOrder })
	result := HomeDraft{ArticleIDs: []int64{}}
	for _, pin := range pins {
		if pin.Article <= 0 {
			return fallback, fmt.Errorf("置顶文章编号无效")
		}
		result.ArticleIDs = append(result.ArticleIDs, pin.Article)
	}
	return result, nil
}
