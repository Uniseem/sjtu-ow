package content

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/notify"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Store 提供内容域数据库读写。
type Store struct {
	d *db.DB
}

// NewStore 创建内容域存储。
func NewStore(d *db.DB) *Store {
	return &Store{d: d}
}

// ListCategories 列出所有分类（含文章数统计，按 sort_order 升序）。
func (s *Store) ListCategories(ctx context.Context) ([]*Category, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `
		SELECT c.id, c.name, c.slug, c.description, c.sort_order, c.allow_submission, c.version, c.created_at, c.updated_at,
		       COUNT(a.page_id) as article_count
		FROM article_categories c
		LEFT JOIN articles a ON a.category_id = c.id
		GROUP BY c.id
		ORDER BY c.sort_order ASC, c.id ASC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var list []*Category
	for rows.Next() {
		var c Category
		var created, updated string
		var allowSub int
		if err := rows.Scan(&c.ID, &c.Name, &c.Slug, &c.Description, &c.SortOrder, &allowSub, &c.Version, &created, &updated, &c.ArticleCount); err != nil {
			return nil, err
		}
		c.AllowSubmission = allowSub == 1
		c.CreatedAt, _ = db.ParseUTC(created)
		c.UpdatedAt, _ = db.ParseUTC(updated)
		list = append(list, &c)
	}
	return list, nil
}

// GetCategoryByID 按 ID 读分类。
func (s *Store) GetCategoryByID(ctx context.Context, id int64) (*Category, error) {
	var c Category
	var created, updated string
	var allowSub int
	err := s.d.ReadPool().QueryRowContext(ctx, `
		SELECT id, name, slug, description, sort_order, allow_submission, version, created_at, updated_at
		FROM article_categories WHERE id = ?
	`, id).Scan(&c.ID, &c.Name, &c.Slug, &c.Description, &c.SortOrder, &allowSub, &c.Version, &created, &updated)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	c.AllowSubmission = allowSub == 1
	c.CreatedAt, _ = db.ParseUTC(created)
	c.UpdatedAt, _ = db.ParseUTC(updated)
	return &c, nil
}

// GetCategoryBySlug 按 slug 读分类。
func (s *Store) GetCategoryBySlug(ctx context.Context, slug string) (*Category, error) {
	var c Category
	var created, updated string
	var allowSub int
	err := s.d.ReadPool().QueryRowContext(ctx, `
		SELECT id, name, slug, description, sort_order, allow_submission, version, created_at, updated_at
		FROM article_categories WHERE slug = ?
	`, slug).Scan(&c.ID, &c.Name, &c.Slug, &c.Description, &c.SortOrder, &allowSub, &c.Version, &created, &updated)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	c.AllowSubmission = allowSub == 1
	c.CreatedAt, _ = db.ParseUTC(created)
	c.UpdatedAt, _ = db.ParseUTC(updated)
	return &c, nil
}

// CreateCategory 创建分类。
func (s *Store) CreateCategory(ctx context.Context, c *Category) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	allowSub := 0
	if c.AllowSubmission {
		allowSub = 1
	}
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			INSERT INTO article_categories (name, slug, description, sort_order, allow_submission, version, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, 1, ?, ?)
		`, c.Name, c.Slug, c.Description, c.SortOrder, allowSub, now, now)
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		c.ID = id
		c.Version = 1
		c.CreatedAt, _ = db.ParseUTC(now)
		c.UpdatedAt = c.CreatedAt
		return nil
	})
}

