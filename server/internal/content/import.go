package content

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

func parseAndFormatUTC(s string, fallback time.Time) string {
	if s == "" {
		return db.FormatUTC(fallback)
	}
	t, err := db.ParseUTC(s)
	if err != nil {
		return db.FormatUTC(fallback)
	}
	return db.FormatUTC(t)
}

// ImportLegacyContent 从现行 Django/Wagtail SQLite 库导入内容与媒体数据（12 号文档 7、8.1）。
func ImportLegacyContent(ctx context.Context, d *db.DB, legacy *sql.DB, siteURL string) error {
	now := time.Now().UTC()
	nowStr := db.FormatUTC(now)
	siteURL = strings.TrimRight(siteURL, "/")

	// 1. 导入图片集合 (wagtailcore_collection -> image_collections)
	{
		rows, err := legacy.QueryContext(ctx, `SELECT id, name FROM wagtailcore_collection ORDER BY id ASC`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var id int64
					var name string
					if err := rows.Scan(&id, &name); err == nil {
						key := fmt.Sprintf("collection_%d", id)
						switch name {
						case "默认封面":
							key = "default_cover"
						case "默认头像":
							key = "default_avatar"
						case "用户头像":
							key = "user_avatar"
						case "投稿图片":
							key = "contributed"
						}
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO image_collections (id, name, key, created_at)
							VALUES (?, ?, ?, ?)
							ON CONFLICT (id) DO UPDATE SET name = excluded.name, key = excluded.key
						`, id, name, key, nowStr)
					}
				}
				return nil
			})
		}
	}

	// 2. 导入图片 (wagtailimages_image -> images)
	{
		rows, err := legacy.QueryContext(ctx, `SELECT id, collection_id, title, file, width, height, created_at, uploaded_by_user_id, file_size
			FROM wagtailimages_image ORDER BY id ASC`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var id int64
					var colID, upID sql.NullInt64
					var title, file, createdAt string
					var width, height int
					var fileSize sql.NullInt64
					if err := rows.Scan(&id, &colID, &title, &file, &width, &height, &createdAt, &upID, &fileSize); err == nil {
						createdUTC := parseAndFormatUTC(createdAt, now)
						size := int64(0)
						if fileSize.Valid {
							size = fileSize.Int64
						}
						var collectionID, uploaderID any
						if colID.Valid {
							collectionID = colID.Int64
						}
						if upID.Valid {
							uploaderID = upID.Int64
						}
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO images (id, collection_id, title, file_name, file_size, width, height, uploader_id, created_at, version)
							VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
							ON CONFLICT (id) DO NOTHING
						`, id, collectionID, title, file, size, width, height, uploaderID, createdUTC)
					}
				}
				return nil
			})
		}
	}

	// 3. 导入文章分类 (content_articlecategory -> article_categories)
	{
		rows, err := legacy.QueryContext(ctx, `SELECT id, name, slug, sort_order, allow_submission FROM content_articlecategory ORDER BY id ASC`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var id int64
					var name, slug string
					var sortOrder, allowSub int
					if err := rows.Scan(&id, &name, &slug, &sortOrder, &allowSub); err == nil {
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO article_categories (id, name, slug, description, sort_order, allow_submission, version, created_at, updated_at)
							VALUES (?, ?, ?, '', ?, ?, 1, ?, ?)
							ON CONFLICT (id) DO NOTHING
						`, id, name, slug, sortOrder, allowSub, nowStr, nowStr)
					}
				}
				return nil
			})
		}
	}

	// 4. 导入文章页面 (content_articlepage + wagtailcore_page)
	{
		rows, err := legacy.QueryContext(ctx, `
			SELECT p.id, p.slug, p.title, p.live, p.has_unpublished_changes,
			       p.go_live_at, p.expire_at, p.first_published_at, p.last_published_at,
			       p.live_revision_id, p.owner_id, p.seo_title, p.search_description,
			       a.category_id, a.cover_id, a.summary, a.body, a.body_plain, a.body_words, a.body_minutes,
			       a.author_id, a.comments_enabled, a.tournament_id
			FROM content_articlepage a
			JOIN wagtailcore_page p ON p.id = a.page_ptr_id
			ORDER BY p.id ASC
		`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var pageID int64
					var slug, title, summary, body, bodyPlain string
					var live, hasUnpub, commentsEnabled, bodyWords, bodyMinutes int
					var goLive, expire, firstPub, lastPub, seoTitle, searchDesc sql.NullString
					var liveRevID, ownerID, catID, coverID, authorID, tourID sql.NullInt64

					if err := rows.Scan(
						&pageID, &slug, &title, &live, &hasUnpub,
						&goLive, &expire, &firstPub, &lastPub,
						&liveRevID, &ownerID, &seoTitle, &searchDesc,
						&catID, &coverID, &summary, &body, &bodyPlain, &bodyWords, &bodyMinutes,
						&authorID, &commentsEnabled, &tourID,
					); err == nil {
						var goLiveUTC, expireUTC, firstPubUTC, lastPubUTC any
						if goLive.Valid && goLive.String != "" {
							goLiveUTC = parseAndFormatUTC(goLive.String, now)
						}
						if expire.Valid && expire.String != "" {
							expireUTC = parseAndFormatUTC(expire.String, now)
						}
						if firstPub.Valid && firstPub.String != "" {
							firstPubUTC = parseAndFormatUTC(firstPub.String, now)
						}
						if lastPub.Valid && lastPub.String != "" {
							lastPubUTC = parseAndFormatUTC(lastPub.String, now)
						}

						var ownerIDVal, liveRevIDVal, catIDVal, coverIDVal, authorIDVal, tourIDVal any
						if ownerID.Valid {
							ownerIDVal = ownerID.Int64
						}
						if liveRevID.Valid {
							liveRevIDVal = liveRevID.Int64
						}
						if catID.Valid {
							catIDVal = catID.Int64
						}
						if coverID.Valid {
							coverIDVal = coverID.Int64
						}
						if authorID.Valid {
							authorIDVal = authorID.Int64
						}
						if tourID.Valid {
							tourIDVal = tourID.Int64
						}

						seoTitleStr := ""
						if seoTitle.Valid {
							seoTitleStr = seoTitle.String
						}
						searchDescStr := ""
						if searchDesc.Valid {
							searchDescStr = searchDesc.String
						}

						// 插入 pages
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO pages (id, kind, slug, title, live, has_unpublished_changes,
								go_live_at, expire_at, first_published_at, last_published_at,
								live_revision_id, latest_revision_id, owner_id, seo_title, search_description,
								version, created_at, updated_at)
							VALUES (?, 'article', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
							ON CONFLICT (id) DO NOTHING
						`, pageID, slug, title, live, hasUnpub,
							goLiveUTC, expireUTC, firstPubUTC, lastPubUTC,
							liveRevIDVal, liveRevIDVal, ownerIDVal, seoTitleStr, searchDescStr,
							nowStr, nowStr)

						// 渲染 HTML 与搜索文本
						rawHTML, _, _ := markdown.Render(body, siteURL, nil)
						anchoredHTML, headings := markdown.AnchorHeadings(rawHTML)
						bodyHTML := rawHTML
						if len(headings) >= 3 {
							bodyHTML = anchoredHTML
						}
						searchText := strings.ToLower(fmt.Sprintf("%s\n%s\n%s", title, summary, bodyPlain))

						// 插入 articles
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO articles (page_id, category_id, cover_image_id, summary,
								body_md, body_html, body_plain, char_count, reading_time, author_id,
								comments_enabled, related_tournament_id, search_text, renderer_version)
							VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
							ON CONFLICT (page_id) DO NOTHING
						`, pageID, catIDVal, coverIDVal, summary,
							body, bodyHTML, bodyPlain, bodyWords, bodyMinutes, authorIDVal,
							commentsEnabled, tourIDVal, searchText)
					}
				}
				return nil
			})
		}
	}

	// 5. 导入单页 (content_sitepage + wagtailcore_page)
	{
		rows, err := legacy.QueryContext(ctx, `
			SELECT p.id, p.slug, p.title, p.live, p.has_unpublished_changes,
			       sp.body, sp.body_plain
			FROM content_sitepage sp
			JOIN wagtailcore_page p ON p.id = sp.page_ptr_id
			ORDER BY p.id ASC
		`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var id int64
					var slug, title, body, bodyPlain string
					var live, unpub int
					if err := rows.Scan(&id, &slug, &title, &live, &unpub, &body, &bodyPlain); err == nil {
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO pages (id, kind, slug, title, live, has_unpublished_changes, version, created_at, updated_at)
							VALUES (?, 'site_page', ?, ?, ?, ?, 1, ?, ?)
							ON CONFLICT (id) DO NOTHING
						`, id, slug, title, live, unpub, nowStr, nowStr)

						html, _, _ := markdown.Render(body, siteURL, nil)
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO site_pages (page_id, body_md, body_html, body_plain)
							VALUES (?, ?, ?, ?)
							ON CONFLICT (page_id) DO NOTHING
						`, id, body, html, bodyPlain)
					}
				}
				return nil
			})
		}
	}

	// 6. 导入修订表 (wagtailcore_revision -> page_revisions)
	{
		rows, err := legacy.QueryContext(ctx, `
			SELECT id, object_id, user_id, content, created_at, approved_go_live_at
			FROM wagtailcore_revision
			ORDER BY id ASC
		`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var id int64
					var objectID string
					var userID sql.NullInt64
					var content, createdAt string
					var appGoLive sql.NullString
					if err := rows.Scan(&id, &objectID, &userID, &content, &createdAt, &appGoLive); err == nil {
						var pageID int64
						if _, err := fmt.Sscanf(objectID, "%d", &pageID); err == nil {
							var userVal, appGoLiveVal any
							if userID.Valid {
								userVal = userID.Int64
							}
							if appGoLive.Valid && appGoLive.String != "" {
								appGoLiveVal = parseAndFormatUTC(appGoLive.String, now)
							}
							createdUTC := parseAndFormatUTC(createdAt, now)
							_, _ = tx.ExecContext(txCtx, `
								INSERT INTO page_revisions (id, page_id, author_id, content, created_at, approved_go_live_at)
								VALUES (?, ?, ?, ?, ?, ?)
								ON CONFLICT (id) DO NOTHING
							`, id, pageID, userVal, content, createdUTC, appGoLiveVal)
						}
					}
				}
				return nil
			})
		}
	}

	// 7. 导入首页置顶 (content_homepagepinnedarticle -> home_pins)
	{
		rows, err := legacy.QueryContext(ctx, `
			SELECT article_id, sort_order
			FROM content_homepagepinnedarticle
			ORDER BY sort_order ASC
			LIMIT 3
		`)
		if err == nil {
			defer rows.Close()
			_ = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
				for rows.Next() {
					var articleID int64
					var sortOrder int
					if err := rows.Scan(&articleID, &sortOrder); err == nil {
						_, _ = tx.ExecContext(txCtx, `
							INSERT INTO home_pins (article_page_id, sort_order)
							VALUES (?, ?)
							ON CONFLICT (article_page_id) DO NOTHING
						`, articleID, sortOrder)
					}
				}
				return nil
			})
		}
	}

	return nil
}
