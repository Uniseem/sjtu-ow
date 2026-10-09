package search

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// Module 负责搜索接口路由。
type Module struct {
	svc *Service
}

// NewModule 创建搜索模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// SearchIn 是 GET /api/search 的入参。
type SearchIn struct {
	Q string `query:"q"`
}

// SearchOut 是 GET /api/search 的出参。
type SearchOut = Result

// Routes 注册搜索接口（附录 C、规则 214、233）。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/search", api.Public, m.search,
		api.Limit(ratelimit.Search))
}

func (m *Module) search(ctx *app.Ctx, in SearchIn) (SearchOut, error) {
	res, err := m.svc.Search(ctx.Context, in.Q)
	if err != nil {
		return SearchOut{}, err
	}
	return *res, nil
}