// UpdateCategory 更新分类。
func (s *Store) UpdateCategory(ctx context.Context, c *Category) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	allowSub := 0
	if c.AllowSubmission {
		allowSub = 1
	}
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			UPDATE article_categories
			SET name = ?, slug = ?, description = ?, sort_order = ?, allow_submission = ?, version = version + 1, updated_at = ?
			WHERE id = ? AND version = ?
		`, c.Name, c.Slug, c.Description, c.SortOrder, allowSub, now, c.ID, c.Version)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.NewErr(409, "conflict", "分类已被他人修改")
		}
		c.Version++
		c.UpdatedAt, _ = db.ParseUTC(now)
		return nil
	})
}

// DeleteCategory 删除分类（若仍有文章使用则拒绝）。
func (s *Store) DeleteCategory(ctx context.Context, id int64) error {
	var count int
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM articles WHERE category_id = ?`, id).Scan(&count)
	if err != nil {
		return err
	}
	if count > 0 {
		return api.Invalid(fmt.Sprintf("该分类下有 %d 篇文章，无法删除", count))
	}

	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `DELETE FROM article_categories WHERE id = ?`, id)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.NotFound("分类不存在")
		}
		return nil
	})
}

const pageColumns = `p.id, p.kind, p.slug, p.title, p.live, p.has_unpublished_changes,
	p.go_live_at, p.expire_at, p.first_published_at, p.last_published_at,
	p.live_revision_id, p.latest_revision_id, p.owner_id, p.seo_title, p.search_description,
	p.version, p.created_at, p.updated_at`

const articleColumns = pageColumns + `,
	a.category_id, IFNULL(c.name, '') as category_name,
	a.cover_image_id, a.summary, a.body_md, a.body_html, a.body_plain,
	a.char_count, a.reading_time, a.author_id, IFNULL(u.nickname, '') as author_name,
	a.comments_enabled, a.related_tournament_id, a.search_text, a.renderer_version`

func scanArticle(row interface{ Scan(...any) error }) (*Article, error) {
	var a Article
	var live, unpub, comments, rendVer int
	var goLive, expire, firstPub, lastPub, created, updated sql.NullString
	var catID, coverID, authorID, tourID sql.NullInt64

	err := row.Scan(
		&a.ID, &a.Kind, &a.Slug, &a.Title, &live, &unpub,
		&goLive, &expire, &firstPub, &lastPub,
		&a.LiveRevisionID, &a.LatestRevisionID, &a.OwnerID, &a.SeoTitle, &a.SearchDescription,
		&a.Version, &created, &updated,
		&catID, &a.CategoryName,
		&coverID, &a.Summary, &a.BodyMD, &a.BodyHTML, &a.BodyPlain,
		&a.CharCount, &a.ReadingTime, &authorID, &a.AuthorName,
		&comments, &tourID, &a.SearchText, &rendVer,
	)
	if err != nil {
		return nil, err
	}

	a.Live = live == 1
	a.HasUnpublishedChanges = unpub == 1
	a.CommentsEnabled = comments == 1
	a.RendererVersion = rendVer

	if goLive.Valid && goLive.String != "" {
		if t, err := db.ParseUTC(goLive.String); err == nil {
			a.GoLiveAt = &t
		}
	}
	if expire.Valid && expire.String != "" {
		if t, err := db.ParseUTC(expire.String); err == nil {
			a.ExpireAt = &t
		}
	}
	if firstPub.Valid && firstPub.String != "" {
		if t, err := db.ParseUTC(firstPub.String); err == nil {
			a.FirstPublishedAt = &t
		}
	}
	if lastPub.Valid && lastPub.String != "" {
		if t, err := db.ParseUTC(lastPub.String); err == nil {
			a.LastPublishedAt = &t
		}
	}
	if created.Valid && created.String != "" {
		a.CreatedAt, _ = db.ParseUTC(created.String)
	}
	if updated.Valid && updated.String != "" {
		a.UpdatedAt, _ = db.ParseUTC(updated.String)
	}
	if catID.Valid {
		a.CategoryID = &catID.Int64
	}
	if coverID.Valid {
		a.CoverImageID = &coverID.Int64
	}
	if authorID.Valid {
		a.AuthorID = &authorID.Int64
	}
	if tourID.Valid {
		a.RelatedTournamentID = &tourID.Int64
	}

	return &a, nil
}

