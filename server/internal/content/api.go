package content

import (
	"net/http"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
)

// Module 负责内容域 HTTP 接口注册与协调。
type Module struct {
	svc *Service
}

// NewModule 创建内容域模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// NewsListIn 是 GET /api/page/news 的入参。
type NewsListIn struct {
	Category string `query:"category"`
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
}

// NewsItemOut 是文章列表项。
type NewsItemOut struct {
	ID               int64      `json:"id"`
	Slug             string     `json:"slug"`
	Title            string     `json:"title"`
	CategoryName     string     `json:"category_name"`
	CoverImageID     *int64     `json:"cover_image_id,omitempty"`
	Summary          string     `json:"summary"`
	ReadingTime      int        `json:"reading_time"`
	AuthorName       string     `json:"author_name"`
	FirstPublishedAt *time.Time `json:"first_published_at,omitempty"`
	Pinned           bool       `json:"pinned,omitempty"`
}

// NewsListOut 是 GET /api/page/news 的出参。
type NewsListOut struct {
	Total    int            `json:"total"`
	Page     int            `json:"page"`
	PageSize int            `json:"page_size"`
	Items    []*NewsItemOut `json:"items"`
}

// NewsDetailIn 是 GET /api/page/news/{slug} 的入参。
type NewsDetailIn struct {
	Slug string `path:"slug"`
}

// HeadingOut 是文章目录标题节点。
type HeadingOut struct {
	Level int    `json:"level"`
	Text  string `json:"text"`
	ID    string `json:"id"`
}

// NewsDetailOut 是 GET /api/page/news/{slug} 的出参。
type NewsDetailOut struct {
	ID                  int64         `json:"id"`
	Slug                string        `json:"slug"`
	Title               string        `json:"title"`
	CategoryName        string        `json:"category_name"`
	CoverImageID        *int64        `json:"cover_image_id,omitempty"`
	Summary             string        `json:"summary"`
	BodyHTML            string        `json:"body_html"`
	CharCount           int           `json:"char_count"`
	ReadingTime         int           `json:"reading_time"`
	AuthorName          string        `json:"author_name"`
	CommentsEnabled     bool          `json:"comments_enabled"`
	RelatedTournamentID *int64        `json:"related_tournament_id,omitempty"`
	FirstPublishedAt    *time.Time    `json:"first_published_at,omitempty"`
	Headings            []*HeadingOut `json:"headings"`
}

// SitePageIn 是 GET /api/page/{slug} 的入参。
type SitePageIn struct {
	Slug string `path:"slug"`
}

// SitePageOut 是 GET /api/page/{slug} 的出参。
type SitePageOut struct {
	Slug     string `json:"slug"`
	Title    string `json:"title"`
	BodyHTML string `json:"body_html"`
}

// AdminArticleDetailIn 是 GET /api/admin/articles/{id} 的入参。
type AdminArticleDetailIn struct {
	ID api.ID `path:"id"`
}

// AdminArticleDetailOut 是 GET /api/admin/articles/{id} 的出参。
type AdminArticleDetailOut struct {
	Article  *Article                `json:"article"`
	Revision *ArticleRevisionContent `json:"revision,omitempty"`
	Version  int64                   `json:"version"`
}

// AdminListArticlesIn 是 GET /api/admin/articles 的入参。
type AdminListArticlesIn struct {
	Category string `query:"category"`
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
}

// AdminListArticlesOut 是 GET /api/admin/articles 的出参。
type AdminListArticlesOut struct {
	Total    int        `json:"total"`
	Page     int        `json:"page"`
	PageSize int        `json:"page_size"`
	Items    []*Article `json:"items"`
}

// CategoryListIn 是 GET /api/admin/categories 的入参（空）。
type CategoryListIn struct{}

// CategoryListOut 是 GET /api/admin/categories 的出参。
type CategoryListOut struct {
	Items []*Category `json:"items"`
}

