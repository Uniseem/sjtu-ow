package content

import (
	"context"
	"encoding/xml"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// 照旧站 content.views.sitemap_xml / robots_txt（设计 13.14；frontend-migration B2）：
// 地址带结尾斜杠，日期按上海时区，内容只收公开的。

type urlSet struct {
	XMLName xml.Name `xml:"http://www.sitemaps.org/schemas/sitemap/0.9 urlset"`
	URLs    []urlEntry
}

type urlEntry struct {
	XMLName xml.Name `xml:"url"`
	Loc     string   `xml:"loc"`
	LastMod string   `xml:"lastmod,omitempty"`
}

var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

// finishedScrimsVisible 和 scrims.FinishedVisibleDays 一样（规则 149）：已结束的内战
// 在公开列表里留 30 天。不引 scrims 包是为了不让内容域依赖活动域。
const finishedScrimsVisible = 30 * 24 * time.Hour

// GenerateSitemap 生成站点地图：已发布的文章和普通页、没解散的战队、发布或结束了的
// 赛事、公开的内战（已发布，或 30 天内结束的）。草稿和取消的不进来。
func (s *Service) GenerateSitemap(ctx context.Context, now time.Time) (string, error) {
	q := s.store.d.ReadPool()
	var urls []urlEntry
	add := func(query string, loc func(key string) string, args ...any) error {
		rows, err := q.QueryContext(ctx, query, args...)
		if err != nil {
			return err
		}
		defer rows.Close()
		for rows.Next() {
			var key, mod string
			if err := rows.Scan(&key, &mod); err != nil {
				return err
			}
			urls = append(urls, urlEntry{Loc: s.siteURL + loc(key), LastMod: shanghaiDate(mod)})
		}
		return rows.Err()
	}
	steps := []struct {
		query string
		loc   func(string) string
		args  []any
	}{
		{`SELECT slug, IFNULL(last_published_at, '') FROM pages WHERE kind = ? AND live = 1 ORDER BY id`,
			func(k string) string { return "/news/" + k + "/" }, []any{KindArticle}},
		{`SELECT slug, IFNULL(last_published_at, '') FROM pages WHERE kind = ? AND live = 1 ORDER BY id`,
			func(k string) string { return "/" + k + "/" }, []any{KindSitePage}},
		{`SELECT id, updated_at FROM teams WHERE disbanded_at IS NULL ORDER BY id`,
			func(k string) string { return "/teams/" + k + "/" }, nil},
		{`SELECT id, updated_at FROM tournaments WHERE status IN ('published', 'finished') ORDER BY id`,
			func(k string) string { return "/tournaments/" + k + "/" }, nil},
		{`SELECT id, updated_at FROM scrims WHERE status = 'published' OR (status = 'finished' AND starts_at >= ?) ORDER BY id`,
			func(k string) string { return "/scrims/" + k + "/" }, []any{db.FormatUTC(now.Add(-finishedScrimsVisible))}},
	}
	for _, st := range steps {
		if err := add(st.query, st.loc, st.args...); err != nil {
			return "", err
		}
	}
	out, err := xml.MarshalIndent(urlSet{URLs: urls}, "", "  ")
	if err != nil {
		return "", err
	}
	return xml.Header + string(out) + "\n", nil
}

// shanghaiDate 把库里的 UTC 时间写成上海时区的「年-月-日」；读不懂就不写。
func shanghaiDate(raw string) string {
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02 15:04:05"} {
		if t, err := time.Parse(layout, raw); err == nil {
			return t.In(shanghai).Format("2006-01-02")
		}
	}
	return ""
}

// GenerateRobots 生成 robots.txt。测试环境整站不让抓（设计 16.10）。
func (s *Service) GenerateRobots() string {
	if s.testEnvironment {
		return "User-agent: *\nDisallow: /\n"
	}
	return strings.Join([]string{
		"User-agent: *",
		"Disallow: /admin/",
		"Disallow: /wagtail/",
		"Disallow: /me/",
		"Disallow: /accounts/",
		"Disallow: /_fragments/",
		"Disallow: /_styleguide/",
		"Disallow: /search/",
		"Sitemap: " + s.siteURL + "/sitemap.xml",
		"",
	}, "\n")
}

// WithTestEnvironment 标记测试站（robots 整站不让抓）。
func (s *Service) WithTestEnvironment(on bool) *Service {
	s.testEnvironment = on
	return s
}

// ServeSitemap 是 GET /sitemap.xml。
func (m *Module) ServeSitemap(w http.ResponseWriter, r *http.Request) {
	body, err := m.svc.GenerateSitemap(r.Context(), time.Now())
	if err != nil {
		http.Error(w, "服务器开小差了，稍后再试", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/xml; charset=utf-8")
	w.Header().Set("Content-Length", strconv.Itoa(len(body)))
	_, _ = w.Write([]byte(body))
}

// ServeRobots 是 GET /robots.txt。
func (m *Module) ServeRobots(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	_, _ = w.Write([]byte(m.svc.GenerateRobots()))
}
