package content

import (
	"context"
	"database/sql"
	"errors"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

type NewsCategoryOut struct {
	Slug string `json:"slug"`
	Name string `json:"name"`
}

func (s *Service) NewsPage(ctx *app.Ctx, in NewsListIn) (NewsListOut, error) {
	var indexID int64
	var intro, title, seo, description string
	err := s.store.d.ReadPool().QueryRowContext(ctx.Context, `SELECT p.id,n.intro,p.title,p.seo_title,p.search_description FROM pages p JOIN news_index n ON n.page_id=p.id
 WHERE p.kind='news_index' AND p.slug='news' AND p.live=1 AND p.search_public=1`).Scan(&indexID, &intro, &title, &seo, &description)
	if errors.Is(err, sql.ErrNoRows) {
		return NewsListOut{}, api.NotFound("页面不存在")
	}
	if err != nil {
		return NewsListOut{}, err
	}
	categories, err := s.store.newsCategories(ctx.Context)
	if err != nil {
		return NewsListOut{}, err
	}
	html, _, err := markdown.Render(intro, s.siteURL, nil)
	if err != nil {
		return NewsListOut{}, err
	}
	pageSize := in.PageSize
	if pageSize < 1 || pageSize > 50 {
		pageSize = 12
	}
	category := strings.TrimSpace(in.Category)
	where := `p.kind='article' AND p.live=1 AND p.search_public=1 AND p.parent_id=?`
	args := []any{indexID}
	if category != "" {
		where += ` AND c.slug=?`
		args = append(args, category)
	}
	var total int
	err = s.store.d.ReadPool().QueryRowContext(ctx.Context, `SELECT COUNT(*) FROM pages p JOIN articles a ON a.page_id=p.id LEFT JOIN article_categories c ON c.id=a.category_id WHERE `+where, args...).Scan(&total)
	if err != nil {
		return NewsListOut{}, err
	}
	lastPage := max(1, (total+pageSize-1)/pageSize)
	page := in.Page
	if page == 0 {
		page = 1
	}
	if page < 1 || page > lastPage {
		page = lastPage
	}
	rows, err := s.store.d.ReadPool().QueryContext(ctx.Context, `SELECT `+articleColumns+` FROM pages p JOIN articles a ON a.page_id=p.id
 LEFT JOIN article_categories c ON c.id=a.category_id LEFT JOIN users u ON u.id=a.author_id WHERE `+where+`
 ORDER BY `+utcTimeOrder("p.first_published_at")+` DESC,`+utcTimeOrder("p.last_published_at")+` DESC,p.id ASC LIMIT ? OFFSET ?`, append(args, pageSize, (page-1)*pageSize)...)
	if err != nil {
		return NewsListOut{}, err
	}
	articles := []*Article{}
	for rows.Next() {
		item, err := scanArticle(rows)
		if err != nil {
			_ = rows.Close()
			return NewsListOut{}, err
		}
		articles = append(articles, item)
	}
	err = rows.Err()
	_ = rows.Close()
	if err != nil {
		return NewsListOut{}, err
	}
	pool, err := media.LoadPool(ctx.Context, s.store.d.ReadPool(), "default_cover")
	if err != nil {
		return NewsListOut{}, err
	}
	items, err := s.store.newsItems(ctx.Context, articles, pool)
	if err != nil {
		return NewsListOut{}, err
	}
	return NewsListOut{Total: total, Page: page, PageSize: pageSize, Items: items, Categories: categories, IntroHTML: html, Title: title, SeoTitle: seo, SearchDescription: description}, nil
}

func (s *Store) newsCategories(ctx context.Context) ([]NewsCategoryOut, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT slug,name FROM article_categories WHERE name<>'' AND slug<>'' ORDER BY sort_order,name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []NewsCategoryOut{}
	for rows.Next() {
		var item NewsCategoryOut
		if err := rows.Scan(&item.Slug, &item.Name); err != nil {
			return nil, err
		}
		out = append(out, item)
	}
	return out, rows.Err()
}
