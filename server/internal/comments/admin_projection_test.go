package comments

import (
	"context"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestAdminCommentProjectionHasActualArticleSlug(t *testing.T) {
	d := newTestDB(t)
	insertTestUser(t, d, 1, "projection@example.test", "测试成员")
	setupTestArticle(t, d, 7, true, true)
	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, "UPDATE pages SET slug='real-article-slug' WHERE id=7"); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, `INSERT INTO comments (article_id,user_id,content,created_at,updated_at) VALUES (7,1,'projection','2026-10-11T00:00:00Z','2026-10-11T00:00:00Z')`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	rows, total, err := NewStore(d).ListAdminComments(context.Background(), "", nil, nil, 1, 20)
	if err != nil || total != 1 || len(rows) != 1 || rows[0].ArticleSlug != "real-article-slug" {
		t.Fatalf("admin comment link projection incorrect: rows=%+v total=%d err=%v", rows, total, err)
	}
}
