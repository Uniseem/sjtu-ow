package content

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/search"
)

func TestPublicContentHTTPMatrix(t *testing.T) {
	d, svc := newsFixture(t)
	projectionExec(t, d, `UPDATE pages SET owner_id=1 WHERE id IN (100,104,105);
 INSERT INTO pages (id,kind,slug,title,live,is_public,created_at,updated_at) VALUES
 (950,'site_page','public-page','公开普通页',1,1,'2026-10-10','2026-10-10'),
 (951,'site_page','private-page','受限普通页',1,0,'2026-10-10','2026-10-10'),
 (952,'site_page','draft-page','草稿普通页',0,1,'2026-10-10','2026-10-10');
 INSERT INTO site_pages (page_id,body_html) VALUES (950,'<p>公开</p>'),(951,'<p>PRIVATE BODY</p>'),(952,'<p>DRAFT BODY</p>');
 INSERT INTO home_pins VALUES (104,0),(105,1),(100,2);
 UPDATE pages SET search_public=0 WHERE id=100;`)
	projectionExec(t, d, `INSERT INTO pages (id,kind,slug,title,live,is_public,parent_id,first_published_at,created_at,updated_at) VALUES (953,'article','private-notice','private-notice',1,0,900,'2099-01-01T00:00:00Z','2026-10-10','2026-10-10'); INSERT INTO articles (page_id,category_id,author_id) VALUES (953,2,1)`)

	reg := &api.Registry{}
	NewModule(svc).Routes(reg)
	search.NewModule(search.NewService(d)).Routes(reg)
	var viewer *app.Viewer
	h := reg.Handler(func(*http.Request) *app.Viewer { return viewer })
	roles := []struct {
		name string
		v    *app.Viewer
	}{
		{"visitor", nil}, {"member", &app.Viewer{ID: 2, EmailVerified: true}},
		{"author", &app.Viewer{ID: 1, EmailVerified: true, Caps: map[app.Cap]struct{}{"admin.enter": {}}}},
		{"editor", &app.Viewer{ID: 2, EmailVerified: true, Caps: map[app.Cap]struct{}{"admin.enter": {}, CapArticlesEditAny: {}}}},
		{"superuser", &app.Viewer{ID: 3, Superuser: true}}, {"disabled", &app.Viewer{ID: 3, Superuser: true, Disabled: true}},
	}
	for _, role := range roles {
		t.Run(role.name, func(t *testing.T) {
			viewer = role.v
			for _, tc := range []struct {
				path   string
				status int
			}{
				{"/api/page/news/current", 200}, {"/api/page/news/draft", 404}, {"/api/page/news/restricted", 404}, {"/api/page/news/missing", 404},
				{"/api/page/public-page", 200}, {"/api/page/private-page", 404}, {"/api/page/draft-page", 404},
			} {
				rec := httptest.NewRecorder()
				h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, tc.path, nil))
				if rec.Code != tc.status {
					t.Fatalf("%s status=%d body=%s", tc.path, rec.Code, rec.Body.String())
				}
			}
			for _, path := range []string{"/api/page/news", "/api/page/home", "/api/home-pins", "/sitemap.xml"} {
				rec := httptest.NewRecorder()
				h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
				if rec.Code != 200 {
					t.Fatalf("%s status=%d body=%s", path, rec.Code, rec.Body.String())
				}
				for _, secret := range []string{"restricted", "latest-restricted", "draft-page", "private-page", "PRIVATE BODY", "DRAFT BODY", "private-notice"} {
					if strings.Contains(rec.Body.String(), secret) {
						t.Fatalf("%s exposes %s", path, secret)
					}
				}
			}
		})
	}
	// Backend remains the authorized editing path, including drafts.
	for _, role := range roles {
		viewer = role.v
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/admin/articles/104", nil))
		allowed := role.name == "author" || role.name == "editor" || role.name == "superuser"
		if (rec.Code == 200) != allowed {
			t.Fatalf("admin %s status=%d body=%s", role.name, rec.Code, rec.Body.String())
		}
	}
	// Editing capability is required to read the full backend pin selection.
	for _, role := range roles {
		viewer = role.v
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/admin/home-pins", nil))
		allowed := role.name == "editor" || role.name == "superuser"
		if (rec.Code == 200) != allowed {
			t.Fatalf("admin pins %s status=%d", role.name, rec.Code)
		}
	}
	// Search hidden does not mean private; search still omits it.
	viewer = nil
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/search?q=%E5%BD%93%E5%89%8D", nil))
	if rec.Code != 200 || strings.Contains(rec.Body.String(), "/news/current/") {
		t.Fatalf("search=%s", rec.Body.String())
	}
	// Explicit private cannot enter search merely because its search cache says visible.
	projectionExec(t, d, "UPDATE pages SET search_public=1 WHERE id=105")
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/search?q=%E5%8F%97%E9%99%90", nil))
	if rec.Code != 200 || strings.Contains(rec.Body.String(), "/news/restricted/") {
		t.Fatalf("private search=%s", rec.Body.String())
	}
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/home-pins", nil))
	var pins HomePinsOut
	if err := json.Unmarshal(rec.Body.Bytes(), &pins); err != nil {
		t.Fatal(err)
	}
	if len(pins.Items) != 1 || pins.Items[0].ID != 100 || pins.Items[0].FirstPublishedAt == nil {
		t.Fatalf("public pins=%+v", pins)
	}
}

