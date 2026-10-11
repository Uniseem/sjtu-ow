package tournaments

import (
	"context"
	"database/sql"
	"net/url"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

// RelatedArticle contains only fields of a live, public article linked to the
// current tournament; drafts and restricted pages are filtered in SQL.
type RelatedArticle struct {
	ID               int64      `json:"id"`
	Title            string     `json:"title"`
	Slug             string     `json:"slug"`
	URL              string     `json:"url"`
	FirstPublishedAt *time.Time `json:"first_published_at"`
}

func relatedArticles(ctx context.Context, q db.DBTX, id int64) ([]RelatedArticle, error) {
	rows, err := q.QueryContext(ctx, `SELECT p.id,p.title,p.slug,p.first_published_at
		FROM pages p JOIN articles a ON a.page_id=p.id
		WHERE p.live=1 AND p.search_public=1 AND a.related_tournament_id=?
		ORDER BY p.first_published_at DESC,p.id DESC`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []RelatedArticle{}
	for rows.Next() {
		var item RelatedArticle
		var published sql.NullString
		if err := rows.Scan(&item.ID, &item.Title, &item.Slug, &published); err != nil {
			return nil, err
		}
		item.FirstPublishedAt = nullTime(published)
		item.URL = "/news/" + url.PathEscape(item.Slug) + "/"
		out = append(out, item)
	}
	return out, rows.Err()
}

func (s *Service) projectPublicDetail(ctx *app.Ctx, page *Page) error {
	q := s.d.ReadPool()
	body, _, err := markdown.Render(page.Tournament.Description, s.siteURL, nil)
	if err != nil {
		return err
	}
	page.BodyHTML = body
	covers, err := media.LoadPool(ctx.Context, q, "default_cover")
	if err != nil {
		return err
	}
	cover := media.PickCover(covers, page.Tournament.ID, 13)
	page.Tournament.DefaultCoverImageID = cover
	page.DefaultCoverImageID = cover
	page.Card = cardOf(page.Tournament, ctx.Now().UTC(), len(page.ApprovedTeams))
	page.Articles, err = relatedArticles(ctx.Context, q, page.Tournament.ID)
	return err
}

// publicAvatars resolves this page's visible participants in one read. The
// only returned identifiers are approved/current avatars or deterministic
// defaults; stopped users are intentionally mapped to nil.
func publicAvatars(ctx context.Context, q db.DBTX, pool []media.PoolImage, users []int64) (map[int64]*int64, error) {
	out := map[int64]*int64{}
	if len(users) == 0 {
		return out, nil
	}
	args := []any{}
	marks := []string{}
	seen := map[int64]bool{}
	for _, id := range users {
		if id <= 0 || seen[id] {
			continue
		}
		seen[id] = true
		args = append(args, id)
		marks = append(marks, "?")
	}
	if len(args) == 0 {
		return out, nil
	}
	rows, err := q.QueryContext(ctx, `SELECT id,is_active,main_role,avatar_image_id FROM users WHERE id IN (`+strings.Join(marks, ",")+`)`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var active int
		var role string
		var image sql.NullInt64
		if err := rows.Scan(&id, &active, &role, &image); err != nil {
			return nil, err
		}
		if active != 1 {
			out[id] = nil
			continue
		}
		if image.Valid {
			value := image.Int64
			out[id] = &value
		} else {
			out[id] = media.PickAvatar(pool, id, role)
		}
	}
	return out, rows.Err()
}