// CreateCategoryIn 是 POST /api/admin/categories 的入参。
type CreateCategoryIn struct {
	Name            string `json:"name"`
	Slug            string `json:"slug"`
	Description     string `json:"description"`
	SortOrder       int    `json:"sort_order"`
	AllowSubmission bool   `json:"allow_submission"`
}

// CreateCategoryOut 是 POST /api/admin/categories 的出参。
type CreateCategoryOut struct {
	Category *Category `json:"category"`
}

// UpdateCategoryIn 是 PATCH /api/admin/categories/{id} 的入参。
type UpdateCategoryIn struct {
	ID              api.ID `path:"id"`
	Name            string `json:"name"`
	Slug            string `json:"slug"`
	Description     string `json:"description"`
	SortOrder       int    `json:"sort_order"`
	AllowSubmission bool   `json:"allow_submission"`
	Version         int64  `json:"version"`
}

// UpdateCategoryOut 是 PATCH /api/admin/categories/{id} 的出参。
type UpdateCategoryOut struct {
	Category *Category `json:"category"`
}

// DeleteCategoryIn 是 DELETE /api/admin/categories/{id} 的入参。
type DeleteCategoryIn struct {
	ID api.ID `path:"id"`
}

// DeleteCategoryOut 是 DELETE /api/admin/categories/{id} 的出参。
type DeleteCategoryOut struct {
	Result string `json:"result"`
}

// HomePinsIn 是 GET /api/home-pins 的入参（空）。
type HomePinsIn struct{}

// HomePinsOut 是 GET /api/home-pins 的出参。
type HomePinsOut struct {
	Items []*NewsItemOut `json:"items"`
}

// SetHomePinsIn 是 PUT /api/admin/home-pins 的入参。
type SetHomePinsIn struct {
	ArticleIDs []int64 `json:"article_ids"`
}

// SetHomePinsOut 是 PUT /api/admin/home-pins 的出参。
type SetHomePinsOut struct {
	Result string `json:"result"`
}

// CreateArticleIn 是 POST /api/articles 的入参。
type CreateArticleIn = CreateDraftInput

// CreateArticleOut 是 POST /api/articles 的出参。
type CreateArticleOut = CreateDraftResult

// PatchArticleIn 是 PATCH /api/articles/{id} 的入参。
type PatchArticleIn struct {
	ID          api.ID                 `path:"id"`
	BaseVersion int64                  `json:"base_version"`
	Changes     map[string]interface{} `json:"changes"`
}

// PatchArticleOut 是 PATCH /api/articles/{id} 的出参。
type PatchArticleOut = SaveDraftResult

// PublishArticleIn 是 POST /api/articles/{id}/publish 的入参。
type PublishArticleIn struct {
	ID          api.ID `path:"id"`
	BaseVersion int64  `json:"base_version"`
}

// PublishArticleOut 是 POST /api/articles/{id}/publish 的出参。
type PublishArticleOut struct {
	Article *Article `json:"article"`
}

// UnpublishArticleIn 是 POST /api/articles/{id}/unpublish 的入参。
type UnpublishArticleIn struct {
	ID api.ID `path:"id"`
}

// UnpublishArticleOut 是 POST /api/articles/{id}/unpublish 的出参。
type UnpublishArticleOut struct {
	Result string `json:"result"`
}

// DeleteArticleIn 是 DELETE /api/articles/{id} 的入参。
type DeleteArticleIn struct {
	ID api.ID `path:"id"`
}

// DeleteArticleOut 是 DELETE /api/articles/{id} 的出参。
type DeleteArticleOut struct {
	Result string `json:"result"`
}

