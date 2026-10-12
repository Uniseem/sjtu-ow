package content

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/comments"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
	"github.com/Uniseem/sjtu-ow/server/internal/tournaments"
)

// ArticleAuthorOut 只包含旧作者卡公开信息，停用作者不输出头像。
type ArticleAuthorOut struct {
	UserID        int64  `json:"user_id"`
	Nickname      string `json:"nickname"`
	AvatarImageID *int64 `json:"avatar_image_id"`
	IsActive      bool   `json:"is_active"`
	Motto         string `json:"motto"`
}

type ArticleNeighbourOut struct {
	Slug  string `json:"slug"`
	Title string `json:"title"`
}

// ArticleTournamentOut 与赛事卡读取的公开字段相同，不输出参与者联系方式。
type ArticleTournamentOut struct {
	ID                    int64      `json:"id"`
	Title                 string     `json:"title"`
	Phase                 string     `json:"phase"`
	StartsAt              *time.Time `json:"starts_at"`
	RegistrationOpensAt   *time.Time `json:"registration_opens_at"`
	RegistrationClosesAt  *time.Time `json:"registration_closes_at"`
	CoverImageID          *int64     `json:"cover_image_id"`
	DefaultCoverImageID   *int64     `json:"default_cover_image_id"`
	RosterMin             int        `json:"roster_min"`
	RosterMax             int        `json:"roster_max"`
	RegistrationModeLabel string     `json:"registration_mode_label"`
	TakesIndividuals      bool       `json:"takes_individuals"`
	SJTUOnly              bool       `json:"sjtu_only"`
}

// ArticlePage 在服务层组合文章页，HTTP 不再负责公开投影或查询。
func (s *Service) ArticlePage(ctx *app.Ctx, slug string) (NewsDetailOut, error) {
	article, err := s.store.GetArticleBySlug(ctx.Context, slug)
	if err != nil {
		return NewsDetailOut{}, err
	}
	if article == nil || !article.Live || !article.Public {
		return NewsDetailOut{}, api.NotFound("文章不存在")
	}
	return s.articleProjection(ctx, article)
}

// articleProjection is shared by public articles and authorized draft previews.
func (s *Service) articleProjection(ctx *app.Ctx, article *Article) (NewsDetailOut, error) {
	_, headings := markdown.AnchorHeadings(article.BodyHTML)
	headingOuts := make([]*HeadingOut, 0, len(headings))
	for _, h := range headings {
		headingOuts = append(headingOuts, &HeadingOut{Level: h.Level, Text: h.Text, ID: h.Anchor})
	}
	out := NewsDetailOut{
		ID: article.ID, Slug: article.Slug, Title: article.Title, CategoryName: article.CategoryName, CoverImageID: article.CoverImageID,
		Summary: article.Summary, BodyHTML: article.BodyHTML, CharCount: article.CharCount, ReadingTime: article.ReadingTime,
		AuthorName: article.AuthorName, CommentsEnabled: article.CommentsEnabled, RelatedTournamentID: article.RelatedTournamentID,
		FirstPublishedAt: article.FirstPublishedAt, Headings: headingOuts, LastPublishedAt: article.LastPublishedAt,
		SeoTitle: article.SeoTitle, SearchDescription: article.SearchDescription, Related: []*NewsItemOut{},
	}
	pool, err := media.LoadPool(ctx.Context, s.store.d.ReadPool(), "default_cover")
	if err != nil {
		return NewsDetailOut{}, err
	}
	out.DefaultCoverImageID = media.PickCover(pool, article.ID, 0)
	if article.CategoryID != nil {
		category, err := s.store.GetCategoryByID(ctx.Context, *article.CategoryID)
		if err != nil {
			return NewsDetailOut{}, err
		}
		if category != nil {
			out.CategorySlug = category.Slug
		}
	}
	out.Author, err = s.store.articleAuthor(ctx.Context, article.AuthorID)
	if err != nil {
		return NewsDetailOut{}, err
	}
	if article.AuthorID != nil {
		out.AuthorArticleCount, err = s.store.authorPublicArticleCount(ctx.Context, *article.AuthorID)
		if err != nil {
			return NewsDetailOut{}, err
		}
	}
	isMod := ctx.Viewer != nil && ctx.Viewer.ID > 0 && !ctx.Viewer.Disabled && ctx.Viewer.HasCap(comments.CapCommentsModerate)
	out.CommentTotal, err = comments.NewStore(s.store.d).CountRoots(ctx.Context, article.ID, isMod)
	if err != nil {
		return NewsDetailOut{}, err
	}
	if article.FirstPublishedAt != nil {
		out.Older, err = s.store.articleNeighbour(ctx.Context, article.ID, *article.FirstPublishedAt, false)
		if err != nil {
			return NewsDetailOut{}, err
		}
		out.Newer, err = s.store.articleNeighbour(ctx.Context, article.ID, *article.FirstPublishedAt, true)
		if err != nil {
			return NewsDetailOut{}, err
		}
	}
	related, err := s.store.relatedArticles(ctx.Context, article.ID, article.CategoryID)
	if err != nil {
		return NewsDetailOut{}, err
	}
	out.Related, err = s.store.newsItems(ctx.Context, related, pool)
	if err != nil {
		return NewsDetailOut{}, err
	}

	if article.RelatedTournamentID != nil {
		t, err := tournaments.GetTournament(ctx.Context, s.store.d.ReadPool(), *article.RelatedTournamentID)
		if err != nil {
			return NewsDetailOut{}, err
		}
		if t != nil && t.IsPublic() {
			label := "整队报名"
			if t.TakesIndividuals() {
				label = "个人报名"
			}
			out.Tournament = &ArticleTournamentOut{ID: t.ID, Title: t.Title, Phase: t.Phase(ctx.Now()), StartsAt: t.StartsAt,
				RegistrationOpensAt: t.RegistrationOpensAt, RegistrationClosesAt: t.RegistrationClosesAt, CoverImageID: t.CoverImageID,
				DefaultCoverImageID: media.PickCover(pool, t.ID, 13), RosterMin: t.RosterMin, RosterMax: t.RosterMax,
				RegistrationModeLabel: label, TakesIndividuals: t.TakesIndividuals(), SJTUOnly: t.SjtuOnly}
		}
	}
	return out, nil
}

