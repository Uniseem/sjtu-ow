package content

import (
	"context"
	"database/sql"
	"errors"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Return the safe editor projection from the same transaction snapshot.
func articleStale(ctx context.Context, q db.DBTX, id int64) error {
	var version int64
	var content sql.NullString
	err := q.QueryRowContext(ctx, `SELECT p.version,r.content FROM pages p LEFT JOIN page_revisions r ON r.id=p.latest_revision_id
        WHERE p.id=? AND p.kind='article'`, id).Scan(&version, &content)
	if errors.Is(err, sql.ErrNoRows) {
		return api.NotFound("文章不存在")
	}
	if err != nil {
		return err
	}
	article, err := scanArticle(q.QueryRowContext(ctx, `SELECT `+articleColumns+` FROM pages p JOIN articles a ON a.page_id=p.id
        LEFT JOIN article_categories c ON c.id=a.category_id LEFT JOIN users u ON u.id=a.author_id WHERE p.id=?`, id))
	if err != nil {
		return err
	}
	draft := articleDraft(article)
	if content.Valid {
		draft, err = readArticleRevisionContent(content.String, draft)
		if err != nil {
			return err
		}
	}
	return api.Stale(map[string]any{"version": version, "values": draft})
}
