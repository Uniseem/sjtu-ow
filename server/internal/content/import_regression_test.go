package content

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestImportStandardPagesAndPublicMetadata(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	for i, slug := range []string{"about", "terms", "privacy", "draft", "undated"} {
		live := 1
		if slug == "draft" {
			live = 0
		}
		var first, last any
		if slug != "undated" {
			first = "2026-09-18 12:00:00"
			last = "2026-10-10 08:30:00.123456"
		}
		if _, err := legacy.ExecContext(ctx, `INSERT INTO wagtailcore_page
            (id, slug, title, live, has_unpublished_changes, seo_title, search_description, first_published_at, last_published_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)`, i+10, slug, "普通页"+slug, live, "SEO "+slug, "描述 "+slug, first, last); err != nil {
			t.Fatal(err)
		}
		if _, err := legacy.ExecContext(ctx, `INSERT INTO content_standardpage VALUES (?, ?)`, i+10, "## 欢迎\n正文 **社区**"); err != nil {
			t.Fatal(err)
		}
	}
	// Shared Wagtail revisions also contain non-page models; those are not
	// content-domain rows, even when their numeric object IDs overlap.
	if _, err := legacy.ExecContext(ctx, `INSERT INTO wagtailcore_revision VALUES
        (1, '10', NULL, '{}', '2026-10-10 08:30:00', NULL, 2),
        (2, '99999', NULL, '{}', '2026-10-10 08:30:00', NULL, 3)`); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := ImportLegacyContent(ctx, d, legacy, "https://example.test"); err != nil {
			t.Fatal(err)
		}
	}
	var revisions int
	if err := d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM page_revisions`).Scan(&revisions); err != nil || revisions != 1 {
		t.Fatalf("revisions=%d err=%v", revisions, err)
	}
	reg := &api.Registry{}
	NewModule(NewService(NewStore(d), "https://example.test")).Routes(reg)
	h := reg.Handler(func(*http.Request) *app.Viewer { return nil })
	for _, slug := range []string{"about", "terms", "privacy", "undated"} {
		t.Run(slug, func(t *testing.T) {
			page, err := NewStore(d).GetSitePageBySlug(ctx, slug)
			if err != nil || page == nil {
				t.Fatalf("page=%+v err=%v", page, err)
			}
			if !page.HasUnpublishedChanges || page.BodyMD != "## 欢迎\n正文 **社区**" || !strings.Contains(page.BodyPlain, "社区") {
				t.Fatalf("lost page data: %+v", page)
			}
			if slug != "undated" && (page.FirstPublishedAt == nil || page.FirstPublishedAt.Format(time.RFC3339) != "2026-09-18T12:00:00Z") {
				t.Fatalf("first publication lost: %+v", page)
			}
			rec := httptest.NewRecorder()
			h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/page/"+slug, nil))
			if rec.Code != 200 {
				t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
			}
			var out map[string]any
			if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
				t.Fatal(err)
			}
			if out["slug"] != slug || out["title"] != "普通页"+slug || out["seo_title"] != "SEO "+slug || out["search_description"] != "描述 "+slug || !strings.Contains(out["body_html"].(string), "<strong>社区</strong>") {
				t.Fatalf("unexpected API: %v", out)
			}
			date, present := out["last_published_at"]
			if !present {
				t.Fatal("missing nullable last_published_at")
			}
			if slug == "undated" {
				if date != nil {
					t.Fatalf("undated=%v", date)
				}
			} else if date != "2026-10-10T08:30:00.123456Z" {
				t.Fatalf("date=%v", date)
			}
		})
	}
	for _, slug := range []string{"draft", "missing"} {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/page/"+slug, nil))
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s status=%d", slug, rec.Code)
		}
	}
}

func TestImportContentReportsReadErrors(t *testing.T) {
	for _, table := range []string{"wagtailcore_collection", "wagtailimages_image", "content_articlecategory", "content_articlepage", "content_standardpage", "wagtailcore_revision", "content_homepagepinnedarticle"} {
		t.Run(table, func(t *testing.T) {
			legacy := newLegacyContentDB(t)
			if _, err := legacy.Exec(`DROP TABLE ` + table); err != nil {
				t.Fatal(err)
			}
			err := ImportLegacyContent(context.Background(), newTestDB(t), legacy, "https://example.test")
			if err == nil || !strings.Contains(err.Error(), table) {
				t.Fatalf("expected %s error, got %v", table, err)
			}
		})
	}
	t.Run("scan", func(t *testing.T) {
		legacy := newLegacyContentDB(t)
		if _, err := legacy.Exec(`INSERT INTO content_articlecategory VALUES (1, NULL, 'bad', 0, 1)`); err == nil {
			t.Fatal("fixture NOT NULL must reject null")
		}
		if _, err := legacy.Exec(`INSERT INTO content_articlecategory VALUES (1, 'bad', 'bad', 'not-an-integer', 1)`); err != nil {
			t.Fatal(err)
		}
		if err := ImportLegacyContent(context.Background(), newTestDB(t), legacy, "https://example.test"); err == nil || !strings.Contains(err.Error(), "扫描失败") {
			t.Fatalf("scan error=%v", err)
		}
	})
	for _, table := range []string{"comments_comment", "comments_commentlike"} {
		t.Run(table, func(t *testing.T) {
			legacy := newLegacyContentDB(t)
			if _, err := legacy.Exec(`CREATE TABLE ` + table + ` (id INTEGER)`); err != nil {
				t.Fatal(err)
			}
			if err := ImportLegacyContent(context.Background(), newTestDB(t), legacy, "https://example.test"); err == nil || !strings.Contains(err.Error(), "读取失败") {
				t.Fatalf("optional malformed table error=%v", err)
			}
		})
	}
}

func TestImportContentReportsWritesAndRollsBack(t *testing.T) {
	for _, table := range []string{"image_collections", "images", "article_categories", "pages", "articles", "site_pages", "page_revisions", "home_pins", "comments", "comment_likes"} {
		t.Run(table, func(t *testing.T) {
			ctx := context.Background()
			d := newTestDB(t)
			legacy := newLegacyContentDB(t)
			insertTestUser(t, d, 1, "member@example.test", "成员")
			_, err := legacy.Exec(`
                INSERT INTO wagtailcore_collection VALUES (20, '迁移集合');
                INSERT INTO wagtailimages_image VALUES (20, 20, '图', 'image.jpg', 100, 100, '2026-10-10 08:00:00', 1, 100);
                INSERT INTO content_articlecategory VALUES (20, '迁移分类', 'import', 0, 1);
                INSERT INTO wagtailcore_page (id, slug, title) VALUES (20, 'article', '文章'), (21, 'about', '关于');
                INSERT INTO content_articlepage (page_ptr_id, category_id, body) VALUES (20, 20, '正文');
                INSERT INTO content_standardpage VALUES (21, '普通页正文');
                INSERT INTO wagtailcore_revision VALUES (20, '20', 1, '{}', '2026-10-10 08:00:00', NULL, 1);
                INSERT INTO content_homepagepinnedarticle VALUES (20, 0);
                CREATE TABLE comments_comment (id INTEGER, page_id INTEGER, author_id INTEGER, parent_id INTEGER, reply_to_user_id INTEGER, body TEXT, is_pinned INTEGER, is_hidden INTEGER, is_deleted INTEGER, like_count INTEGER, created_at TEXT, edited_at TEXT);
                INSERT INTO comments_comment VALUES (20, 20, 1, NULL, NULL, '评论', 0, 0, 0, 1, '2026-10-10 08:00:00', NULL);
                CREATE TABLE comments_commentlike (comment_id INTEGER, user_id INTEGER, created_at TEXT);
                INSERT INTO comments_commentlike VALUES (20, 1, '2026-10-10 08:00:00');
            `)
			if err != nil {
				t.Fatal(err)
			}
			err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
				_, err := tx.ExecContext(ctx, fmt.Sprintf(`CREATE TRIGGER reject_import BEFORE INSERT ON %s BEGIN SELECT RAISE(ABORT, 'injected import failure'); END`, table))
				return err
			})
			if err != nil {
				t.Fatal(err)
			}
			err = ImportLegacyContent(ctx, d, legacy, "https://example.test")
			if err == nil || !strings.Contains(err.Error(), "injected import failure") {
				t.Fatalf("%s error=%v", table, err)
			}
			if table == "site_pages" || table == "articles" {
				id := 21
				if table == "articles" {
					id = 20
				}
				var n int
				if err := d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM pages WHERE id = ?`, id).Scan(&n); err != nil || n != 0 {
					t.Fatalf("partial page not rolled back: count=%d err=%v", n, err)
				}
			}
		})
	}
}

