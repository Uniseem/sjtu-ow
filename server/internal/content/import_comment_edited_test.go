package content

import (
	"context"
	"database/sql"
	"testing"
)

func TestImportCommentEditedAt(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	insertTestUser(t, d, 1, "member@example.test", "成员")
	_, err := legacy.Exec(`
 INSERT INTO wagtailcore_page (id,slug,title) VALUES (20,'article','文章');
 INSERT INTO content_articlepage (page_ptr_id,body) VALUES (20,'正文');
 CREATE TABLE comments_comment (id INTEGER,page_id INTEGER,author_id INTEGER,parent_id INTEGER,reply_to_user_id INTEGER,body TEXT,is_pinned INTEGER,is_hidden INTEGER,is_deleted INTEGER,like_count INTEGER,created_at TEXT,edited_at TEXT);
 INSERT INTO comments_comment VALUES
 (1,20,1,NULL,NULL,'未编辑',0,0,0,0,'2026-10-10 08:00:00',NULL),
 (2,20,1,1,1,'已编辑',0,0,0,0,'2026-10-10 08:00:00','2026-10-11 09:30:00.123456');`)
	if err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := ImportLegacyContent(ctx, d, legacy, "https://example.test"); err != nil {
			t.Fatal(err)
		}
		for _, tc := range []struct {
			id              int
			edited, updated string
		}{
			{1, "", "2026-10-10T08:00:00.000000Z"},
			{2, "2026-10-11T09:30:00.123456Z", "2026-10-11T09:30:00.123456Z"},
		} {
			var edited sql.NullString
			var updated string
			if err := d.ReadPool().QueryRowContext(ctx, `SELECT edited_at,updated_at FROM comments WHERE id=?`, tc.id).Scan(&edited, &updated); err != nil {
				t.Fatal(err)
			}
			if edited.Valid != (tc.edited != "") || edited.String != tc.edited || updated != tc.updated {
				t.Fatalf("id=%d edited=%v updated=%s", tc.id, edited, updated)
			}
		}
	}
}