func TestImportPublicFlagsAcrossKinds(t *testing.T) {
	for _, restriction := range []int{1, 2, 3, 4, 99} {
		t.Run(string(rune('a'+restriction)), func(t *testing.T) {
			d := newTestDB(t)
			legacy := newLegacyContentDB(t)
			_, err := legacy.Exec(`INSERT INTO wagtailcore_page (id,path,slug,title,live) VALUES
  (1,'0001','root','root',1),(2,'00010001','news','news',1),(3,'000100010001','article','article',1),
  (4,'00010002','about','about',1),(99,'0002','else','else',1);
  INSERT INTO content_articleindexpage VALUES (2,'intro'); INSERT INTO content_articlepage (page_ptr_id,body) VALUES (3,'body');
  INSERT INTO content_standardpage VALUES (4,'page'); INSERT INTO wagtailcore_pageviewrestriction VALUES (1,?)`, restriction)
			if err != nil {
				t.Fatal(err)
			}
			for range 2 {
				if err := ImportLegacyContent(context.Background(), d, legacy, "https://example.test"); err != nil {
					t.Fatal(err)
				}
			}
			for _, id := range []int{2, 3, 4} {
				var public, live int
				if err := d.ReadPool().QueryRowContext(context.Background(), `SELECT is_public,live FROM pages WHERE id=?`, id).Scan(&public, &live); err != nil {
					t.Fatal(err)
				}
				want := 1
				if restriction == 1 || restriction == id || (restriction == 2 && id == 3) {
					want = 0
				}
				if public != want || live != 1 {
					t.Fatalf("restriction=%d id=%d public=%d live=%d", restriction, id, public, live)
				}
			}
		})
	}
}

func TestPublicPinsKeepAdminSelection(t *testing.T) {
	d, svc := newsFixture(t)
	projectionExec(t, d, "INSERT INTO home_pins VALUES (104,0),(105,1),(100,2)")
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true}}
	public, err := svc.HomePins(ctx, true)
	if err != nil || len(public.Items) != 1 {
		t.Fatalf("public=%+v err=%v", public, err)
	}
	admin, err := svc.HomePins(ctx, false)
	if err != nil || len(admin.Items) != 3 {
		t.Fatalf("admin=%+v err=%v", admin, err)
	}
	ctx.Viewer = &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}}}
	if _, err := svc.HomePins(ctx, false); err == nil {
		t.Fatal("ordinary backend entrant read private pins")
	}

	if _, err := svc.GenerateSitemap(context.Background(), time.Now()); err != nil {
		t.Fatal(err)
	}
}