func TestImportContentReportsIterationError(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	_, err := legacy.Exec(`DROP TABLE wagtailcore_collection;
        CREATE TABLE collection_source (id INTEGER PRIMARY KEY, payload TEXT);
        INSERT INTO collection_source VALUES (20, '{"name":"valid collection"}'), (21, 'invalid JSON');
        CREATE VIEW wagtailcore_collection AS SELECT id, json_extract(payload, '$.name') AS name FROM collection_source;`)
	if err != nil {
		t.Fatal(err)
	}
	err = ImportLegacyContent(ctx, d, legacy, "https://example.test")
	if err == nil {
		t.Fatal("iteration failure was swallowed")
	}
	var n int
	if err := d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM image_collections WHERE id = 20`).Scan(&n); err != nil || n != 0 {
		t.Fatalf("iteration error committed partial collection: n=%d err=%v", n, err)
	}
}

func TestImportCollectionKeysFollowLegacyIDs(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	if _, err := legacy.Exec(`INSERT INTO wagtailcore_collection VALUES
        (1, '根目录'), (2, '投稿图片'), (3, '默认封面'), (4, '默认头像'), (5, '用户头像');
        INSERT INTO wagtailimages_image VALUES (30, 3, '旧封面', 'cover.jpg', 10, 10, '2026-10-10 08:00:00', NULL, 100);`); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := ImportLegacyContent(ctx, d, legacy, "https://example.test"); err != nil {
			t.Fatal(err)
		}
		for key, id := range map[string]int{"contributed": 2, "default_cover": 3, "default_avatar": 4, "user_avatar": 5} {
			var got int
			if err := d.ReadPool().QueryRowContext(ctx, `SELECT id FROM image_collections WHERE key = ?`, key).Scan(&got); err != nil || got != id {
				t.Fatalf("%s id=%d err=%v", key, got, err)
			}
		}
		var n int
		if err := d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM image_collections`).Scan(&n); err != nil || n != 6 {
			t.Fatalf("collections=%d err=%v", n, err)
		}
		if err := d.ReadPool().QueryRowContext(ctx, `SELECT collection_id FROM images WHERE id = 30`).Scan(&n); err != nil || n != 3 {
			t.Fatalf("old image lost collection: %d err=%v", n, err)
		}
	}
}

