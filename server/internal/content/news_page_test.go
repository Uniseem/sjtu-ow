package content

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newsFixture(t *testing.T) (*db.DB, *Service) {
	t.Helper()
	d, svc := articleProjectionFixture(t)
	projectionExec(t, d, `INSERT INTO pages (id,kind,slug,title,live,created_at,updated_at) VALUES
 (900,'news_index','news','资讯',1,'2026-10-10','2026-10-10'),(901,'news_index','other','其他栏目',1,'2026-10-10','2026-10-10');
 INSERT INTO news_index (page_id,intro) VALUES (900,'社区的 **文章** 栏目。'),(901,'另一栏目');
 INSERT INTO article_categories (id,name,slug,sort_order,created_at,updated_at) VALUES
 (3,'','shell',0,'2026-10-10','2026-10-10'),(4,'未填网址','',0,'2026-10-10','2026-10-10'),
 (5,'A','alpha',-1,'2026-10-10','2026-10-10'),(6,'B','beta',-1,'2026-10-10','2026-10-10');`)
	return d, svc
}

func TestNewsPageAPI(t *testing.T) {
	d, svc := newsFixture(t)
	reg := &api.Registry{}
	NewModule(svc).Routes(reg)
	h := reg.Handler(func(*http.Request) *app.Viewer { return nil })
	get := func(query string) NewsListOut {
		t.Helper()
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/page/news"+query, nil))
		if rec.Code != 200 {
			t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
		}
		var out NewsListOut
		if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
			t.Fatal(err)
		}
		return out
	}
	out := get("")
	if out.Total != 10 || out.Page != 1 || out.PageSize != 12 || len(out.Items) != 10 || !strings.Contains(out.IntroHTML, "<strong>文章</strong>") {
		t.Fatalf("list=%+v", out)
	}
	if len(out.Categories) != 4 || out.Categories[0].Slug != "alpha" || out.Categories[1].Slug != "beta" || out.Categories[2].Slug != "notice" || out.Categories[3].Slug != "news" {
		t.Fatalf("categories=%+v", out.Categories)
	}
	if out.Items[0].ID != 112 || out.Items[1].ID != 109 || out.Items[0].Author == nil || out.Items[0].Author.ID != 2 || out.Items[0].Author.AvatarImageID == nil || *out.Items[0].Author.AvatarImageID != 80 {
		t.Fatalf("cards=%+v", out.Items)
	}
	if out.Items[1].DefaultCoverImageID == nil || *out.Items[1].DefaultCoverImageID != 30 {
		t.Fatal("default cover lost")
	}
	for _, item := range out.Items {
		if item.ID == 103 || item.ID == 104 || item.ID == 105 || item.ID == 114 || item.ID == 115 {
			t.Fatalf("non-public/wrong column=%d", item.ID)
		}
	}
	for _, q := range []string{"?page_size=2&page=99999", "?page_size=2&page=-1"} {
		out = get(q)
		if out.Page != 5 || len(out.Items) != 2 || out.Items[0].ID != 113 || out.Items[1].ID != 110 {
			t.Fatalf("last page=%+v", out)
		}
	}
	out = get("?category=%20news%20")
	if out.Total != 6 || len(out.Items) != 6 {
		t.Fatalf("category=%+v", out)
	}
	out = get("?category=missing")
	if out.Total != 0 || out.Items == nil || len(out.Items) != 0 || out.Page != 1 {
		t.Fatalf("empty=%+v", out)
	}
	projectionExec(t, d, `UPDATE pages SET first_published_at='2026-10-14T08:00:00.123456Z',last_published_at='2026-10-15T00:00:00Z' WHERE id IN (108,109);
 UPDATE pages SET first_published_at='2026-10-14T08:00:00.123456Z',last_published_at='2026-10-16T00:00:00Z' WHERE id=107`)
	out = get("?category=news")
	if out.Items[0].ID != 107 {
		t.Fatal("last published order lost")
	}
	projectionExec(t, d, "UPDATE users SET is_active=0 WHERE id=1")
	out = get("?category=news")
	for _, item := range out.Items {
		if item.Author != nil && item.Author.ID == 1 && (item.Author.IsActive || item.Author.AvatarImageID != nil) {
			t.Fatal("stopped author avatar exposed")
		}
	}
}

