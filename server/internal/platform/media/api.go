package media

import (
	"net/http"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责媒体域接口路由。
type Module struct {
	svc *Service
}

// NewModule 创建媒体域模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// UploadImageIn 是 POST /api/images 的入参（纯 JSON 描述；文件上传由专用 Handler 或 Multipart 解析）。
type UploadImageIn struct {
	Title         string `json:"title"`
	CollectionKey string `json:"collection_key"`
	FileName      string `json:"file_name"`
	DataURL       string `json:"data_url"` // 支持 base64 或常规上传
}

// UploadImageOut 是 POST /api/images 的出参。
type UploadImageOut struct {
	Image *Image `json:"image"`
}

// GetThumbnailIn 是 GET /api/media/r/{id}/{spec} 的入参。
type GetThumbnailIn struct {
	ID   api.ID `path:"id"`
	Spec string `path:"spec"`
}

// GetThumbnailOut 是 GET /api/media/r/{id}/{spec} 的出参。
type GetThumbnailOut struct {
	URL string `json:"url"`
}

// Routes 注册媒体域相关接口。
func (m *Module) Routes(r *api.Registry) {
	// 图片信息读取与缩略图生成探针
	api.Get(r, "/api/images/{id}", api.Public, m.getImage)
	api.Delete(r, "/api/images/{id}", api.Cap(app.Cap("images.manage")), m.deleteImage,
		api.NoLimit("管理员删除图片无需限流"))
	api.Get(r, "/api/media/r/{id}/{spec}", api.Public, m.getThumbnail)
}

func (m *Module) getImage(ctx *app.Ctx, in struct {
	ID api.ID `path:"id"`
}) (*Image, error) {
	return m.svc.GetImageByID(ctx.Context, int64(in.ID))
}

func (m *Module) deleteImage(ctx *app.Ctx, in struct {
	ID api.ID `path:"id"`
}) (struct {
	Result string `json:"result"`
}, error) {
	if err := m.svc.DeleteImage(ctx, int64(in.ID)); err != nil {
		return struct {
			Result string `json:"result"`
		}{}, err
	}
	return struct {
		Result string `json:"result"`
	}{Result: "ok"}, nil
}

func (m *Module) getThumbnail(ctx *app.Ctx, in GetThumbnailIn) (GetThumbnailOut, error) {
	path, err := m.svc.RenderThumbnail(ctx.Context, int64(in.ID), in.Spec)
	if err != nil {
		return GetThumbnailOut{}, err
	}
	return GetThumbnailOut{URL: path}, nil
}

// ServeThumbnailHTTP 提供直接响应图片二进制的 HTTP Handler（供 Caddy 缺失回源）。
func (m *Module) ServeThumbnailHTTP(w http.ResponseWriter, r *http.Request, id int64, spec string) {
	path, err := m.svc.RenderThumbnail(r.Context(), id, spec)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	w.Header().Set("Content-Type", "image/webp")
	w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	http.ServeFile(w, r, path)
}
