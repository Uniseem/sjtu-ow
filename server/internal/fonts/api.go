package fonts

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func (m *Module) Routes(r *api.Registry) {
	library := api.Nav("settings", "fonts")
	typography := api.Nav("settings", "typography")
	api.Get(r, "/api/admin/fonts", api.Superuser, m.list, library)
	api.Get(r, "/api/admin/fonts/{id}", api.Superuser, m.detail, library)
	api.Post(r, "/api/admin/fonts", api.Superuser, m.importFont, library, api.NoLimit("超级管理员显式导入已授权字体，总大小有上限"))
	api.Delete(r, "/api/admin/fonts/{id}", api.Superuser, m.deleteFont, library, api.NoLimit("超管删除未被引用的字体，事务内再次查引用"))
	api.Post(r, "/api/admin/fonts/uploads", api.Superuser, m.beginUpload, library, api.NoLimit("超管成品包上传会话，总64MB、最多3个未完成"))
	api.Post(r, "/api/admin/fonts/uploads/{id}/chunks", api.Superuser, m.uploadChunk, library, api.NoLimit("超管上传128KB定长分块，所有者绑定"))
	api.Get(r, "/api/admin/typography", api.Superuser, m.typography, typography)
	api.Post(r, "/api/admin/typography/preview", api.Superuser, m.preview, typography, api.NoLimit("超管排版草稿只生成作用域CSS预览，不写设置"))
	api.Patch(r, "/api/admin/typography", api.Superuser, m.patchTypography, typography, api.NoLimit("超管排版自动保存，乐观版本且写前校验九区域"))
}
func (m *Module) list(ctx *app.Ctx, _ struct{}) (FontList, error) { return m.svc.list(ctx) }
func (m *Module) detail(ctx *app.Ctx, in IDIn) (FontDetail, error) {
	return m.svc.detail(ctx, int64(in.ID))
}
func (m *Module) importFont(ctx *app.Ctx, in ImportIn) (FontDetail, error) {
	return m.svc.importFont(ctx, in)
}
func (m *Module) deleteFont(ctx *app.Ctx, in IDIn) (Result, error) {
	return m.svc.delete(ctx, int64(in.ID))
}
func (m *Module) typography(ctx *app.Ctx, _ struct{}) (TypographyPage, error) {
	return m.svc.typography(ctx)
}
func (m *Module) patchTypography(ctx *app.Ctx, in PatchTypographyIn) (SaveOut, error) {
	return m.svc.patchTypography(ctx, in)
}
func (m *Module) beginUpload(ctx *app.Ctx, in BeginUploadIn) (UploadOut, error) {
	return m.svc.beginUpload(ctx, in)
}
func (m *Module) uploadChunk(ctx *app.Ctx, in UploadChunkIn) (UploadOut, error) {
	return m.svc.uploadChunk(ctx, in)
}

func (m *Module) preview(ctx *app.Ctx, in PreviewIn) (PreviewOut, error) {
	return m.svc.preview(ctx, in)
}
