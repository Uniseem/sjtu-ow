package manual

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责后台手册的路由注册。
type Module struct{}

// NewModule 创建后台手册模块。
func NewModule() *Module {
	return &Module{}
}

// GetManualOut 是 GET /api/admin/manual 的响应。
type GetManualOut struct {
	Parts []Part `json:"parts"`
}

// Routes 注册后台手册路由。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/manual", api.Member, m.getManual, api.Nav("manual", "manual"))
}

func (m *Module) getManual(ctx *app.Ctx, _ struct{}) (GetManualOut, error) {
	parts := PartsFor(ctx.Viewer)
	if len(parts) == 0 {
		return GetManualOut{}, api.Forbidden()
	}
	return GetManualOut{Parts: parts}, nil
}