func TestImportArticleSearchPublicRestrictions(t *testing.T) {
	for _, restrictedID := range []int{1, 2, 3} {
		t.Run(fmt.Sprint(restrictedID), func(t *testing.T) {
			ctx := context.Background()
			d := newTestDB(t)
			legacy := newLegacyContentDB(t)
			_, err := legacy.Exec(`INSERT INTO wagtailcore_page (id,path,slug,title) VALUES
                (1,'00010001','restricted-parent','受限栏目'),
                (2,'000100010001','article','文章'),
                (3,'00010002','other','其他栏目');
                INSERT INTO content_articlepage (page_ptr_id,body) VALUES (2,'正文');`)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := legacy.Exec(`INSERT INTO wagtailcore_pageviewrestriction VALUES (1,?)`, restrictedID); err != nil {
				t.Fatal(err)
			}
			if err := ImportLegacyContent(ctx, d, legacy, "https://example.test"); err != nil {
				t.Fatal(err)
			}
			var public, live int
			if err := d.ReadPool().QueryRowContext(ctx, `SELECT search_public,live FROM pages WHERE id=2`).Scan(&public, &live); err != nil {
				t.Fatal(err)
			}
			want := 0
			if restrictedID == 3 {
				want = 1
			}
			if public != want || live != 1 {
				t.Fatalf("public=%d live=%d want public=%d", public, live, want)
			}
		})
	}
}