// Routes 注册内容域所有接口。
func (m *Module) Routes(r *api.Registry) {
	// 公开页面接口
	// 站点地图和 robots 照旧站的地址（frontend-migration B2）。
	api.Raw(r, http.MethodGet, "/sitemap.xml", nil, m.ServeSitemap)
	api.Raw(r, http.MethodGet, "/robots.txt", nil, m.ServeRobots)
	api.Get(r, "/api/page/home", api.Public, m.getHomePage)
	api.Get(r, "/api/page/news", api.Public, m.listNews)
	api.Get(r, "/api/page/news/{slug}", api.Public, m.getNewsDetail)
	api.Get(r, "/api/page/{slug}", api.Public, m.getSitePage)
	api.Get(r, "/api/home-pins", api.Public, m.getHomePins)

	// 会员/作者操作
	api.Post(r, "/api/articles", api.Member, m.createArticle,
		api.NoLimit("创建草稿无需限流"))
	api.Patch(r, "/api/articles/{id}", api.Member, m.patchArticle,
		api.NoLimit("自动保存由防抖控制"))
	api.Post(r, "/api/articles/{id}/publish", api.Member, m.publishArticle,
		api.NoLimit("发布文章无需限流"))
	api.Post(r, "/api/articles/{id}/unpublish", api.Member, m.unpublishArticle,
		api.NoLimit("撤下文章无需限流"))
	api.Delete(r, "/api/articles/{id}", api.Member, m.deleteArticle,
		api.NoLimit("删除文章无需限流"))

	// 后台管理
	api.Get(r, "/api/admin/articles", api.Cap(app.Cap("admin.enter")), m.adminListArticles,
		api.Nav("content", "articles"))
	api.Get(r, "/api/admin/articles/{id}", api.Cap(app.Cap("admin.enter")), m.adminGetArticleDetail,
		api.Nav("content", "article_edit"))

	// 分类管理
	api.Get(r, "/api/admin/categories", api.Cap(app.Cap("admin.enter")), m.listCategories,
		api.Nav("content", "categories"))
	api.Post(r, "/api/admin/categories", api.Cap(CapCategoriesManage), m.createCategory,
		api.NoLimit("创建分类无需限流"))
	api.Patch(r, "/api/admin/categories/{id}", api.Cap(CapCategoriesManage), m.updateCategory,
		api.NoLimit("修改分类无需限流"))
	api.Delete(r, "/api/admin/categories/{id}", api.Cap(CapCategoriesManage), m.deleteCategory,
		api.NoLimit("删除分类无需限流"))

	// 首页置顶
	api.Get(r, "/api/admin/home-pins", api.Cap(app.Cap("admin.enter")), m.adminGetHomePins,
		api.Nav("content", "home_pins"))
	api.Put(r, "/api/admin/home-pins", api.Cap(CapArticlesEditAny), m.setHomePins,
		api.NoLimit("设置置顶无需限流"))
}

func (m *Module) listNews(ctx *app.Ctx, in NewsListIn) (NewsListOut, error) {
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 || pageSize > 50 {
		pageSize = 12
	}
	offset := (page - 1) * pageSize

	articles, total, err := m.svc.store.ListArticles(ctx.Context, in.Category, true, pageSize, offset)
	if err != nil {
		return NewsListOut{}, err
	}

	items := make([]*NewsItemOut, 0, len(articles))
	for _, a := range articles {
		items = append(items, &NewsItemOut{
			ID:               a.ID,
			Slug:             a.Slug,
			Title:            a.Title,
			CategoryName:     a.CategoryName,
			CoverImageID:     a.CoverImageID,
			Summary:          a.Summary,
			ReadingTime:      a.ReadingTime,
			AuthorName:       a.AuthorName,
			FirstPublishedAt: a.FirstPublishedAt,
		})
	}

	return NewsListOut{
		Total:    total,
		Page:     page,
		PageSize: pageSize,
		Items:    items,
	}, nil
}