func TestNewsPageGateAndErrors(t *testing.T) {
	for _, update := range []string{"UPDATE pages SET live=0 WHERE id=900", "UPDATE pages SET search_public=0 WHERE id=900", "DELETE FROM pages WHERE id=900"} {
		d, svc := newsFixture(t)
		projectionExec(t, d, update)
		reg := &api.Registry{}
		NewModule(svc).Routes(reg)
		rec := httptest.NewRecorder()
		reg.Handler(func(*http.Request) *app.Viewer { return &app.Viewer{ID: 1, Superuser: true} }).ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/page/news", nil))
		if rec.Code != 404 {
			t.Fatalf("%s status=%d body=%s", update, rec.Code, rec.Body.String())
		}
	}
	for _, table := range []string{"news_index", "article_categories", "images", "users"} {
		t.Run(table, func(t *testing.T) {
			d, svc := newsFixture(t)
			projectionExec(t, d, "ALTER TABLE "+table+" RENAME TO broken_"+table)
			if _, err := svc.NewsPage(&app.Ctx{Context: context.Background()}, NewsListIn{}); err == nil {
				t.Fatal("query failure swallowed")
			}
		})
	}
}

func TestImportNewsIndex(t *testing.T) {
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	_, err := legacy.Exec(`INSERT INTO wagtailcore_page (id,path,slug,title,live,has_unpublished_changes,first_published_at,last_published_at,live_revision_id,seo_title,search_description) VALUES
 (900,'0001','home','首页',1,0,NULL,NULL,NULL,'',''),
 (901,'00010001','news','资讯',1,1,'2026-10-09 08:00:00','2026-10-10 08:00:00.123456',1,'SEO','描述'),
 (902,'000100010001','article','文章',1,0,'2026-10-10 00:00:00',NULL,NULL,'','');
 INSERT INTO content_articleindexpage VALUES (901,'已发布 **简介**');
 INSERT INTO content_articlepage (page_ptr_id,body) VALUES (902,'正文');
 INSERT INTO django_content_type VALUES (4,'content','articleindexpage');
 INSERT INTO wagtailcore_revision VALUES (1,'901',NULL,'{"intro":"已发布简介"}','2026-10-09 08:00:00',NULL,4),
 (2,'901',NULL,'{"intro":"草稿简介"}','2026-10-10 08:00:00',NULL,4);`)
	if err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := ImportLegacyContent(context.Background(), d, legacy, "https://example.test"); err != nil {
			t.Fatal(err)
		}
		var parent, unpub, revisions, latest int
		var seo, description, last string
		if err := d.ReadPool().QueryRowContext(context.Background(), `SELECT parent_id,has_unpublished_changes,seo_title,search_description,last_published_at,latest_revision_id FROM pages WHERE id=901`).Scan(&parent, &unpub, &seo, &description, &last, &latest); err != nil {
			t.Fatal(err)
		}
		if latest != 2 || parent != 900 || unpub != 1 || seo != "SEO" || description != "描述" || last != "2026-10-10T08:00:00.123456Z" {
			t.Fatal("column metadata lost")
		}
		if err := d.ReadPool().QueryRowContext(context.Background(), `SELECT COUNT(*) FROM page_revisions WHERE page_id=901`).Scan(&revisions); err != nil || revisions != 2 {
			t.Fatalf("revisions=%d err=%v", revisions, err)
		}
		out, err := NewService(NewStore(d), "https://example.test").NewsPage(&app.Ctx{Context: context.Background()}, NewsListIn{})
		if err != nil || out.Total != 1 || !strings.Contains(out.IntroHTML, "<strong>简介</strong>") || strings.Contains(out.IntroHTML, "草稿") {
			t.Fatalf("page=%+v err=%v", out, err)
		}
	}
}

func TestImportNewsIndexReportsFailures(t *testing.T) {
	t.Run("read", func(t *testing.T) {
		legacy := newLegacyContentDB(t)
		if _, err := legacy.Exec("DROP TABLE content_articleindexpage"); err != nil {
			t.Fatal(err)
		}
		if err := ImportLegacyContent(context.Background(), newTestDB(t), legacy, "https://example.test"); err == nil || !strings.Contains(err.Error(), "content_articleindexpage") {
			t.Fatalf("err=%v", err)
		}
	})
	t.Run("write", func(t *testing.T) {
		d := newTestDB(t)
		legacy := newLegacyContentDB(t)
		if _, err := legacy.Exec(`INSERT INTO wagtailcore_page (id,slug,title) VALUES (900,'news','资讯'); INSERT INTO content_articleindexpage VALUES (900,'简介')`); err != nil {
			t.Fatal(err)
		}
		projectionExec(t, d, `CREATE TRIGGER reject_news BEFORE INSERT ON news_index BEGIN SELECT RAISE(ABORT,'news injected error'); END`)
		err := ImportLegacyContent(context.Background(), d, legacy, "https://example.test")
		if err == nil || !strings.Contains(err.Error(), "news injected error") {
			t.Fatalf("err=%v", err)
		}
		var count int
		_ = d.ReadPool().QueryRowContext(context.Background(), "SELECT COUNT(*) FROM pages WHERE id=900").Scan(&count)
		if count != 0 {
			t.Fatal("partial index not rolled back")
		}
	})
}
