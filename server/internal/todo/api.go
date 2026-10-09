package todo

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责后台待办的路由注册。
type Module struct {
	svc *Service
}

// NewModule 创建后台待办模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// GetTodoOut 是 GET /api/admin/todo 的响应。
type GetTodoOut = Result

// Routes 注册后台待办路由。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/todo", api.Member, m.getTodo, api.Nav("home", "todo"))
}

func (m *Module) getTodo(ctx *app.Ctx, _ struct{}) (GetTodoOut, error) {
	res, err := m.svc.GetDuties(ctx)
	if err != nil {
		return GetTodoOut{}, err
	}
	return *res, nil
}