func (m *Module) getNewsDetail(ctx *app.Ctx, in NewsDetailIn) (NewsDetailOut, error) {
	slug := in.Slug
	article, err := m.svc.store.GetArticleBySlug(ctx.Context, slug)
	if err != nil {
		return NewsDetailOut{}, err
	}
	if article == nil {
		return NewsDetailOut{}, api.NotFound("文章不存在")
	}

	// 权限检查：非公开文章仅作者或编辑可见
	if !article.Live {
		if !m.svc.canEditArticle(ctx.Viewer, &article.Page) {
			return NewsDetailOut{}, api.NotFound("文章不存在")
		}
	}

	// 提取标题结构（目录用）
	_, headings := markdown.AnchorHeadings(article.BodyHTML)
	headingOuts := make([]*HeadingOut, 0, len(headings))
	for _, h := range headings {
		headingOuts = append(headingOuts, &HeadingOut{
			Level: h.Level,
			Text:  h.Text,
			ID:    h.Anchor,
		})
	}

	return NewsDetailOut{
		ID:                  article.ID,
		Slug:                article.Slug,
		Title:               article.Title,
		CategoryName:        article.CategoryName,
		CoverImageID:        article.CoverImageID,
		Summary:             article.Summary,
		BodyHTML:            article.BodyHTML,
		CharCount:           article.CharCount,
		ReadingTime:         article.ReadingTime,
		AuthorName:          article.AuthorName,
		CommentsEnabled:     article.CommentsEnabled,
		RelatedTournamentID: article.RelatedTournamentID,
		FirstPublishedAt:    article.FirstPublishedAt,
		Headings:            headingOuts,
	}, nil
}

func (m *Module) getSitePage(ctx *app.Ctx, in SitePageIn) (SitePageOut, error) {
	sp, err := m.svc.store.GetSitePageBySlug(ctx.Context, in.Slug)
	if err != nil {
		return SitePageOut{}, err
	}
	if sp == nil || !sp.Live {
		return SitePageOut{}, api.NotFound("页面不存在")
	}
	return SitePageOut{
		Slug:     sp.Slug,
		Title:    sp.Title,
		BodyHTML: sp.BodyHTML,
	}, nil
}

func (m *Module) getHomePins(ctx *app.Ctx, _ HomePinsIn) (HomePinsOut, error) {
	pins, err := m.svc.store.GetHomePins(ctx.Context)
	if err != nil {
		return HomePinsOut{}, err
	}
	items := make([]*NewsItemOut, 0, len(pins))
	for _, p := range pins {
		if p.Article != nil {
			items = append(items, &NewsItemOut{
				ID:               p.Article.ID,
				Slug:             p.Article.Slug,
				Title:            p.Article.Title,
				CategoryName:     p.Article.CategoryName,
				CoverImageID:     p.Article.CoverImageID,
				Summary:          p.Article.Summary,
				ReadingTime:      p.Article.ReadingTime,
				AuthorName:       p.Article.AuthorName,
				FirstPublishedAt: p.Article.FirstPublishedAt,
			})
		}
	}
	return HomePinsOut{Items: items}, nil
}

func (m *Module) createArticle(ctx *app.Ctx, in CreateArticleIn) (CreateArticleOut, error) {
	res, err := m.svc.CreateDraft(ctx, in)
	if err != nil {
		return CreateArticleOut{}, err
	}
	return *res, nil
}

func (m *Module) patchArticle(ctx *app.Ctx, in PatchArticleIn) (PatchArticleOut, error) {
	res, err := m.svc.SaveDraft(ctx, int64(in.ID), SaveDraftInput{
		BaseVersion: in.BaseVersion,
		Changes:     in.Changes,
	})
	if err != nil {
		return PatchArticleOut{}, err
	}
	return *res, nil
}

func (m *Module) publishArticle(ctx *app.Ctx, in PublishArticleIn) (PublishArticleOut, error) {
	a, err := m.svc.Publish(ctx, int64(in.ID), PublishInput{BaseVersion: in.BaseVersion})
	if err != nil {
		return PublishArticleOut{}, err
	}
	return PublishArticleOut{Article: a}, nil
}

func (m *Module) unpublishArticle(ctx *app.Ctx, in UnpublishArticleIn) (UnpublishArticleOut, error) {
	if err := m.svc.Unpublish(ctx, int64(in.ID)); err != nil {
		return UnpublishArticleOut{}, err
	}
	return UnpublishArticleOut{Result: "ok"}, nil
}