func newsItem(a *Article, defaultCover *int64) *NewsItemOut {
	return &NewsItemOut{ID: a.ID, Slug: a.Slug, Title: a.Title, CategoryName: a.CategoryName, CoverImageID: a.CoverImageID,
		DefaultCoverImageID: defaultCover, Summary: a.Summary, ReadingTime: a.ReadingTime, AuthorName: a.AuthorName, FirstPublishedAt: a.FirstPublishedAt}
}

func (s *Store) articleAuthor(ctx context.Context, id *int64) (*ArticleAuthorOut, error) {
	if id == nil {
		return nil, nil
	}
	var out ArticleAuthorOut
	var active int
	var main, flex string
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT id,nickname,avatar_image_id,is_active,motto,main_role,flex_roles FROM users WHERE id=?`, *id).
		Scan(&out.UserID, &out.Nickname, &out.AvatarImageID, &active, &out.Motto, &main, &flex)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	out.IsActive = active == 1
	if !out.IsActive {
		out.AvatarImageID = nil
		return &out, nil
	}
	if out.AvatarImageID == nil {
		pool, err := media.LoadPool(ctx, s.d.ReadPool(), "default_avatar")
		if err != nil {
			return nil, err
		}
		if main == "" {
			roles := accounts.ParseRoles(flex)
			if len(roles) > 0 {
				main = roles[0]
			}
		}
		out.AvatarImageID = media.PickAvatar(pool, out.UserID, main)
	}
	return &out, nil
}

func (s *Store) authorPublicArticleCount(ctx context.Context, id int64) (int, error) {
	var count int
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM pages p JOIN articles a ON a.page_id=p.id
 WHERE p.live=1 AND p.is_public=1 AND a.author_id=?`, id).Scan(&count)
	return count, err
}

func (s *Store) articleNeighbour(ctx context.Context, id int64, first time.Time, newer bool) (*ArticleNeighbourOut, error) {
	comparison, order := "<", "DESC"
	if newer {
		comparison, order = ">", "ASC"
	}
	var out ArticleNeighbourOut
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT p.slug,p.title FROM pages p
 WHERE p.kind='article' AND p.live=1 AND p.is_public=1
 AND p.parent_id IS NOT NULL
 AND p.parent_id IS (SELECT parent_id FROM pages WHERE id=?)
 AND `+utcTimeOrder("p.first_published_at")+` `+comparison+` ?
 ORDER BY `+utcTimeOrder("p.first_published_at")+` `+order+`,p.id ASC LIMIT 1`, id, first.UTC().Format("2006-01-02T15:04:05.000000000")).Scan(&out.Slug, &out.Title)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &out, nil
}

func (s *Store) relatedArticles(ctx context.Context, id int64, category *int64) ([]*Article, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT `+articleColumns+`
 FROM pages p JOIN articles a ON a.page_id=p.id
 LEFT JOIN article_categories c ON c.id=a.category_id LEFT JOIN users u ON u.id=a.author_id
 WHERE p.live=1 AND p.is_public=1 AND a.category_id IS ? AND p.id<>?
 ORDER BY `+utcTimeOrder("p.first_published_at")+` DESC,`+utcTimeOrder("p.last_published_at")+` DESC,p.id ASC LIMIT 3`, category, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []*Article{}
	for rows.Next() {
		item, err := scanArticle(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

// UTC 字符串归一到九位小数排序：避免 julianday 丢失微秒，或 Z/.000000Z 词序不一致。
func utcTimeOrder(column string) string {
	return "substr(" + column + ",1,19) || '.' || substr(rtrim(substr(" + column + ",21),'Z') || '000000000',1,9)"
}
