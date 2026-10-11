package db

import (
	"context"
	"testing"
)

func TestPagePublicMigration(t *testing.T) {
	d := openTestDB(t)
	ctx := context.Background()
	p, err := newProvider(d)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := p.UpTo(ctx, 20); err != nil {
		t.Fatal(err)
	}
	if err := d.WriteTx(ctx, func(ctx context.Context, tx *Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO pages (id,kind,slug,title,live,search_public,created_at,updated_at) VALUES
 (1,'article','public','public',1,1,'x','x'),(2,'article','private','private',1,0,'x','x'),(3,'site_page','draft','draft',0,1,'x','x')`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := Migrate(ctx, d); err != nil {
			t.Fatal(err)
		}
	}
	for _, tc := range []struct{ id, public, live int }{{1, 1, 1}, {2, 0, 1}, {3, 1, 0}} {
		var public, live int
		if err := d.ReadPool().QueryRowContext(ctx, `SELECT is_public,live FROM pages WHERE id=?`, tc.id).Scan(&public, &live); err != nil || public != tc.public || live != tc.live {
			t.Fatalf("id=%d public=%d live=%d err=%v", tc.id, public, live, err)
		}
	}
}