func (m *Module) deleteArticle(ctx *app.Ctx, in DeleteArticleIn) (DeleteArticleOut, error) {
	if err := m.svc.Delete(ctx, int64(in.ID)); err != nil {
		return DeleteArticleOut{}, err
	}
	return DeleteArticleOut{Result: "ok"}, nil
}

func (m *Module) adminListArticles(ctx *app.Ctx, in AdminListArticlesIn) (AdminListArticlesOut, error) {
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}
	offset := (page - 1) * pageSize

	articles, total, err := m.svc.store.ListArticles(ctx.Context, in.Category, false, pageSize, offset)
	if err != nil {
		return AdminListArticlesOut{}, err
	}

	return AdminListArticlesOut{
		Total:    total,
		Page:     page,
		PageSize: pageSize,
		Items:    articles,
	}, nil
}

func (m *Module) adminGetArticleDetail(ctx *app.Ctx, in AdminArticleDetailIn) (AdminArticleDetailOut, error) {
	pageID := int64(in.ID)
	a, err := m.svc.store.GetArticleByID(ctx.Context, pageID)
	if err != nil {
		return AdminArticleDetailOut{}, err
	}
	if a == nil {
		return AdminArticleDetailOut{}, api.NotFound("文章不存在")
	}

	rev, err := m.svc.store.GetLatestRevision(ctx.Context, pageID)
	if err != nil {
		return AdminArticleDetailOut{}, err
	}

	var revContent *ArticleRevisionContent
	var ver int64 = a.Version
	if rev != nil {
		ver = rev.ID
	}

	return AdminArticleDetailOut{
		Article:  a,
		Revision: revContent,
		Version:  ver,
	}, nil
}

func (m *Module) listCategories(ctx *app.Ctx, _ CategoryListIn) (CategoryListOut, error) {
	cats, err := m.svc.store.ListCategories(ctx.Context)
	if err != nil {
		return CategoryListOut{}, err
	}
	return CategoryListOut{Items: cats}, nil
}

func (m *Module) createCategory(ctx *app.Ctx, in CreateCategoryIn) (CreateCategoryOut, error) {
	c := &Category{
		Name:            in.Name,
		Slug:            in.Slug,
		Description:     in.Description,
		SortOrder:       in.SortOrder,
		AllowSubmission: in.AllowSubmission,
	}
	if err := m.svc.store.CreateCategory(ctx.Context, c); err != nil {
		return CreateCategoryOut{}, err
	}
	return CreateCategoryOut{Category: c}, nil
}

func (m *Module) updateCategory(ctx *app.Ctx, in UpdateCategoryIn) (UpdateCategoryOut, error) {
	c := &Category{
		ID:              int64(in.ID),
		Name:            in.Name,
		Slug:            in.Slug,
		Description:     in.Description,
		SortOrder:       in.SortOrder,
		AllowSubmission: in.AllowSubmission,
		Version:         in.Version,
	}
	if err := m.svc.store.UpdateCategory(ctx.Context, c); err != nil {
		return UpdateCategoryOut{}, err
	}
	return UpdateCategoryOut{Category: c}, nil
}

func (m *Module) deleteCategory(ctx *app.Ctx, in DeleteCategoryIn) (DeleteCategoryOut, error) {
	if err := m.svc.store.DeleteCategory(ctx.Context, int64(in.ID)); err != nil {
		return DeleteCategoryOut{}, err
	}
	return DeleteCategoryOut{Result: "ok"}, nil
}

func (m *Module) adminGetHomePins(ctx *app.Ctx, _ HomePinsIn) (HomePinsOut, error) {
	return m.getHomePins(ctx, HomePinsIn{})
}

func (m *Module) setHomePins(ctx *app.Ctx, in SetHomePinsIn) (SetHomePinsOut, error) {
	if err := m.svc.store.SetHomePins(ctx.Context, in.ArticleIDs); err != nil {
		return SetHomePinsOut{}, err
	}
	return SetHomePinsOut{Result: "ok"}, nil
}

func (m *Module) getHomePage(ctx *app.Ctx, _ HomePageIn) (*HomePageOut, error) {
	return m.svc.HomePage(ctx)
}
