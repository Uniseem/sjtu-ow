package db

import (
	"context"
	"database/sql"
	"testing"
)

func TestCommentEditedAtUpgrade(t *testing.T) {
	d := openTestDB(t)
	ctx := context.Background()
	p, err := newProvider(d)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = p.UpTo(ctx, 18); err != nil {
		t.Fatal(err)
	}
	err = d.WriteTx(ctx, func(ctx context.Context, tx *Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO pages (id,kind,slug,title,created_at,updated_at) VALUES (1,'article','old','旧文章','2026-10-10T08:00:00Z','2026-10-10T08:00:00Z');
 INSERT INTO articles (page_id) VALUES (1);
 INSERT INTO comments (id,article_id,content,created_at,updated_at) VALUES (1,1,'旧评论','2026-10-10T08:00:00Z','2026-10-11T08:00:00Z');`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := Migrate(ctx, d); err != nil {
			t.Fatal(err)
		}
		var content, updated string
		var edited sql.NullString
		if err := d.ReadPool().QueryRowContext(ctx, `SELECT content,updated_at,edited_at FROM comments WHERE id=1`).Scan(&content, &updated, &edited); err != nil {
			t.Fatal(err)
		}
		if content != "旧评论" || updated != "2026-10-11T08:00:00Z" || edited.Valid {
			t.Fatalf("content=%s updated=%s edited=%v", content, updated, edited)
		}
	}
}