// GetArticleByID 读文章完整数据。
func (s *Store) GetArticleByID(ctx context.Context, pageID int64) (*Article, error) {
	query := `
		SELECT ` + articleColumns + `
		FROM pages p
		JOIN articles a ON a.page_id = p.id
		LEFT JOIN article_categories c ON c.id = a.category_id
		LEFT JOIN users u ON u.id = a.author_id
		WHERE p.id = ? AND p.kind = 'article'
	`
	a, err := scanArticle(s.d.ReadPool().QueryRowContext(ctx, query, pageID))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return a, nil
}

// GetArticleBySlug 按 slug 读文章完整数据。
func (s *Store) GetArticleBySlug(ctx context.Context, slug string) (*Article, error) {
	query := `
		SELECT ` + articleColumns + `
		FROM pages p
		JOIN articles a ON a.page_id = p.id
		LEFT JOIN article_categories c ON c.id = a.category_id
		LEFT JOIN users u ON u.id = a.author_id
		WHERE p.slug = ? AND p.kind = 'article'
	`
	a, err := scanArticle(s.d.ReadPool().QueryRowContext(ctx, query, slug))
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return a, nil
}

// ListArticles 列出文章（支持分类筛选、live 状态筛选、分页）。
func (s *Store) ListArticles(ctx context.Context, categorySlug string, onlyLive bool, limit, offset int) ([]*Article, int, error) {
	where := "WHERE p.kind = 'article'"
	var args []any

	if onlyLive {
		where += " AND p.live = 1"
	}
	if categorySlug != "" {
		where += " AND c.slug = ?"
		args = append(args, categorySlug)
	}

	// 查总数
	countQuery := `
		SELECT COUNT(*)
		FROM pages p
		JOIN articles a ON a.page_id = p.id
		LEFT JOIN article_categories c ON c.id = a.category_id
		` + where
	var total int
	if err := s.d.ReadPool().QueryRowContext(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	query := `
		SELECT ` + articleColumns + `
		FROM pages p
		JOIN articles a ON a.page_id = p.id
		LEFT JOIN article_categories c ON c.id = a.category_id
		LEFT JOIN users u ON u.id = a.author_id
		` + where + `
		ORDER BY p.first_published_at DESC, p.id DESC
		LIMIT ? OFFSET ?
	`
	argsWithLimit := append(args, limit, offset)
	rows, err := s.d.ReadPool().QueryContext(ctx, query, argsWithLimit...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var list []*Article
	for rows.Next() {
		a, err := scanArticle(rows)
		if err != nil {
			return nil, 0, err
		}
		list = append(list, a)
	}
	return list, total, nil
}

// CreateArticleDraft 创建文章初始草稿（规则 46）。
func (s *Store) CreateArticleDraft(ctx context.Context, p *Page, a *Article, revContent string, authorID int64) (*Article, int64, error) {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	var pageID, revID int64

	err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			INSERT INTO pages (kind, slug, title, live, has_unpublished_changes, owner_id, seo_title, search_description, version, created_at, updated_at)
			VALUES ('article', ?, ?, 0, 1, ?, ?, ?, 1, ?, ?)
		`, p.Slug, p.Title, p.OwnerID, p.SeoTitle, p.SearchDescription, now, now)
		if err != nil {
			return err
		}
		pageID, err = res.LastInsertId()
		if err != nil {
			return err
		}

		comments := 1
		if !a.CommentsEnabled {
			comments = 0
		}
		_, err = tx.ExecContext(txCtx, `
			INSERT INTO articles (page_id, category_id, cover_image_id, summary, body_md, body_html, body_plain,
				char_count, reading_time, author_id, comments_enabled, related_tournament_id, search_text, renderer_version)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
		`, pageID, a.CategoryID, a.CoverImageID, a.Summary, a.BodyMD, a.BodyHTML, a.BodyPlain,
			a.CharCount, a.ReadingTime, a.AuthorID, comments, a.RelatedTournamentID, a.SearchText)
		if err != nil {
			return err
		}

		// 创建初始修订
		revRes, err := tx.ExecContext(txCtx, `
			INSERT INTO page_revisions (page_id, author_id, content, created_at)
			VALUES (?, ?, ?, ?)
		`, pageID, authorID, revContent, now)
		if err != nil {
			return err
		}
		revID, err = revRes.LastInsertId()
		if err != nil {
			return err
		}

		// 更新 page 的 latest_revision_id
		_, err = tx.ExecContext(txCtx, `UPDATE pages SET latest_revision_id = ? WHERE id = ?`, revID, pageID)
		return err
	})
	if err != nil {
		return nil, 0, err
	}

	p.ID = pageID
	p.Version = 1
	p.LatestRevisionID = &revID
	p.CreatedAt, _ = db.ParseUTC(now)
	p.UpdatedAt = p.CreatedAt
	a.Page = *p
	return a, revID, nil
}

// SaveArticleDraft 保存文章草稿（支持复用/覆盖或新增修订）。
func (s *Store) SaveArticleDraft(ctx context.Context, pageID int64, baseVersion int64, revContent string, authorID int64, overwriteRevID int64) (int64, int64, error) {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	var newRevID int64
	var newVer int64

	err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		// 检查版本号
		var curVer int64
		err := tx.QueryRowContext(txCtx, `SELECT version FROM pages WHERE id = ? AND kind = 'article'`, pageID).Scan(&curVer)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return api.NotFound("文章不存在")
			}
			return err
		}
		if curVer != baseVersion {
			return api.NewErr(409, "stale", "另一个人刚改过，已换成最新内容")
		}
		newVer = curVer + 1

		if overwriteRevID > 0 {
			// 复用当前修订
			_, err = tx.ExecContext(txCtx, `
				UPDATE page_revisions
				SET content = ?, created_at = ?
				WHERE id = ?
			`, revContent, now, overwriteRevID)
			if err != nil {
				return err
			}
			newRevID = overwriteRevID
		} else {
			// 新增修订
			res, err := tx.ExecContext(txCtx, `
				INSERT INTO page_revisions (page_id, author_id, content, created_at)
				VALUES (?, ?, ?, ?)
			`, pageID, authorID, revContent, now)
			if err != nil {
				return err
			}
			newRevID, err = res.LastInsertId()
			if err != nil {
				return err
			}
		}

		// 更新 page 行的版本与 latest_revision_id
		_, err = tx.ExecContext(txCtx, `
			UPDATE pages
			SET version = version + 1, latest_revision_id = ?, has_unpublished_changes = 1, updated_at = ?
			WHERE id = ?
		`, newRevID, now, pageID)
		return err
	})
	if err != nil {
		return 0, 0, err
	}
	return newVer, newRevID, nil
}

// PublishArticle 将草稿正式发布到文章行。
func (s *Store) PublishArticle(ctx context.Context, pageID int64, p *Page, a *Article, revID int64) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	comments := 1
	if !a.CommentsEnabled {
		comments = 0
	}

	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		var firstPub sql.NullString
		_ = tx.QueryRowContext(txCtx, `SELECT first_published_at FROM pages WHERE id = ?`, pageID).Scan(&firstPub)
		firstPubStr := now
		if firstPub.Valid && firstPub.String != "" {
			firstPubStr = firstPub.String
		}

		var goLiveStr, expireStr any
		if p.GoLiveAt != nil {
			goLiveStr = p.GoLiveAt.UTC().Format(time.RFC3339Nano)
		}
		if p.ExpireAt != nil {
			expireStr = p.ExpireAt.UTC().Format(time.RFC3339Nano)
		}

		liveInt := 0
		var liveRev any
		if p.Live {
			liveInt = 1
			liveRev = revID
		}

		// 更新 pages
		_, err := tx.ExecContext(txCtx, `
			UPDATE pages
			SET title = ?, slug = ?, live = ?, has_unpublished_changes = 0,
			    go_live_at = ?, expire_at = ?, first_published_at = ?, last_published_at = ?,
			    live_revision_id = ?, latest_revision_id = ?,
			    seo_title = ?, search_description = ?, version = version + 1, updated_at = ?
			WHERE id = ?
		`, p.Title, p.Slug, liveInt, goLiveStr, expireStr, firstPubStr, now, liveRev, revID, p.SeoTitle, p.SearchDescription, now, pageID)
		if err != nil {
			return err
		}

		// 更新 articles
		_, err = tx.ExecContext(txCtx, `
			UPDATE articles
			SET category_id = ?, cover_image_id = ?, summary = ?,
			    body_md = ?, body_html = ?, body_plain = ?,
			    char_count = ?, reading_time = ?, author_id = ?,
			    comments_enabled = ?, related_tournament_id = ?, search_text = ?, renderer_version = 1
			WHERE page_id = ?
		`, a.CategoryID, a.CoverImageID, a.Summary, a.BodyMD, a.BodyHTML, a.BodyPlain,
			a.CharCount, a.ReadingTime, a.AuthorID, comments, a.RelatedTournamentID, a.SearchText, pageID)
		if err != nil || !p.Live {
			return err
		}
		// 安排过「上线时通知」的文章，这一次发布让它上线了（规则 55、74）
		_, err = notify.SendWaiting(txCtx, tx, notify.KindArticle, pageID, time.Now().UTC())
		return err
	})
}

// UnpublishArticle 撤下文章。
func (s *Store) UnpublishArticle(ctx context.Context, pageID int64) error {
	now := time.Now().UTC().Format(time.RFC3339Nano)
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `
			UPDATE pages
			SET live = 0, has_unpublished_changes = 1, version = version + 1, updated_at = ?
			WHERE id = ? AND kind = 'article'
		`, now, pageID)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.NotFound("文章不存在")
		}
		return nil
	})
}

// DeleteArticle 删除文章。
func (s *Store) DeleteArticle(ctx context.Context, pageID int64) error {
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `DELETE FROM pages WHERE id = ? AND kind = 'article'`, pageID)
		if err != nil {
			return err
		}
		affected, _ := res.RowsAffected()
		if affected == 0 {
			return api.NotFound("文章不存在")
		}
		return nil
	})
}

// GetLatestRevision 获取页面最新修订。
func (s *Store) GetLatestRevision(ctx context.Context, pageID int64) (*PageRevision, error) {
	var rev PageRevision
	var authID sql.NullInt64
	var appGoLive sql.NullString
	var created string

	err := s.d.ReadPool().QueryRowContext(ctx, `
		SELECT id, page_id, author_id, content, created_at, approved_go_live_at
		FROM page_revisions
		WHERE page_id = ?
		ORDER BY id DESC LIMIT 1
	`, pageID).Scan(&rev.ID, &rev.PageID, &authID, &rev.Content, &created, &appGoLive)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	if authID.Valid {
		rev.AuthorID = &authID.Int64
	}
	if appGoLive.Valid && appGoLive.String != "" {
		if t, err := db.ParseUTC(appGoLive.String); err == nil {
			rev.ApprovedGoLiveAt = &t
		}
	}
	rev.CreatedAt, _ = db.ParseUTC(created)
	return &rev, nil
}

// GetSitePageBySlug 按 slug 读普通单页。
func (s *Store) GetSitePageBySlug(ctx context.Context, slug string) (*SitePage, error) {
	query := `
		SELECT ` + pageColumns + `, sp.body_md, sp.body_html, sp.body_plain
		FROM pages p
		JOIN site_pages sp ON sp.page_id = p.id
		WHERE p.slug = ? AND p.kind = 'site_page'
	`
	var sp SitePage
	var live, unpub int
	var goLive, expire, firstPub, lastPub, created, updated sql.NullString

	err := s.d.ReadPool().QueryRowContext(ctx, query, slug).Scan(
		&sp.ID, &sp.Kind, &sp.Slug, &sp.Title, &live, &unpub,
		&goLive, &expire, &firstPub, &lastPub,
		&sp.LiveRevisionID, &sp.LatestRevisionID, &sp.OwnerID, &sp.SeoTitle, &sp.SearchDescription,
		&sp.Version, &created, &updated,
		&sp.BodyMD, &sp.BodyHTML, &sp.BodyPlain,
	)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	sp.Live = live == 1
	sp.HasUnpublishedChanges = unpub == 1
	sp.CreatedAt, _ = db.ParseUTC(created.String)
	sp.UpdatedAt, _ = db.ParseUTC(updated.String)
	return &sp, nil
}

// GetHomePins 读首页置顶文章（最多 3 篇，按 sort_order 升序）。
func (s *Store) GetHomePins(ctx context.Context) ([]*HomePin, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `
		SELECT hp.article_page_id, hp.sort_order, `+articleColumns+`
		FROM home_pins hp
		JOIN pages p ON p.id = hp.article_page_id
		JOIN articles a ON a.page_id = p.id
		LEFT JOIN article_categories c ON c.id = a.category_id
		LEFT JOIN users u ON u.id = a.author_id
		ORDER BY hp.sort_order ASC, hp.article_page_id ASC
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var pins []*HomePin
	for rows.Next() {
		var pin HomePin
		var a Article
		var live, unpub, comments, rendVer int
		var goLive, expire, firstPub, lastPub, created, updated sql.NullString
		var catID, coverID, authorID, tourID sql.NullInt64

		err := rows.Scan(
			&pin.ArticlePageID, &pin.SortOrder,
			&a.ID, &a.Kind, &a.Slug, &a.Title, &live, &unpub,
			&goLive, &expire, &firstPub, &lastPub,
			&a.LiveRevisionID, &a.LatestRevisionID, &a.OwnerID, &a.SeoTitle, &a.SearchDescription,
			&a.Version, &created, &updated,
			&catID, &a.CategoryName,
			&coverID, &a.Summary, &a.BodyMD, &a.BodyHTML, &a.BodyPlain,
			&a.CharCount, &a.ReadingTime, &authorID, &a.AuthorName,
			&comments, &tourID, &a.SearchText, &rendVer,
		)
		if err != nil {
			return nil, err
		}
		a.Live = live == 1
		a.HasUnpublishedChanges = unpub == 1
		a.CommentsEnabled = comments == 1
		a.RendererVersion = rendVer
		if catID.Valid {
			a.CategoryID = &catID.Int64
		}
		if coverID.Valid {
			a.CoverImageID = &coverID.Int64
		}
		if authorID.Valid {
			a.AuthorID = &authorID.Int64
		}
		if tourID.Valid {
			a.RelatedTournamentID = &tourID.Int64
		}
		a.CreatedAt, _ = db.ParseUTC(created.String)
		a.UpdatedAt, _ = db.ParseUTC(updated.String)
		pin.Article = &a
		pins = append(pins, &pin)
	}
	return pins, nil
}

// SetHomePins 设置首页置顶文章（最多 3 篇，原子替换）。
func (s *Store) SetHomePins(ctx context.Context, articleIDs []int64) error {
	if len(articleIDs) > 3 {
		return api.Invalid("首页置顶最多 3 篇文章")
	}

	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(txCtx, `DELETE FROM home_pins`); err != nil {
			return err
		}
		for i, id := range articleIDs {
			// 必须是已发布的文章
			var live int
			err := tx.QueryRowContext(txCtx, `SELECT live FROM pages WHERE id = ? AND kind = 'article'`, id).Scan(&live)
			if err != nil {
				return api.Invalid(fmt.Sprintf("文章 ID %d 不存在", id))
			}
			if live != 1 {
				return api.Invalid(fmt.Sprintf("文章 ID %d 尚未发布，不能置顶", id))
			}

			if _, err := tx.ExecContext(txCtx, `INSERT INTO home_pins (article_page_id, sort_order) VALUES (?, ?)`, id, i+1); err != nil {
				return err
			}
		}
		return nil
	})
}

// CheckSlugAvailable 检查同一页面类型下 slug 是否可用。
func (s *Store) CheckSlugAvailable(ctx context.Context, kind, slug string, excludePageID int64) (bool, error) {
	var count int
	err := s.d.ReadPool().QueryRowContext(ctx, `
		SELECT COUNT(*) FROM pages WHERE kind = ? AND slug = ? AND id != ?
	`, kind, slug, excludePageID).Scan(&count)
	if err != nil {
		return false, err
	}
	return count == 0, nil
}
