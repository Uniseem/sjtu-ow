package content

import (
	"context"
	"encoding/xml"
	"fmt"
	"strings"
	"time"
)

type urlSet struct {
	XMLName xml.Name `xml:"http://www.sitemaps.org/schemas/sitemap/0.9 urlset"`
	URLs    []urlEntry
}

type urlEntry struct {
	XMLName xml.Name `xml:"url"`
	Loc     string   `xml:"loc"`
	LastMod string   `xml:"lastmod,omitempty"`
}

// GenerateSitemap 生成符合 sitemap 规范的 XML 字符串（只包含公开 live 的页面和文章）。
func (s *Service) GenerateSitemap(ctx context.Context) (string, error) {
	rows, err := s.store.d.ReadPool().QueryContext(ctx, `
		SELECT kind, slug, IFNULL(last_published_at, updated_at) as mod_time
		FROM pages
		WHERE live = 1
		ORDER BY id ASC
	`)
	if err != nil {
		return "", err
	}
	defer rows.Close()

	var urls []urlEntry

	// 首页与固定路由
	urls = append(urls,
		urlEntry{Loc: s.siteURL + "/"},
		urlEntry{Loc: s.siteURL + "/news"},
		urlEntry{Loc: s.siteURL + "/teams"},
		urlEntry{Loc: s.siteURL + "/tournaments"},
		urlEntry{Loc: s.siteURL + "/scrims"},
		urlEntry{Loc: s.siteURL + "/members"},
	)

	for rows.Next() {
		var kind, slug, modTime string
		if err := rows.Scan(&kind, &slug, &modTime); err != nil {
			return "", err
		}

		var loc string
		switch kind {
		case KindArticle:
			loc = fmt.Sprintf("%s/news/%s", s.siteURL, slug)
		case KindSitePage:
			loc = fmt.Sprintf("%s/%s", s.siteURL, slug)
		default:
			continue
		}

		var lastMod string
		if t, err := time.Parse(time.RFC3339Nano, modTime); err == nil {
			lastMod = t.Format("2006-01-02")
		}

		urls = append(urls, urlEntry{
			Loc:     loc,
			LastMod: lastMod,
		})
	}

	doc := urlSet{URLs: urls}
	out, err := xml.MarshalIndent(doc, "", "  ")
	if err != nil {
		return "", err
	}
	return xml.Header + string(out), nil
}

// GenerateRobots 生成 robots.txt 文本。
func (s *Service) GenerateRobots() string {
	var sb strings.Builder
	sb.WriteString("User-agent: *\n")
	sb.WriteString("Disallow: /admin/\n")
	sb.WriteString("Disallow: /api/\n")
	sb.WriteString("Disallow: /auth/\n")
	sb.WriteString("Disallow: /me/\n")
	sb.WriteString(fmt.Sprintf("Sitemap: %s/sitemap.xml\n", s.siteURL))
	return sb.String()
}
