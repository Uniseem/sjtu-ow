package content

import (
	"net/http"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func (m *Module) registerContentEditing(r *api.Registry) {
	api.Get(r, "/api/admin/articles/new", api.Cap("admin.enter"), m.newArticleEditor, api.Nav("content", "articles"))
	api.Get(r, "/api/admin/articles/{id}/revisions", api.Cap("admin.enter"), m.articleRevisions, api.Nav("content", "articles"))
	api.Get(r, "/api/admin/articles/{id}/revisions/{revision}", api.Cap("admin.enter"), m.articleRevision, api.Nav("content", "articles"))
	api.Post(r, "/api/admin/articles/{id}/revisions/{revision}/restore", api.Cap("admin.enter"), m.restoreRevision,
		api.Nav("content", "articles"), api.NoLimit("恢复已有修订为草稿"))
	api.Post(r, "/api/admin/markdown/preview", api.Cap(app.Cap("admin.enter")), m.markdownPreview,
		api.Nav("content", "articles"), api.NoLimit("预览缓存有总量和正文大小限制"))
	api.Raw(r, http.MethodGet, "/api/admin/previews/{token}", nil, m.serveMarkdownPreview)
	api.Raw(r, http.MethodGet, "/api/admin/articles/{id}/preview", nil, m.serveArticlePreview)
	api.Get(r, "/api/admin/articles/{id}/preview-page", api.Cap("admin.enter"), m.articlePreviewPage, api.Nav("content", "articles"))
	api.Get(r, "/api/admin/pages", api.Cap(CapSitePagesManage), m.listSiteParts, api.Nav("content", "pages"))
	api.Get(r, "/api/admin/pages/{id}", api.Cap(CapSitePagesManage), m.readPlainPage, api.Nav("content", "pages"))
	api.Patch(r, "/api/admin/pages/{id}", api.Cap(CapSitePagesManage), m.patchPlainPage,
		api.Nav("content", "pages"), api.NoLimit("普通页自动保存由客户端防抖"))
	api.Post(r, "/api/admin/pages/{id}/publish", api.Cap(CapSitePagesManage), m.publishPlainPage,
		api.Nav("content", "pages"), api.NoLimit("发布网站页面"))
	api.Raw(r, http.MethodGet, "/api/admin/pages/{id}/preview", nil, m.servePlainPagePreview)
	api.Get(r, "/api/admin/home-pins/draft", api.Cap(CapSitePagesManage), m.readHomeDraft, api.Nav("content", "pages"))
	api.Patch(r, "/api/admin/home-pins/draft", api.Cap(CapSitePagesManage), m.patchHomeDraft,
		api.Nav("content", "pages"), api.NoLimit("首页置顶自动保存由客户端防抖"))
	api.Post(r, "/api/admin/home-pins/publish", api.Cap(CapSitePagesManage), m.publishHomeDraft,
		api.Nav("content", "pages"), api.NoLimit("发布首页置顶"))
	api.Raw(r, http.MethodGet, "/api/admin/home-pins/preview", nil, m.serveHomePreview)
	api.Get(r, "/api/admin/news-intro", api.Cap(CapSitePagesManage), m.readNewsDraft, api.Nav("content", "pages"))
	api.Patch(r, "/api/admin/news-intro", api.Cap(CapSitePagesManage), m.patchNewsDraft,
		api.Nav("content", "pages"), api.NoLimit("资讯栏目介绍自动保存由客户端防抖"))
	api.Post(r, "/api/admin/news-intro/publish", api.Cap(CapSitePagesManage), m.publishNewsDraft,
		api.Nav("content", "pages"), api.NoLimit("发布资讯栏目介绍"))
	api.Raw(r, http.MethodGet, "/api/admin/news-intro/preview", nil, m.serveNewsPreview)
}
