package search

import (
	"context"
	"database/sql"
	"fmt"
	"regexp"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Compatibility lists remain until the frontend has switched to Groups.
type ArticleResult struct {
	ID               int64      `json:"id"`
	Slug             string     `json:"slug"`
	Title            string     `json:"title"`
	Summary          string     `json:"summary"`
	CategoryName     string     `json:"category_name"`
	FirstPublishedAt *time.Time `json:"first_published_at,omitempty"`
}
type TeamResult struct {
	ID          int64  `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
	Recruiting  bool   `json:"is_recruiting"`
}
type MemberResult struct {
	ID       int64  `json:"id"`
	Nickname string `json:"nickname"`
	Motto    string `json:"motto"`
}
type TournamentResult struct {
	ID      int64  `json:"id"`
	Title   string `json:"title"`
	Summary string `json:"summary"`
}
type ScrimResult struct {
	ID    int64  `json:"id"`
	Title string `json:"title"`
}

// Hit and Group mirror the old public search page, including empty groups.
type Hit struct {
	Title   string `json:"title"`
	URL     string `json:"url"`
	Excerpt string `json:"excerpt"`
	Meta    string `json:"meta"`
}
type Group struct {
	Key       string `json:"key"`
	Label     string `json:"label"`
	Hits      []Hit  `json:"hits"`
	Truncated bool   `json:"truncated"`
}
type Result struct {
	Query       string              `json:"query"`
	Groups      []Group             `json:"groups"`
	Articles    []*ArticleResult    `json:"articles"`
	Teams       []*TeamResult       `json:"teams"`
	Members     []*MemberResult     `json:"members"`
	Tournaments []*TournamentResult `json:"tournaments"`
	Scrims      []*ScrimResult      `json:"scrims"`
}

type Service struct{ d *db.DB }

func NewService(d *db.DB) *Service { return &Service{d: d} }

const perTypeLimit = 20

func queryWhitespace(r rune) bool { return unicode.IsSpace(r) || (r >= 0x1c && r <= 0x1f) }
func parseQuery(raw string) (string, []string) {
	q := []rune(strings.TrimFunc(raw, queryWhitespace))
	if len(q) > 50 {
		q = q[:50]
	}
	terms := strings.FieldsFunc(caseFold(string(q)), queryWhitespace)
	if len(terms) > 5 {
		terms = terms[:5]
	}
	return string(q), terms
}
func matches(text string, terms []string) bool {
	if len(terms) == 0 {
		return false
	}
	folded := caseFold(text)
	for _, term := range terms {
		if !strings.Contains(folded, term) {
			return false
		}
	}
	return true
}

var tags = regexp.MustCompile(`<[^>]*>`)

func excerpt(text string, terms []string) string {
	text = strings.Join(strings.FieldsFunc(tags.ReplaceAllString(text, ""), queryWhitespace), " ")
	runes := []rune(text)
	folded := caseFold(text)
	first := -1
	for _, term := range terms {
		if pos := strings.Index(folded, term); pos >= 0 {
			pos = utf8.RuneCountInString(folded[:pos])
			if first < 0 || pos < first {
				first = pos
			}
		}
	}
	start, end := 0, 80
	if first >= 0 {
		start, end = max(first-40, 0), first+40
	}
	end = min(end, len(runes))
	start = min(start, end)
	out := string(runes[start:end])
	if start > 0 {
		out = "…" + out
	}
	if end < len(runes) {
		out += "…"
	}
	return out
}
func (g *Group) add(hit Hit) {
	if len(g.Hits) < perTypeLimit {
		g.Hits = append(g.Hits, hit)
	} else {
		g.Truncated = true
	}
}

// walk propagates database errors and stops only after the 21st match.
func (s *Service) walk(ctx context.Context, query string, read func(*sql.Rows) (bool, error)) error {
	rows, err := s.d.ReadPool().QueryContext(ctx, query)
	if err != nil {
		return err
	}
	defer rows.Close()
	count := 0
	for rows.Next() {
		matched, err := read(rows)
		if err != nil {
			return err
		}
		if matched {
			count++
			if count > perTypeLimit {
				break
			}
		}
	}
	return rows.Err()
}

// Search reads saved plain text and applies the same Unicode case-folding as
// search/services.py; SQLite lower() only folds ASCII.
func (s *Service) Search(ctx context.Context, rawQuery string) (*Result, error) {
	q, terms := parseQuery(rawQuery)
	res := &Result{
		Query:    q,
		Groups:   []Group{{Key: "articles", Label: "文章", Hits: []Hit{}}, {Key: "events", Label: "赛事与内战", Hits: []Hit{}}, {Key: "teams", Label: "战队", Hits: []Hit{}}, {Key: "members", Label: "成员", Hits: []Hit{}}},
		Articles: []*ArticleResult{}, Teams: []*TeamResult{}, Members: []*MemberResult{}, Tournaments: []*TournamentResult{}, Scrims: []*ScrimResult{},
	}
	if len(terms) == 0 {
		return res, nil
	}
	err := s.walk(ctx, `SELECT p.id, p.slug, p.title, a.summary, a.body_plain, IFNULL(c.name, ''), p.first_published_at
        FROM pages p JOIN articles a ON a.page_id=p.id LEFT JOIN article_categories c ON c.id=a.category_id
        WHERE p.kind='article' AND p.live=1 AND p.search_public=1
        ORDER BY p.last_published_at DESC, p.id DESC`, func(rows *sql.Rows) (bool, error) {
		item := &ArticleResult{}
		var body string
		var first sql.NullString
		if err := rows.Scan(&item.ID, &item.Slug, &item.Title, &item.Summary, &body, &item.CategoryName, &first); err != nil {
			return false, err
		}
		text := item.Title + "\n" + item.Summary + "\n" + body
		if !matches(text, terms) {
			return false, nil
		}
		if first.Valid && first.String != "" {
			t, err := db.ParseUTC(first.String)
			if err != nil {
				return false, err
			}
			item.FirstPublishedAt = &t
		}
		meta := item.CategoryName
		if meta == "" {
			meta = "文章"
		}
		res.Groups[0].add(Hit{item.Title, "/news/" + item.Slug + "/", excerpt(text, terms), meta})
		if len(res.Articles) < perTypeLimit {
			res.Articles = append(res.Articles, item)
		}
		return true, nil
	})
	if err != nil {
		return nil, fmt.Errorf("搜索文章: %w", err)
	}
	err = s.walk(ctx, `SELECT id,title,summary,description_plain FROM tournaments WHERE status IN ('published','finished') ORDER BY updated_at DESC,id DESC`, func(rows *sql.Rows) (bool, error) {
		item := &TournamentResult{}
		var desc string
		if err := rows.Scan(&item.ID, &item.Title, &item.Summary, &desc); err != nil {
			return false, err
		}
		text := item.Title + "\n" + item.Summary + "\n" + desc
		if !matches(text, terms) {
			return false, nil
		}
		res.Groups[1].add(Hit{item.Title, fmt.Sprintf("/tournaments/%d/", item.ID), excerpt(text, terms), "赛事"})
		if len(res.Tournaments) < perTypeLimit {
			res.Tournaments = append(res.Tournaments, item)
		}
		return true, nil
	})
	if err != nil {
		return nil, fmt.Errorf("搜索赛事: %w", err)
	}
	err = s.walk(ctx, `SELECT id,title,description_plain FROM scrims WHERE status IN ('published','finished') ORDER BY updated_at DESC,id DESC`, func(rows *sql.Rows) (bool, error) {
		item := &ScrimResult{}
		var desc string
		if err := rows.Scan(&item.ID, &item.Title, &desc); err != nil {
			return false, err
		}
		text := item.Title + "\n\n" + desc
		if !matches(text, terms) {
			return false, nil
		}
		res.Groups[1].add(Hit{item.Title, fmt.Sprintf("/scrims/%d/", item.ID), excerpt(text, terms), "内战"})
		if len(res.Scrims) < perTypeLimit {
			res.Scrims = append(res.Scrims, item)
		}
		return true, nil
	})
	if err != nil {
		return nil, fmt.Errorf("搜索内战: %w", err)
	}
	err = s.walk(ctx, `SELECT id,name,description,is_recruiting FROM teams WHERE disbanded_at IS NULL ORDER BY updated_at DESC,id DESC`, func(rows *sql.Rows) (bool, error) {
		item := &TeamResult{}
		var recruiting int
		if err := rows.Scan(&item.ID, &item.Name, &item.Description, &recruiting); err != nil {
			return false, err
		}
		if !matches(item.Name+"\n"+item.Description, terms) {
			return false, nil
		}
		item.Recruiting = recruiting == 1
		meta := "战队"
		if item.Recruiting {
			meta = "招募中"
		}
		res.Groups[2].add(Hit{item.Name, fmt.Sprintf("/teams/%d/", item.ID), excerpt(item.Description, terms), meta})
		if len(res.Teams) < perTypeLimit {
			res.Teams = append(res.Teams, item)
		}
		return true, nil
	})
	if err != nil {
		return nil, fmt.Errorf("搜索战队: %w", err)
	}
	err = s.walk(ctx, `SELECT id,nickname,motto FROM users WHERE is_active=1 AND email_verified_at IS NOT NULL ORDER BY nickname,id`, func(rows *sql.Rows) (bool, error) {
		item := &MemberResult{}
		if err := rows.Scan(&item.ID, &item.Nickname, &item.Motto); err != nil {
			return false, err
		}
		if !matches(item.Nickname, terms) {
			return false, nil
		}
		res.Groups[3].add(Hit{item.Nickname, fmt.Sprintf("/members/%d/", item.ID), item.Motto, "成员"})
		if len(res.Members) < perTypeLimit {
			res.Members = append(res.Members, item)
		}
		return true, nil
	})
	if err != nil {
		return nil, fmt.Errorf("搜索成员: %w", err)
	}
	return res, nil
}
