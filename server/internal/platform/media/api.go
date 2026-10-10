package media

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strings"

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

// UploadImageIn 是 POST /api/admin/images/upload 的入参（支持 base64 或常规 DataURL）。
type UploadImageIn struct {
	Title         string `json:"title"`
	CollectionKey string `json:"collection_key"`
	FileName      string `json:"file_name"`
	DataURL       string `json:"data_url"`
}

// UploadImageOut 是 POST /api/admin/images/upload 的出参。
type UploadImageOut struct {
	Image *Image `json:"image"`
}

// ListImagesIn 是 GET /api/admin/images 的入参。
type ListImagesIn struct {
	CollectionKey string `query:"collection_key"`
	CollectionID  *int64 `query:"collection_id"`
	Q             string `query:"q"`
	Page          int    `query:"page"`
	PageSize      int    `query:"page_size"`
}

// ListImagesOut 是 GET /api/admin/images 的出参。
type ListImagesOut struct {
	Items    []Image `json:"items"`
	Total    int     `json:"total"`
	Page     int     `json:"page"`
	PageSize int     `json:"page_size"`
}

// ListCollectionsOut 是 GET /api/admin/image-collections 的出参。
type ListCollectionsOut struct {
	Collections []Collection `json:"collections"`
}

// Routes 注册媒体域相关接口。
func (m *Module) Routes(r *api.Registry) {
	// 图片信息读取
	api.Get(r, "/api/images/{id}", api.Public, m.getImage)
	api.Delete(r, "/api/images/{id}", api.Cap(app.Cap("images.manage")), m.deleteImage,
		api.NoLimit("管理员删除图片无需限流"))
	// 缩略图本身（12 号文档 3.4）：文件在 media 卷里就由 Caddy 直接给，不在才到这里
	// 现做。原来的 GET /api/media/r/{id}/{spec} 回的是 JSON 和服务器上的文件路径，
	// 前端没法当 <img src> 用，还把内部路径露了出去，去掉（frontend-migration S2、B1）。
	api.Raw(r, http.MethodGet, "/media/r/{id}/{file}", nil, m.ServeThumbnailHTTP)

	// 管理后台图片管理
	api.Get(r, "/api/admin/images", api.Cap(app.Cap("images.manage")), m.listImages,
		api.Nav("content", "images"))
	api.Get(r, "/api/admin/image-collections", api.Cap(app.Cap("images.manage")), m.listCollections,
		api.Nav("content", "images"))
	api.Post(r, "/api/admin/images/upload", api.Cap(app.Cap("images.contribute")), m.uploadImage,
		api.Nav("content", "images"), api.NoLimit("上传图片"))
	api.Raw(r, http.MethodPost, "/api/admin/images/upload-file", nil, m.ServeUploadHTTP)
}

func (m *Module) getImage(ctx *app.Ctx, in struct {
	ID api.ID `path:"id"`
}) (*Image, error) {
	return m.svc.GetImageByID(ctx.Context, int64(in.ID))
}

func (m *Module) listImages(ctx *app.Ctx, in ListImagesIn) (ListImagesOut, error) {
	items, total, err := m.svc.ListImages(ctx.Context, in.CollectionKey, in.CollectionID, in.Q, in.Page, in.PageSize)
	if err != nil {
		return ListImagesOut{}, err
	}
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 {
		pageSize = 48
	}
	return ListImagesOut{
		Items:    items,
		Total:    total,
		Page:     page,
		PageSize: pageSize,
	}, nil
}

func (m *Module) listCollections(ctx *app.Ctx, _ struct{}) (ListCollectionsOut, error) {
	cols, err := m.svc.ListCollections(ctx.Context)
	if err != nil {
		return ListCollectionsOut{}, err
	}
	return ListCollectionsOut{Collections: cols}, nil
}

func parseDataURL(s string) ([]byte, error) {
	s = strings.TrimSpace(s)
	if strings.HasPrefix(s, "data:") {
		parts := strings.SplitN(s, ",", 2)
		if len(parts) == 2 {
			return base64.StdEncoding.DecodeString(parts[1])
		}
	}
	return base64.StdEncoding.DecodeString(s)
}

func (m *Module) uploadImage(ctx *app.Ctx, in UploadImageIn) (UploadImageOut, error) {
	raw, err := parseDataURL(in.DataURL)
	if err != nil || len(raw) == 0 {
		return UploadImageOut{}, api.Invalid("图片数据解析失败")
	}

	img, err := m.svc.Upload(ctx, UploadInput{
		Title:         in.Title,
		FileName:      in.FileName,
		CollectionKey: in.CollectionKey,
		Reader:        bytes.NewReader(raw),
		FileSize:      int64(len(raw)),
	})
	if err != nil {
		return UploadImageOut{}, err
	}
	return UploadImageOut{Image: img}, nil
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

// ServeThumbnailHTTP 是 GET /media/r/{id}/{spec}.webp：编号不对、规格不在白名单、
// 原图不在一律 404（不说哪一样不对）；生成失败 500。生成好的文件留在 media 卷里，
// 下一次由 Caddy 直接给。
func (m *Module) ServeThumbnailHTTP(w http.ResponseWriter, r *http.Request) {
	id, okID := api.ParseID(r.PathValue("id"))
	spec, okExt := strings.CutSuffix(r.PathValue("file"), ".webp")
	_, okSpec := AllowedSpecs[spec]
	if !okID || !okExt || !okSpec {
		http.NotFound(w, r)
		return
	}
	path, err := m.svc.RenderThumbnail(r.Context(), int64(id), spec)
	if err != nil {
		var apiErr *api.Error
		if errors.As(err, &apiErr) && apiErr.Status == http.StatusNotFound {
			http.NotFound(w, r)
			return
		}
		slog.Error("缩略图没生成出来", "id", int64(id), "spec", spec, "err", err.Error())
		http.Error(w, "服务器开小差了，稍后再试", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "image/webp")
	w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	http.ServeFile(w, r, path)
}

// ServeUploadHTTP 支持标准 multipart/form-data 文件上传。
func (m *Module) ServeUploadHTTP(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(MaxFileSize); err != nil {
		http.Error(w, "文件过大或表单解析失败", http.StatusBadRequest)
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		http.Error(w, "未找到上传的文件", http.StatusBadRequest)
		return
	}
	defer file.Close()

	title := r.FormValue("title")
	colKey := r.FormValue("collection_key")

	ctx := &app.Ctx{Context: r.Context()}
	img, err := m.svc.Upload(ctx, UploadInput{
		Title:         title,
		FileName:      header.Filename,
		CollectionKey: colKey,
		Reader:        file,
		FileSize:      header.Size,
	})
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(UploadImageOut{Image: img})
}
