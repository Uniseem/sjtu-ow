package content

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// 站点地图照旧站（frontend-migration B2）：地址带斜杠、只收公开的、日期按上海时区。
func TestSitemapListsWhatTheOldSiteListed(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 10, 12, 0, 0, 0, time.UTC)
	old := db.FormatUTC(now.Add(-40 * 24 * time.Hour))
	recent := db.FormatUTC(now.Add(-5 * 24 * time.Hour))
	// 16:30 UTC 已经是上海的第二天 00:30
	late := "2026-10-01T16:30:00Z"
	stmts := []string{
		`INSERT INTO pages (id, kind, slug, title, live, last_published_at, created_at, updated_at) VALUES
			(1, 'article', 'kai-mu', '开幕', 1, '` + late + `', 'x', 'x'),
			(2, 'article', 'cao-gao', '草稿', 0, NULL, 'x', 'x'),
			(3, 'site_page', 'about', '关于', 1, '` + late + `', 'x', 'x')`,
		`INSERT INTO teams (id, name, disbanded_at, created_at, updated_at) VALUES
			(5, '在的队', NULL, 'x', '` + late + `'), (6, '散了的队', '` + late + `', 'x', 'x')`,
		`INSERT INTO tournaments (id, title, status, created_at, updated_at) VALUES
			(7, '发布', 'published', 'x', 'x'), (8, '结束', 'finished', 'x', 'x'), (9, '草稿', 'draft', 'x', 'x'), (10, '取消', 'cancelled', 'x', 'x')`,
		`INSERT INTO scrims (id, title, format, starts_at, status, created_at, updated_at) VALUES
			(11, '发布', 'rq_5v5', '` + old + `', 'published', 'x', 'x'),
			(12, '刚结束', 'rq_5v5', '` + recent + `', 'finished', 'x', 'x'),
			(13, '早结束', 'rq_5v5', '` + old + `', 'finished', 'x', 'x'),
			(14, '取消', 'rq_5v5', '` + recent + `', 'cancelled', 'x', 'x')`,
	}
	for _, q := range stmts {
		if err := d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error { _, err := tx.ExecContext(c, q); return err }); err != nil {
			t.Fatalf("%s: %v", q, err)
		}
	}
	svc := NewService(NewStore(d), "https://sjtu.example/")
	got, err := svc.GenerateSitemap(ctx, now)
	if err != nil {
		t.Fatal(err)
	}
	var locs []string
	for _, line := range strings.Split(got, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "<loc>") {
			locs = append(locs, strings.TrimSuffix(strings.TrimPrefix(line, "<loc>"), "</loc>"))
		}
	}
	want := []string{
		"https://sjtu.example/news/kai-mu/",
		"https://sjtu.example/about/",
		"https://sjtu.example/teams/5/",
		"https://sjtu.example/tournaments/7/",
		"https://sjtu.example/tournaments/8/",
		"https://sjtu.example/scrims/11/",
		"https://sjtu.example/scrims/12/",
	}
	if strings.Join(locs, "\n") != strings.Join(want, "\n") {
		t.Fatalf("地址\n got %q\nwant %q", locs, want)
	}
	if !strings.Contains(got, "<lastmod>2026-10-02</lastmod>") {
		t.Fatalf("日期要按上海时区：\n%s", got)
	}
}

func TestRobotsMatchesTheOldSite(t *testing.T) {
	svc := NewService(NewStore(nil), "https://sjtu.example")
	want := "User-agent: *\nDisallow: /admin/\nDisallow: /wagtail/\nDisallow: /me/\nDisallow: /accounts/\nDisallow: /_fragments/\nDisallow: /_styleguide/\nDisallow: /search/\nSitemap: https://sjtu.example/sitemap.xml\n"
	if got := svc.GenerateRobots(); got != want {
		t.Fatalf("robots\n got %q\nwant %q", got, want)
	}
	if got := svc.WithTestEnvironment(true).GenerateRobots(); got != "User-agent: *\nDisallow: /\n" {
		t.Fatalf("测试站整站不让抓：%q", got)
	}
	rec := httptest.NewRecorder()
	NewModule(svc).ServeRobots(rec, httptest.NewRequest(http.MethodGet, "/robots.txt", nil))
	if rec.Header().Get("Content-Type") != "text/plain; charset=utf-8" {
		t.Fatal(rec.Header())
	}
}
