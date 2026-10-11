package db

import (
	"context"
	"database/sql"
	"testing"
)

func TestContentParentLinksUpgrade(t *testing.T) {
	d := openTestDB(t)
	ctx := context.Background()
	p, err := newProvider(d)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = p.UpTo(ctx, 19); err != nil {
		t.Fatal(err)
	}
	if err := d.WriteTx(ctx, func(ctx context.Context, tx *Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO pages (id,kind,slug,title,created_at,updated_at) VALUES (10,'article','old','原文','2026-10-10','2026-10-10')`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := Migrate(ctx, d); err != nil {
			t.Fatal(err)
		}
		var title string
		var parent sql.NullInt64
		if err := d.ReadPool().QueryRowContext(ctx, `SELECT title,parent_id FROM pages WHERE id=10`).Scan(&title, &parent); err != nil || title != "原文" || parent.Valid {
			t.Fatalf("title=%s parent=%v err=%v", title, parent, err)
		}
		if err := d.ReadPool().QueryRowContext(ctx, `SELECT parent_id FROM image_collections WHERE key='default_cover'`).Scan(&parent); err != nil || parent.Valid {
			t.Fatalf("collection parent=%v err=%v", parent, err)
		}
	}
}
