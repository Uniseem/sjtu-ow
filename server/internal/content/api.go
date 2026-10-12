package content

import (
	"database/sql"
	"net/http"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/comments"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责内容域 HTTP 接口注册与协调。
type Module struct {
	svc               *Service
	previewResolver   api.ViewerResolver
	previewStylesheet string
	previews          contentPreviewCache
	comments          *comments.Service
}

func (m *Module) SetComments(service *comments.Service) { m.comments = service }

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

type StyleguideOut struct {
	ImageID *int64 `json:"image_id"`
}

func (m *Module) styleguide(ctx *app.Ctx, _ struct{}) (StyleguideOut, error) {
	// A published cover is public; no pending member avatar or private upload.
	var id int64
	err := m.svc.store.d.ReadPool().QueryRowContext(ctx.Context, `SELECT a.cover_image_id FROM articles a JOIN pages p ON p.id=a.page_id WHERE p.live=1 AND p.is_public=1 AND a.cover_image_id IS NOT NULL ORDER BY p.id LIMIT 1`).Scan(&id)
	if err == sql.ErrNoRows {
		return StyleguideOut{}, nil
	}
	if err != nil {
		return StyleguideOut{}, err
	}
	return StyleguideOut{ImageID: &id}, nil
}

// NewsItemOut 是文章列表项。
type NewsItemOut struct {
	ID                  int64          `json:"id"`
	Slug                string         `json:"slug"`
	Title               string         `json:"title"`
	CategoryName        string         `json:"category_name"`
	CoverImageID        *int64         `json:"cover_image_id,omitempty"`
	DefaultCoverImageID *int64         `json:"default_cover_image_id"`
	Summary             string         `json:"summary"`
	ReadingTime         int            `json:"reading_time"`
	AuthorName          string         `json:"author_name"`
	Author              *NewsAuthorOut `json:"author"`
	FirstPublishedAt    *time.Time     `json:"first_published_at,omitempty"`
	Pinned              bool           `json:"pinned,omitempty"`
}

// NewsListOut 是 GET /api/page/news 的出参。
type NewsListOut struct {
	Total             int               `json:"total"`
	Page              int               `json:"page"`
	PageSize          int               `json:"page_size"`
	Items             []*NewsItemOut    `json:"items"`
	Categories        []NewsCategoryOut `json:"categories"`
	IntroHTML         string            `json:"intro_html"`
	Title             string            `json:"title"`
	SeoTitle          string            `json:"seo_title"`
	SearchDescription string            `json:"search_description"`
}

// NewsDetailIn 是 GET /api/page/news/{slug} 的入参。
type NewsDetailIn struct {
	Slug     string `path:"slug"`
	Sort     string `query:"sort"`
	Comments int    `query:"comments"`
}

// HeadingOut 是文章目录标题节点。
type HeadingOut struct {
	Level int    `json:"level"`
	Text  string `json:"text"`
	ID    string `json:"id"`
}

// NewsDetailOut 是 GET /api/page/news/{slug} 的出参。
type NewsDetailOut struct {
	ID                  int64                        `json:"id"`
	Slug                string                       `json:"slug"`
	Title               string                       `json:"title"`
	CategoryName        string                       `json:"category_name"`
	CoverImageID        *int64                       `json:"cover_image_id,omitempty"`
	Summary             string                       `json:"summary"`
	BodyHTML            string                       `json:"body_html"`
	CharCount           int                          `json:"char_count"`
	ReadingTime         int                          `json:"reading_time"`
	AuthorName          string                       `json:"author_name"`
	CommentsEnabled     bool                         `json:"comments_enabled"`
	RelatedTournamentID *int64                       `json:"related_tournament_id,omitempty"`
	FirstPublishedAt    *time.Time                   `json:"first_published_at,omitempty"`
	Headings            []*HeadingOut                `json:"headings"`
	CategorySlug        string                       `json:"category_slug"`
	DefaultCoverImageID *int64                       `json:"default_cover_image_id"`
	Author              *ArticleAuthorOut            `json:"author"`
	AuthorArticleCount  int                          `json:"author_article_count"`
	LastPublishedAt     *time.Time                   `json:"last_published_at"`
	CommentTotal        int                          `json:"comment_total"`
	Older               *ArticleNeighbourOut         `json:"older"`
	Newer               *ArticleNeighbourOut         `json:"newer"`
	Related             []*NewsItemOut               `json:"related"`
	Tournament          *ArticleTournamentOut        `json:"tournament"`
	SeoTitle            string                       `json:"seo_title"`
	SearchDescription   string                       `json:"search_description"`
	Thread              *comments.ListCommentsResult `json:"thread,omitempty"`
}

// SitePageIn 是 GET /api/page/{slug} 的入参。
type SitePageIn struct {
	Slug string `path:"slug"`
}

// SitePageOut 是 GET /api/page/{slug} 的出参。
type SitePageOut struct {
	Slug              string     `json:"slug"`
	Title             string     `json:"title"`
	BodyHTML          string     `json:"body_html"`
	SeoTitle          string     `json:"seo_title"`
	SearchDescription string     `json:"search_description"`
	LastPublishedAt   *time.Time `json:"last_published_at"`
}

// AdminArticleDetailIn 是 GET /api/admin/articles/{id} 的入参。
type AdminArticleDetailIn struct {
	ID api.ID `path:"id"`
}

// AdminArticleDetailOut 是 GET /api/admin/articles/{id} 的出参。
type AdminArticleDetailOut struct {
	Capabilities ArticleCapabilities       `json:"capabilities"`
	Guide        bool                      `json:"guide"`
	Categories   []ArticleCategoryChoice   `json:"categories"`
	Authors      []ArticleAuthorChoice     `json:"authors"`
	Tournaments  []ArticleTournamentChoice `json:"tournaments"`
	PreviewURL   *string                   `json:"preview_url"`
	Announced    int                       `json:"announced"`
	Verdict      *ArticleVerdict           `json:"verdict"`
	Article      *Article                  `json:"article"`
	Revision     *ArticleRevisionContent   `json:"revision,omitempty"`
	Version      int64                     `json:"version"`
}

// AdminListArticlesIn 是 GET /api/admin/articles 的入参。
type AdminListArticlesIn struct {
	Q        string `query:"q"`
	Status   string `query:"status"`
	Mine     bool   `query:"mine"`
	Category string `query:"category"`
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
}

// AdminListArticlesOut 是 GET /api/admin/articles 的出参。
type AdminListArticlesOut struct {
	Categories []ArticleCategoryChoice `json:"categories,omitempty"`
	Total      int                     `json:"total"`
	Page       int                     `json:"page"`
	PageSize   int                     `json:"page_size"`
	Items      []*Article              `json:"items"`
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
	m.registerContentEditing(r)
	// 公开页面接口
	// 站点地图和 robots 照旧站的地址（frontend-migration B2）。
	api.Raw(r, http.MethodGet, "/sitemap.xml", nil, m.ServeSitemap)
	api.Raw(r, http.MethodGet, "/robots.txt", nil, m.ServeRobots)
	api.Get(r, "/api/page/home", api.Public, m.getHomePage)
	api.Get(r, "/api/page/styleguide", api.Cap("admin.enter"), m.styleguide)
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
	api.Get(r, "/api/admin/categories", api.Cap(CapCategoriesManage), m.listCategories,
		api.Nav("content", "categories"))
	api.Post(r, "/api/admin/categories", api.Cap(CapCategoriesManage), m.createCategory,
		api.NoLimit("创建分类无需限流"))
	api.Patch(r, "/api/admin/categories/{id}", api.Cap(CapCategoriesManage), m.updateCategory,
		api.NoLimit("修改分类无需限流"))
	api.Delete(r, "/api/admin/categories/{id}", api.Cap(CapCategoriesManage), m.deleteCategory,
		api.NoLimit("删除分类无需限流"))

	// 首页置顶
	api.Get(r, "/api/admin/home-pins", api.Cap(CapArticlesEditAny), m.adminGetHomePins,
		api.Nav("content", "home_pins"))
	api.Put(r, "/api/admin/home-pins", api.Cap(CapArticlesEditAny), m.setHomePins,
		api.NoLimit("设置置顶无需限流"))
}

func (m *Module) listNews(ctx *app.Ctx, in NewsListIn) (NewsListOut, error) {
	return m.svc.NewsPage(ctx, in)
}

func (m *Module) getNewsDetail(ctx *app.Ctx, in NewsDetailIn) (NewsDetailOut, error) {
	out, err := m.svc.ArticlePage(ctx, in.Slug)
	if err != nil || m.comments == nil {
		return out, err
	}
	out.Thread, err = m.comments.ListComments(ctx, out.ID, comments.ListCommentsInput{SortBy: in.Sort, Page: in.Comments, PageSize: 20})
	return out, err
}

func (m *Module) getSitePage(ctx *app.Ctx, in SitePageIn) (SitePageOut, error) {
	sp, err := m.svc.store.GetSitePageBySlug(ctx.Context, in.Slug)
	if err != nil {
		return SitePageOut{}, err
	}
	if sp == nil || !sp.Live || !sp.Public {
		return SitePageOut{}, api.NotFound("页面不存在")
	}
	return SitePageOut{
		Slug:              sp.Slug,
		Title:             sp.Title,
		BodyHTML:          sp.BodyHTML,
		SeoTitle:          sp.SeoTitle,
		SearchDescription: sp.SearchDescription,
		LastPublishedAt:   sp.LastPublishedAt,
	}, nil
}

func (m *Module) getHomePins(ctx *app.Ctx, _ HomePinsIn) (HomePinsOut, error) {
	return m.svc.HomePins(ctx, true)
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
	out, err := m.listEditableArticles(ctx, in)
	if err != nil {
		return out, err
	}
	choices, err := m.svc.store.ListCategories(ctx.Context)
	if err != nil {
		return out, err
	}
	for _, category := range choices {
		out.Categories = append(out.Categories, ArticleCategoryChoice{ID: category.ID, Name: category.Name, AllowSubmission: category.AllowSubmission})
	}
	return out, nil
}

func (m *Module) adminGetArticleDetail(ctx *app.Ctx, in AdminArticleDetailIn) (AdminArticleDetailOut, error) {
	article, err := m.authorizedArticle(ctx, int64(in.ID))
	if err != nil {
		return AdminArticleDetailOut{}, err
	}
	return m.editorProjection(ctx, article)
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
	if err := validateCategoryValues(c); err != nil {
		return CreateCategoryOut{}, err
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
	if err := validateCategoryValues(c); err != nil {
		return UpdateCategoryOut{}, err
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
	return m.svc.HomePins(ctx, false)
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
