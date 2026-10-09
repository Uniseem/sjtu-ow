package search

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ArticleResult 是文章搜索结果项。
type ArticleResult struct {
	ID               int64      `json:"id"`
	Slug             string     `json:"slug"`
	Title            string     `json:"title"`
	Summary          string     `json:"summary"`
	CategoryName     string     `json:"category_name"`
	FirstPublishedAt *time.Time `json:"first_published_at,omitempty"`
}

// TeamResult 是战队搜索结果项。
type TeamResult struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
	Bio  string `json:"bio"`
}

// TournamentResult 是赛事搜索结果项。
type TournamentResult struct {
	ID      int64  `json:"id"`
	Title   string `json:"title"`
	Summary string `json:"summary"`
}

// ScrimResult 是内战搜索结果项。
type ScrimResult struct {
	ID    int64  `json:"id"`
	Title string `json:"title"`
}

// Result 是全站搜索结果（规则 233）。
type Result struct {
	Query       string              `json:"query"`
	Articles    []*ArticleResult    `json:"articles"`
	Teams       []*TeamResult       `json:"teams"`
	Tournaments []*TournamentResult `json:"tournaments"`
	Scrims      []*ScrimResult      `json:"scrims"`
}

// Service 提供全站搜索服务。
type Service struct {
	d *db.DB
}

// NewService 创建搜索服务。
func NewService(d *db.DB) *Service {
	return &Service{d: d}
}

// hasTable 检查表是否存在。
func (s *Service) hasTable(ctx context.Context, tableName string) bool {
	var count int
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?`, tableName).Scan(&count)
	return err == nil && count > 0
}

// Search 执行纯子串大小写折叠搜索（规则 233，12 号文档 5.14）。
func (s *Service) Search(ctx context.Context, rawQuery string) (*Result, error) {
	q := strings.TrimSpace(rawQuery)
	if q == "" {
		return &Result{
			Query:       "",
			Articles:    []*ArticleResult{},
			Teams:       []*TeamResult{},
			Tournaments: []*TournamentResult{},
			Scrims:      []*ScrimResult{},
		}, nil
	}

	// 规则 233：查询 <= 50 字符
	if utf8.RuneCountInString(q) > 50 {
		return nil, api.Invalid("搜索关键词长度不能超过 50 个字符")
	}

	// 最多 5 个词
	words := strings.Fields(strings.ToLower(q))
	if len(words) > 5 {
		words = words[:5]
	}

	res := &Result{
		Query:       q,
		Articles:    []*ArticleResult{},
		Teams:       []*TeamResult{},
		Tournaments: []*TournamentResult{},
		Scrims:      []*ScrimResult{},
	}

	// 1. 搜索文章：live=1 且所有词满足 instr(search_text, 词) > 0（上限 20 条）
	if s.hasTable(ctx, "articles") {
		var whereClauses []string
		var args []any
		whereClauses = append(whereClauses, "p.live = 1", "p.kind = 'article'")
		for _, w := range words {
			whereClauses = append(whereClauses, "instr(a.search_text, ?) > 0")
			args = append(args, w)
		}
		query := fmt.Sprintf(`
			SELECT p.id, p.slug, p.title, a.summary, IFNULL(c.name, ''), p.first_published_at
			FROM pages p
			JOIN articles a ON a.page_id = p.id
			LEFT JOIN article_categories c ON c.id = a.category_id
			WHERE %s
			ORDER BY p.first_published_at DESC, p.id DESC
			LIMIT 20
		`, strings.Join(whereClauses, " AND "))

		rows, err := s.d.ReadPool().QueryContext(ctx, query, args...)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var item ArticleResult
				var firstPub sql.NullString
				if err := rows.Scan(&item.ID, &item.Slug, &item.Title, &item.Summary, &item.CategoryName, &firstPub); err == nil {
					if firstPub.Valid && firstPub.String != "" {
						t, _ := db.ParseUTC(firstPub.String)
						item.FirstPublishedAt = &t
					}
					res.Articles = append(res.Articles, &item)
				}
			}
		}
	}

	// 2. 搜索战队（若已建表，M5）：name 或 bio
	if s.hasTable(ctx, "teams") {
		var whereClauses []string
		var args []any
		whereClauses = append(whereClauses, "disbanded_at IS NULL")
		for _, w := range words {
			whereClauses = append(whereClauses, "(instr(lower(name), ?) > 0 OR instr(lower(bio), ?) > 0)")
			args = append(args, w, w)
		}
		query := fmt.Sprintf(`
			SELECT id, name, bio FROM teams
			WHERE %s
			ORDER BY id ASC
			LIMIT 20
		`, strings.Join(whereClauses, " AND "))
		rows, err := s.d.ReadPool().QueryContext(ctx, query, args...)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var item TeamResult
				if err := rows.Scan(&item.ID, &item.Name, &item.Bio); err == nil {
					res.Teams = append(res.Teams, &item)
				}
			}
		}
	}

	// 3. 搜索赛事（若已建表，M6）：title 或 summary
	if s.hasTable(ctx, "tournaments") {
		var whereClauses []string
		var args []any
		whereClauses = append(whereClauses, "status != 'draft'")
		for _, w := range words {
			whereClauses = append(whereClauses, "(instr(lower(title), ?) > 0 OR instr(lower(summary), ?) > 0)")
			args = append(args, w, w)
		}
		query := fmt.Sprintf(`
			SELECT id, title, summary FROM tournaments
			WHERE %s
			ORDER BY id DESC
			LIMIT 20
		`, strings.Join(whereClauses, " AND "))
		rows, err := s.d.ReadPool().QueryContext(ctx, query, args...)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var item TournamentResult
				if err := rows.Scan(&item.ID, &item.Title, &item.Summary); err == nil {
					res.Tournaments = append(res.Tournaments, &item)
				}
			}
		}
	}

	// 4. 搜索内战（若已建表，M6）：title
	if s.hasTable(ctx, "scrims") {
		var whereClauses []string
		var args []any
		whereClauses = append(whereClauses, "status != 'draft'")
		for _, w := range words {
			whereClauses = append(whereClauses, "instr(lower(title), ?) > 0")
			args = append(args, w)
		}
		query := fmt.Sprintf(`
			SELECT id, title FROM scrims
			WHERE %s
			ORDER BY id DESC
			LIMIT 20
		`, strings.Join(whereClauses, " AND "))
		rows, err := s.d.ReadPool().QueryContext(ctx, query, args...)
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var item ScrimResult
				if err := rows.Scan(&item.ID, &item.Title); err == nil {
					res.Scrims = append(res.Scrims, &item)
				}
			}
		}
	}

	return res, nil
}
