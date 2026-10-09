package moderation

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责审核域的路由。
type Module struct{ svc *Service }

// NewModule 造审核模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// ListIn 是复核列表的筛选。
type ListIn struct {
	Status     string `query:"status"`
	Risk       string `query:"risk"`
	TargetType string `query:"target_type"`
	Since      int    `query:"since"`
	Page       int    `query:"page"`
}

// IDIn 只带编号。
type IDIn struct {
	ID api.ID `path:"id"`
}

// HandleIn 是人工处置。
type HandleIn struct {
	ID     api.ID `path:"id"`
	Action string `json:"action"`
	Note   string `json:"note"`
}

// AskIn 是发信要求作者修改。
type AskIn struct {
	ID      api.ID `path:"id"`
	Message string `json:"message"`
}

// ItemOut 包一条记录。
type ItemOut struct {
	Item *Item `json:"item"`
}

// Routes 注册审核域的接口。
func (m *Module) Routes(r *api.Registry) {
	gate := api.Cap(accounts.CapModerationReview)
	nav := api.Nav("moderation", "queue")
	api.Get(r, "/api/admin/moderation", gate, m.list, nav)
	api.Get(r, "/api/admin/moderation/{id}", gate, m.get, nav)
	api.Post(r, "/api/admin/moderation/{id}/handle", gate, m.handle, nav, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/moderation/{id}/ask-author", gate, m.ask, nav, api.NoLimit("后台，有能力的门"))
}

func (m *Module) list(ctx *app.Ctx, in ListIn) (*ListResult, error) {
	return m.svc.List(ctx, ListInput{Status: in.Status, Risk: in.Risk, TargetType: in.TargetType, SinceDays: in.Since, Page: in.Page})
}

func (m *Module) get(ctx *app.Ctx, in IDIn) (*Detail, error) { return m.svc.Get(ctx, int64(in.ID)) }

func (m *Module) handle(ctx *app.Ctx, in HandleIn) (ItemOut, error) {
	i, err := m.svc.Handle(ctx, int64(in.ID), in.Action, in.Note)
	return ItemOut{Item: i}, err
}

func (m *Module) ask(ctx *app.Ctx, in AskIn) (ItemOut, error) {
	i, err := m.svc.AskAuthor(ctx, int64(in.ID), in.Message)
	return ItemOut{Item: i}, err
}
