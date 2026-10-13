package content

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

type articleExpiryCandidate struct {
	PageID, Version int64
	ExpireAt        string
}

type approvedArticleCandidate struct {
	PageID, RevisionID int64
	ApprovedAt         string
}

func joinScheduledErrors(failures []error) error { return errors.Join(failures...) }

// Imported revisions and early Go writes use different valid UTC encodings.
// Parse their time instead of comparing a variable-width fractional suffix.
func expiryCandidates(ctx context.Context, q db.DBTX, now time.Time) ([]articleExpiryCandidate, error) {
	rows, err := q.QueryContext(ctx, "SELECT id,version,expire_at FROM pages WHERE kind='article' AND live=1 AND expire_at IS NOT NULL")
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []articleExpiryCandidate{}
	for rows.Next() {
		var candidate articleExpiryCandidate
		if err := rows.Scan(&candidate.PageID, &candidate.Version, &candidate.ExpireAt); err != nil {
			return nil, err
		}
		at, err := db.ParseUTC(candidate.ExpireAt)
		if err != nil {
			return nil, err
		}
		if at.Before(now) {
			out = append(out, candidate)
		}
	}
	return out, rows.Err()
}

func approvedArticleCandidates(ctx context.Context, q db.DBTX, now time.Time) ([]approvedArticleCandidate, error) {
	rows, err := q.QueryContext(ctx, `SELECT p.id,r.id,r.approved_go_live_at FROM page_revisions r
        JOIN pages p ON p.id=r.page_id WHERE p.kind='article' AND r.approved_go_live_at IS NOT NULL ORDER BY r.approved_go_live_at,r.id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []approvedArticleCandidate{}
	for rows.Next() {
		var candidate approvedArticleCandidate
		if err := rows.Scan(&candidate.PageID, &candidate.RevisionID, &candidate.ApprovedAt); err != nil {
			return nil, err
		}
		at, err := db.ParseUTC(candidate.ApprovedAt)
		if err != nil {
			return nil, err
		}
		if at.Before(now) {
			out = append(out, candidate)
		}
	}
	return out, rows.Err()
}

func expireArticleCandidate(ctx context.Context, tx *db.Tx, candidate articleExpiryCandidate, now time.Time) error {
	var live int
	var version int64
	var expiry sql.NullString
	err := tx.QueryRowContext(ctx, "SELECT live,version,expire_at FROM pages WHERE id=? AND kind='article'", candidate.PageID).Scan(&live, &version, &expiry)
	if errors.Is(err, sql.ErrNoRows) {
		return nil
	}
	if err != nil {
		return err
	}
	if live != 1 || version != candidate.Version || !expiry.Valid || expiry.String != candidate.ExpireAt {
		return nil
	}
	at, err := db.ParseUTC(expiry.String)
	if err != nil {
		return err
	}
	if !at.Before(now) {
		return nil
	}
	if _, err := tx.ExecContext(ctx, `UPDATE pages SET live=0,expired=1,live_revision_id=NULL,has_unpublished_changes=1,
        version=version+1,updated_at=? WHERE id=?`, db.FormatUTC(now), candidate.PageID); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, "UPDATE page_revisions SET approved_go_live_at=NULL WHERE page_id=?", candidate.PageID); err != nil {
		return err
	}
	return audit.Record(ctx, tx, 0, "wagtail.unpublish.scheduled", "page", candidate.PageID, nil, now)
}

// Publish exactly the approved immutable revision. A newer autosave remains
// the latest draft and never becomes public because the worker ran.
func (s *Service) publishApprovedArticle(ctx context.Context, tx *db.Tx, candidate approvedArticleCandidate, now time.Time) (*Article, error) {
	var content string
	var approval sql.NullString
	err := tx.QueryRowContext(ctx, "SELECT content,approved_go_live_at FROM page_revisions WHERE id=? AND page_id=?", candidate.RevisionID, candidate.PageID).Scan(&content, &approval)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if !approval.Valid || approval.String != candidate.ApprovedAt {
		return nil, nil
	}
	at, err := db.ParseUTC(approval.String)
	if err != nil {
		return nil, err
	}
	if !at.Before(now) {
		return nil, nil
	}
	article, err := scanArticle(tx.QueryRowContext(ctx, `SELECT `+articleColumns+` FROM pages p JOIN articles a ON a.page_id=p.id
        LEFT JOIN article_categories c ON c.id=a.category_id LEFT JOIN users u ON u.id=a.author_id WHERE p.id=? AND p.kind='article'`, candidate.PageID))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	draft, err := readArticleRevisionContent(content, articleDraft(article))
	if err != nil {
		return nil, err
	}
	if draft.AuthorID == nil {
		draft.AuthorID = article.OwnerID
	}
	title := strings.TrimSpace(draft.Title)
	if title == "" || draft.CategoryID == nil || strings.TrimSpace(draft.BodyMD) == "" {
		return nil, fmt.Errorf("已批准修订缺少标题、分类或正文")
	}
	slug := strings.TrimSpace(draft.Slug)
	if slug == "" {
		slug = Slugify(title)
	}
	slug, err = approvedArticleSlug(ctx, tx, article.ID, slug)
	if err != nil {
		return nil, err
	}
	rendered, stats, err := markdown.Render(draft.BodyMD, s.siteURL, nil)
	if err != nil {
		return nil, err
	}
	anchored, headings := markdown.AnchorHeadings(rendered)
	if len(headings) >= 3 {
		rendered = anchored
	}
	plain := markdown.PlainHTML(rendered)
	words := markdown.WordCount(plain)
	reading := markdown.ReadingMinutes(words, stats.Images, stats.Videos)
	search := strings.ToLower(fmt.Sprintf("%s\n%s\n%s", title, draft.Summary, plain))
	var expiry any
	if draft.ExpireAt != nil {
		expiry = db.FormatUTC(*draft.ExpireAt)
	}
	if _, err := tx.ExecContext(ctx, `UPDATE pages SET title=?,slug=?,seo_title=?,search_description=?,go_live_at=?,expire_at=?,
        live=1,expired=0,live_revision_id=?,has_unpublished_changes=CASE WHEN latest_revision_id=? THEN 0 ELSE 1 END,
        first_published_at=COALESCE(NULLIF(first_published_at,''),?),last_published_at=?,updated_at=?,version=version+1 WHERE id=?`,
		title, slug, draft.SeoTitle, draft.SearchDescription, db.FormatUTC(at), expiry, candidate.RevisionID, candidate.RevisionID,
		db.FormatUTC(now), db.FormatUTC(now), db.FormatUTC(now), article.ID); err != nil {
		return nil, err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE articles SET category_id=?,cover_image_id=?,summary=?,body_md=?,body_html=?,body_plain=?,
        char_count=?,reading_time=?,author_id=?,comments_enabled=?,related_tournament_id=?,search_text=?,renderer_version=1 WHERE page_id=?`,
		draft.CategoryID, draft.CoverImageID, draft.Summary, draft.BodyMD, rendered, plain, words, reading, draft.AuthorID,
		draft.CommentsEnabled, draft.RelatedTournamentID, search, article.ID); err != nil {
		return nil, err
	}
	if _, err := tx.ExecContext(ctx, "UPDATE page_revisions SET approved_go_live_at=NULL WHERE page_id=?", article.ID); err != nil {
		return nil, err
	}
	if err := audit.Record(ctx, tx, 0, "wagtail.publish.scheduled", "page", article.ID, map[string]any{"revision_id": candidate.RevisionID}, now); err != nil {
		return nil, err
	}
	article.Title, article.Slug, article.Summary, article.BodyMD, article.AuthorID = title, slug, draft.Summary, draft.BodyMD, draft.AuthorID
	return article, nil
}

func approvedArticleSlug(ctx context.Context, q db.DBTX, id int64, base string) (string, error) {
	if _, reserved := ReservedSlugs[base]; reserved {
		base += "-article"
	}
	candidate := base
	for suffix := 2; suffix <= 1001; suffix++ {
		var count int
		if err := q.QueryRowContext(ctx, "SELECT COUNT(*) FROM pages WHERE kind='article' AND slug=? AND id!=?", candidate, id).Scan(&count); err != nil {
			return "", err
		}
		if count == 0 {
			return candidate, nil
		}
		candidate = fmt.Sprintf("%s-%d", base, suffix)
	}
	return "", fmt.Errorf("无法为已批准文章生成唯一网址")
}
