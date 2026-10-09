package agenda

import (
	"net/http"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// Module 负责安排的路由。
type Module struct{ svc *Service }

// NewModule 造安排模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// NoIn 是没有入参的接口。
type NoIn struct{}

// MineOut 是首页「我的安排」。
type MineOut struct {
	Items []Item `json:"items"`
}

// Routes 注册安排的接口。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/me/agenda", api.Member, m.mine)
	api.Get(r, "/api/me/calendar", api.Member, m.address)
	api.Post(r, "/api/me/calendar/renew", api.Member, m.renew, api.NoLimit("换一个地址，只改自己一个数"))
	// 日历订阅：.ics 文件，不是 JSON；规则 216 每个 IP 每分钟 30 次。
	api.Raw(r, http.MethodGet, "/calendar/{file}", []ratelimit.Decl{ratelimit.CalendarFeed}, m.svc.Serve)
}

func (m *Module) mine(ctx *app.Ctx, _ NoIn) (MineOut, error) {
	items, err := m.svc.Mine(ctx)
	return MineOut{Items: items}, err
}

func (m *Module) address(ctx *app.Ctx, _ NoIn) (*Address, error) { return m.svc.MyAddress(ctx) }

func (m *Module) renew(ctx *app.Ctx, _ NoIn) (*Address, error) { return m.svc.Renew(ctx) }
