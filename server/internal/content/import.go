package content

import (
	"context"
	"database/sql"
	"fmt"
	"strconv"
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
		if err != nil {
			return fmt.Errorf("1. 导入图片集合 (wagtailcore_collection -> image_collections)：读取失败: %w", err)
		}

		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			// 新库预置集合的编号不等于旧库编号，先在同一事务里释放固定 key。
			// 旧图片仍沿用旧集合 ID；未在旧库出现的内置集合随后补回。
			if _, err := tx.ExecContext(txCtx, `UPDATE image_collections
                SET key = '_import_seed_' || id
                WHERE key IN ('default_cover', 'default_avatar', 'user_avatar', 'contributed', 'team_logo')`); err != nil {
				return fmt.Errorf("释放预置集合 key: %w", err)
			}
			for rows.Next() {
				var id int64
				var name string
				if err := rows.Scan(&id, &name); err != nil {
					return fmt.Errorf("1. 导入图片集合 (wagtailcore_collection -> image_collections)：扫描失败: %w", err)
				}

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
				case "队标":
					key = "team_logo"
				}
				if _, err := tx.ExecContext(txCtx, `
							INSERT INTO image_collections (id, name, key, created_at)
							VALUES (?, ?, ?, ?)
							ON CONFLICT (id) DO UPDATE SET name = excluded.name, key = excluded.key
						`, id, name, key, nowStr); err != nil {
					return fmt.Errorf("1. 导入图片集合 (wagtailcore_collection -> image_collections)：SQL 写入失败: %w", err)
				}
			}
			for _, builtin := range []struct{ name, key string }{
				{"默认封面", "default_cover"}, {"默认头像", "default_avatar"},
				{"用户头像", "user_avatar"}, {"投稿图片", "contributed"}, {"队标", "team_logo"},
			} {
				// 未被旧集合占用的预置行恢复原 key，避免重复导入增殖空集合。
				if _, err := tx.ExecContext(txCtx, `UPDATE image_collections SET key = ?
                    WHERE name = ? AND key LIKE '_import_seed_%'
                    AND NOT EXISTS (SELECT 1 FROM image_collections WHERE key = ?)`, builtin.key, builtin.name, builtin.key); err != nil {
					return err
				}
				if _, err := tx.ExecContext(txCtx, `INSERT INTO image_collections (name, key, created_at)
                    SELECT ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM image_collections WHERE key = ?)`, builtin.name, builtin.key, nowStr, builtin.key); err != nil {
					return err
				}
			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("1. 导入图片集合 (wagtailcore_collection -> image_collections)：写入失败: %w", err)
		}
	}

	// 2. 导入图片 (wagtailimages_image -> images)
	{
		rows, err := legacy.QueryContext(ctx, `SELECT id, collection_id, title, file, width, height, created_at, uploaded_by_user_id, file_size
			FROM wagtailimages_image ORDER BY id ASC`)
		if err != nil {
			return fmt.Errorf("2. 导入图片 (wagtailimages_image -> images)：读取失败: %w", err)
		}

		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for rows.Next() {
				var id int64
				var colID, upID sql.NullInt64
				var title, file, createdAt string
				var width, height int
				var fileSize sql.NullInt64
				if err := rows.Scan(&id, &colID, &title, &file, &width, &height, &createdAt, &upID, &fileSize); err != nil {
					return fmt.Errorf("2. 导入图片 (wagtailimages_image -> images)：扫描失败: %w", err)
				}

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
				if _, err := tx.ExecContext(txCtx, `
							INSERT INTO images (id, collection_id, title, file_name, file_size, width, height, uploader_id, created_at, version)
							VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
							ON CONFLICT (id) DO NOTHING
						`, id, collectionID, title, file, size, width, height, uploaderID, createdUTC); err != nil {
					return fmt.Errorf("2. 导入图片 (wagtailimages_image -> images)：SQL 写入失败: %w", err)
				}
			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("2. 导入图片 (wagtailimages_image -> images)：写入失败: %w", err)
		}
	}

	// 3. 导入文章分类 (content_articlecategory -> article_categories)
	{
		rows, err := legacy.QueryContext(ctx, `SELECT id, name, slug, sort_order, allow_submission FROM content_articlecategory ORDER BY id ASC`)
		if err != nil {
			return fmt.Errorf("3. 导入文章分类 (content_articlecategory -> article_categories)：读取失败: %w", err)
		}

		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for rows.Next() {
				var id int64
				var name, slug string
				var sortOrder, allowSub int
				if err := rows.Scan(&id, &name, &slug, &sortOrder, &allowSub); err != nil {
					return fmt.Errorf("3. 导入文章分类 (content_articlecategory -> article_categories)：扫描失败: %w", err)
				}

				if _, err := tx.ExecContext(txCtx, `
							INSERT INTO article_categories (id, name, slug, description, sort_order, allow_submission, version, created_at, updated_at)
							VALUES (?, ?, ?, '', ?, ?, 1, ?, ?)
							ON CONFLICT (id) DO NOTHING
						`, id, name, slug, sortOrder, allowSub, nowStr, nowStr); err != nil {
					return fmt.Errorf("3. 导入文章分类 (content_articlecategory -> article_categories)：SQL 写入失败: %w", err)
				}
			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("3. 导入文章分类 (content_articlecategory -> article_categories)：写入失败: %w", err)
		}
	}

	// 4. 导入文章页面 (content_articlepage + wagtailcore_page)
	{
		artCols := make(map[string]bool)
		{
			aRows, err := legacy.QueryContext(ctx, `PRAGMA table_info(content_articlepage)`)
			if err != nil {
				return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：读取失败: %w", err)
			}

			defer aRows.Close()
			for aRows.Next() {
				var cid, notnull, pk int
				var name, ctype string
				var dflt any
				if err := aRows.Scan(&cid, &name, &ctype, &notnull, &dflt, &pk); err != nil {
					return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：扫描失败: %w", err)
				}

				artCols[name] = true
			}

			if err := aRows.Err(); err != nil {
				return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：读取列失败: %w", err)
			}
		}
		plainCol := "'' AS body_plain"
		if artCols["body_plain"] {
			plainCol = "a.body_plain"
		}
		wordsCol := "0 AS body_words"
		if artCols["body_words"] {
			wordsCol = "a.body_words"
		}
		minsCol := "1 AS body_minutes"
		if artCols["body_minutes"] {
			minsCol = "a.body_minutes"
		}
		tourCol := "NULL AS tournament_id"
		if artCols["tournament_id"] {
			tourCol = "a.tournament_id"
		}

		rows, err := legacy.QueryContext(ctx, fmt.Sprintf(`
			SELECT p.id, p.slug, p.title, p.live, p.has_unpublished_changes,
			       p.go_live_at, p.expire_at, p.first_published_at, p.last_published_at,
			       p.live_revision_id, p.owner_id, p.seo_title, p.search_description,
			       a.category_id, a.cover_id, a.summary, a.body, %s, %s, %s,
			       a.author_id, a.comments_enabled, %s
			FROM content_articlepage a
			JOIN wagtailcore_page p ON p.id = a.page_ptr_id
			ORDER BY p.id ASC
		`, plainCol, wordsCol, minsCol, tourCol))
		if err != nil {
			return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：读取失败: %w", err)
		}

		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
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
				); err != nil {
					return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：扫描失败: %w", err)
				}

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
				if _, err := tx.ExecContext(txCtx, `
							INSERT INTO pages (id, kind, slug, title, live, has_unpublished_changes,
								go_live_at, expire_at, first_published_at, last_published_at,
								live_revision_id, latest_revision_id, owner_id, seo_title, search_description,
								version, created_at, updated_at)
							VALUES (?, 'article', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
							ON CONFLICT (id) DO NOTHING
						`, pageID, slug, title, live, hasUnpub,
					goLiveUTC, expireUTC, firstPubUTC, lastPubUTC,
					liveRevIDVal, liveRevIDVal, ownerIDVal, seoTitleStr, searchDescStr,
					nowStr, nowStr); err != nil {
					return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：SQL 写入失败: %w", err)
				}

				// 渲染 HTML 与搜索文本
				rawHTML, _, err := markdown.Render(body, siteURL, nil)
				if err != nil {
					return fmt.Errorf("渲染文章 %d: %w", pageID, err)
				}
				anchoredHTML, headings := markdown.AnchorHeadings(rawHTML)
				bodyHTML := rawHTML
				if len(headings) >= 3 {
					bodyHTML = anchoredHTML
				}
				searchText := strings.ToLower(fmt.Sprintf("%s\n%s\n%s", title, summary, bodyPlain))

				// 插入 articles
				if _, err := tx.ExecContext(txCtx, `
							INSERT INTO articles (page_id, category_id, cover_image_id, summary,
								body_md, body_html, body_plain, char_count, reading_time, author_id,
								comments_enabled, related_tournament_id, search_text, renderer_version)
							VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
							ON CONFLICT (page_id) DO NOTHING
						`, pageID, catIDVal, coverIDVal, summary,
					body, bodyHTML, bodyPlain, bodyWords, bodyMinutes, authorIDVal,
					commentsEnabled, tourIDVal, searchText); err != nil {
					return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：SQL 写入失败: %w", err)
				}
			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("4. 导入文章页面 (content_articlepage + wagtailcore_page)：写入失败: %w", err)
		}
	}

	// 5. 导入普通页 (content_standardpage + wagtailcore_page)
	{
		rows, err := legacy.QueryContext(ctx, `
			SELECT p.id, p.slug, p.title, p.live, p.has_unpublished_changes,
			       p.seo_title, p.search_description, p.first_published_at, p.last_published_at, sp.body
			FROM content_standardpage sp
			JOIN wagtailcore_page p ON p.id = sp.page_ptr_id
			ORDER BY p.id ASC
		`)
		if err != nil {
			return fmt.Errorf("导入 content_standardpage：查询失败: %w", err)
		}
		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for rows.Next() {
				var id int64
				var slug, title, body string
				var live, unpub int
				var seoTitle, searchDesc, firstPub, lastPub sql.NullString
				if err := rows.Scan(&id, &slug, &title, &live, &unpub, &seoTitle, &searchDesc, &firstPub, &lastPub, &body); err != nil {
					return fmt.Errorf("扫描普通页: %w", err)
				}
				var firstPubUTC, lastPubUTC any
				if firstPub.Valid && firstPub.String != "" {
					firstPubUTC = parseAndFormatUTC(firstPub.String, now)
				}
				if lastPub.Valid && lastPub.String != "" {
					lastPubUTC = parseAndFormatUTC(lastPub.String, now)
				}
				if _, err := tx.ExecContext(txCtx, `
					INSERT INTO pages (id, kind, slug, title, live, has_unpublished_changes,
						seo_title, search_description, first_published_at, last_published_at, version, created_at, updated_at)
					VALUES (?, 'site_page', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
					ON CONFLICT (id) DO NOTHING
				`, id, slug, title, live, unpub, seoTitle.String, searchDesc.String, firstPubUTC, lastPubUTC, nowStr, nowStr); err != nil {
					return fmt.Errorf("写普通页 %d: %w", id, err)
				}
				html, _, err := markdown.Render(body, siteURL, nil)
				if err != nil {
					return fmt.Errorf("渲染普通页 %d: %w", id, err)
				}
				if _, err := tx.ExecContext(txCtx, `
					INSERT INTO site_pages (page_id, body_md, body_html, body_plain)
					VALUES (?, ?, ?, ?)
					ON CONFLICT (page_id) DO NOTHING
				`, id, body, html, markdown.PlainHTML(html)); err != nil {
					return fmt.Errorf("写普通页正文 %d: %w", id, err)
				}
			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("导入 content_standardpage: %w", err)
		}
	}

	// 6. 导入修订表 (wagtailcore_revision -> page_revisions)
	{
		rows, err := legacy.QueryContext(ctx, `
			SELECT id, object_id, user_id, content, created_at, approved_go_live_at
			FROM wagtailcore_revision
            WHERE content_type_id IN (
                SELECT id FROM django_content_type
                WHERE app_label = 'content' AND model IN ('articlepage', 'standardpage')
            )
			ORDER BY id ASC
		`)
		if err != nil {
			return fmt.Errorf("6. 导入修订表 (wagtailcore_revision -> page_revisions)：读取失败: %w", err)
		}

		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for rows.Next() {
				var id int64
				var objectID string
				var userID sql.NullInt64
				var content, createdAt string
				var appGoLive sql.NullString
				if err := rows.Scan(&id, &objectID, &userID, &content, &createdAt, &appGoLive); err != nil {
					return fmt.Errorf("6. 导入修订表 (wagtailcore_revision -> page_revisions)：扫描失败: %w", err)
				}

				pageID, err := strconv.ParseInt(objectID, 10, 64)
				if err != nil {
					return fmt.Errorf("修订 %d 的页面编号无效: %w", id, err)
				}

				var userVal, appGoLiveVal any
				if userID.Valid {
					userVal = userID.Int64
				}
				if appGoLive.Valid && appGoLive.String != "" {
					appGoLiveVal = parseAndFormatUTC(appGoLive.String, now)
				}
				createdUTC := parseAndFormatUTC(createdAt, now)
				if _, err := tx.ExecContext(txCtx, `
								INSERT INTO page_revisions (id, page_id, author_id, content, created_at, approved_go_live_at)
								VALUES (?, ?, ?, ?, ?, ?)
								ON CONFLICT (id) DO NOTHING
							`, id, pageID, userVal, content, createdUTC, appGoLiveVal); err != nil {
					return fmt.Errorf("6. 导入修订表 (wagtailcore_revision -> page_revisions)：SQL 写入失败: %w", err)
				}

			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("6. 导入修订表 (wagtailcore_revision -> page_revisions)：写入失败: %w", err)
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
		if err != nil {
			return fmt.Errorf("7. 导入首页置顶 (content_homepagepinnedarticle -> home_pins)：读取失败: %w", err)
		}

		defer rows.Close()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			for rows.Next() {
				var articleID int64
				var sortOrder int
				if err := rows.Scan(&articleID, &sortOrder); err != nil {
					return fmt.Errorf("7. 导入首页置顶 (content_homepagepinnedarticle -> home_pins)：扫描失败: %w", err)
				}

				if _, err := tx.ExecContext(txCtx, `
							INSERT INTO home_pins (article_page_id, sort_order)
							VALUES (?, ?)
							ON CONFLICT (article_page_id) DO NOTHING
						`, articleID, sortOrder); err != nil {
					return fmt.Errorf("7. 导入首页置顶 (content_homepagepinnedarticle -> home_pins)：SQL 写入失败: %w", err)
				}
			}
			return rows.Err()
		}); err != nil {
			return fmt.Errorf("7. 导入首页置顶 (content_homepagepinnedarticle -> home_pins)：写入失败: %w", err)
		}
	}

	// 8. 导入评论 (comments_comment -> comments)
	{
		var hasCommentsTable bool
		if err := legacy.QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='comments_comment'`).Scan(&hasCommentsTable); err != nil {
			return fmt.Errorf("检查旧表 comments_comment: %w", err)
		}
		if hasCommentsTable {
			cRows, err := legacy.QueryContext(ctx, `
				SELECT id, page_id, author_id, parent_id, reply_to_user_id, body,
				       is_pinned, is_hidden, is_deleted, like_count, created_at, edited_at
				FROM comments_comment ORDER BY COALESCE(parent_id, 0) ASC, id ASC
			`)
			if err != nil {
				return fmt.Errorf("8. 导入评论 (comments_comment -> comments)：读取失败: %w", err)
			}
			{
				defer cRows.Close()
				if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
					for cRows.Next() {
						var id, pageID int64
						var authorID, parentID, replyTo sql.NullInt64
						var body, createdAt string
						var editedAt sql.NullString
						var isPinned, isHidden, isDeleted, likeCount int
						if err := cRows.Scan(
							&id, &pageID, &authorID, &parentID, &replyTo, &body,
							&isPinned, &isHidden, &isDeleted, &likeCount, &createdAt, &editedAt,
						); err != nil {
							return fmt.Errorf("8. 导入评论 (comments_comment -> comments)：扫描失败: %w", err)
						}

						var authorVal, parentVal, replyToVal any
						if authorID.Valid {
							var n int
							if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM users WHERE id = ?`, authorID.Int64).Scan(&n); err != nil {
								return fmt.Errorf("导入评论：检查引用失败: %w", err)
							}
							if n > 0 {
								authorVal = authorID.Int64
							}
						}
						if parentID.Valid {
							var n int
							if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM comments WHERE id = ?`, parentID.Int64).Scan(&n); err != nil {
								return fmt.Errorf("导入评论：检查引用失败: %w", err)
							}
							if n > 0 {
								parentVal = parentID.Int64
							}
						}
						if replyTo.Valid {
							var n int
							if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM users WHERE id = ?`, replyTo.Int64).Scan(&n); err != nil {
								return fmt.Errorf("导入评论：检查引用失败: %w", err)
							}
							if n > 0 {
								replyToVal = replyTo.Int64
							}
						}
						createdUTC := parseAndFormatUTC(createdAt, now)
						updatedUTC := createdUTC
						if editedAt.Valid && editedAt.String != "" {
							updatedUTC = parseAndFormatUTC(editedAt.String, now)
						}
						if _, err := tx.ExecContext(txCtx, `
								INSERT INTO comments (
									id, article_id, user_id, parent_id, reply_to_user_id,
									content, is_pinned, is_hidden, is_deleted, like_count,
									version, created_at, updated_at
								) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
								ON CONFLICT (id) DO NOTHING
							`, id, pageID, authorVal, parentVal, replyToVal,
							body, isPinned, isHidden, isDeleted, likeCount,
							createdUTC, updatedUTC); err != nil {
							return fmt.Errorf("8. 导入评论 (comments_comment -> comments)：SQL 写入失败: %w", err)
						}
					}
					return cRows.Err()
				}); err != nil {
					return fmt.Errorf("8. 导入评论 (comments_comment -> comments)：写入失败: %w", err)
				}
			}
		}
	}

	// 9. 导入评论点赞 (comments_commentlike -> comment_likes)
	{
		var hasLikesTable bool
		if err := legacy.QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='comments_commentlike'`).Scan(&hasLikesTable); err != nil {
			return fmt.Errorf("检查旧表 comments_commentlike: %w", err)
		}
		if hasLikesTable {
			lRows, err := legacy.QueryContext(ctx, `
				SELECT comment_id, user_id, created_at
				FROM comments_commentlike
			`)
			if err != nil {
				return fmt.Errorf("9. 导入评论点赞 (comments_commentlike -> comment_likes)：读取失败: %w", err)
			}
			{
				defer lRows.Close()
				if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
					for lRows.Next() {
						var commentID, userID int64
						var createdAt string
						if err := lRows.Scan(&commentID, &userID, &createdAt); err != nil {
							return fmt.Errorf("9. 导入评论点赞 (comments_commentlike -> comment_likes)：扫描失败: %w", err)
						}

						var cExists, uExists int
						if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM comments WHERE id = ?`, commentID).Scan(&cExists); err != nil {
							return fmt.Errorf("导入点赞：检查引用失败: %w", err)
						}
						if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM users WHERE id = ?`, userID).Scan(&uExists); err != nil {
							return fmt.Errorf("导入点赞：检查引用失败: %w", err)
						}
						if cExists > 0 && uExists > 0 {
							createdUTC := parseAndFormatUTC(createdAt, now)
							if _, err := tx.ExecContext(txCtx, `
									INSERT INTO comment_likes (comment_id, user_id, created_at)
									VALUES (?, ?, ?)
									ON CONFLICT DO NOTHING
								`, commentID, userID, createdUTC); err != nil {
								return fmt.Errorf("9. 导入评论点赞 (comments_commentlike -> comment_likes)：SQL 写入失败: %w", err)
							}
						}
					}
					return lRows.Err()
				}); err != nil {
					return fmt.Errorf("9. 导入评论点赞 (comments_commentlike -> comment_likes)：写入失败: %w", err)
				}
			}
		}
	}

	return nil
}
