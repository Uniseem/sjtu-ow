package notify

import (
	"net/http"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// Module 负责通知的路由。
type Module struct{ svc *Service }

// NewModule 造通知模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// BatchIn 只带批次编号。
type BatchIn struct {
	Batch string `path:"batch"`
}

// DecideIn 是确认页提交的：勾了哪几封；skip 为真这次都不发。
type DecideIn struct {
	Batch string   `path:"batch"`
	Send  []api.ID `json:"send"`
	Skip  bool     `json:"skip"`
}

// WaitingOut 是还等着的事。
type WaitingOut struct {
	Batches []WaitingBatch `json:"batches"`
}

// AnnounceIn 指一个对象。
type AnnounceIn struct {
	Kind string `path:"kind"`
	ID   api.ID `path:"id"`
}

// TokenIn 是退订链接里的令牌。
type TokenIn struct {
	Token string `path:"token"`
}

// NoIn 是没有入参的接口。
type NoIn struct{}

// PrefsIn 改我的活动通知开关。
type PrefsIn struct {
	Accepts bool `json:"accepts"`
}

// Routes 注册通知的接口。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/letters", api.Member, m.waiting)
	api.Get(r, "/api/letters/{batch}", api.Member, m.held)
	api.Post(r, "/api/letters/{batch}", api.Member, m.decide, api.NoLimit("只处理自己的批次，每封只认领一次"))

	// 「通知全体成员」：门在服务里按种类判（文章要能改作者，赛事、内战要对应的管理权限）。
	api.Get(r, "/api/admin/announce/{kind}/{id}", api.Member, m.status)
	api.Post(r, "/api/admin/announce/{kind}/{id}", api.Member, m.announce, api.NoLimit("同一件事 30 分钟冷却，服务里数"))

	api.Get(r, "/api/announcements/unsubscribe/{token}", api.Public, m.unsubscribeInfo, api.Limit(ratelimit.Unsubscribe))
	api.Post(r, "/api/announcements/unsubscribe/{token}", api.Public, m.unsubscribe, api.Limit(ratelimit.Unsubscribe))
	api.Get(r, "/api/me/announcements", api.Member, m.myPrefs)
	api.Post(r, "/api/me/announcements", api.Member, m.setMyPrefs, api.NoLimit("改自己的一个开关，幂等"))

	// 邮件客户端的一键退订：POST 表单到信里的链接（RFC 8058），不是 JSON。
	api.Raw(r, http.MethodPost, "/unsubscribe/{token}/{$}", []ratelimit.Decl{ratelimit.Unsubscribe}, m.svc.OneClick)
}

func (m *Module) waiting(ctx *app.Ctx, _ NoIn) (WaitingOut, error) {
	b, err := m.svc.Waiting(ctx)
	return WaitingOut{Batches: b}, err
}

func (m *Module) held(ctx *app.Ctx, in BatchIn) (*HeldBatch, error) {
	return m.svc.Held(ctx, in.Batch)
}

func (m *Module) decide(ctx *app.Ctx, in DecideIn) (*DecideResult, error) {
	ids := make([]int64, len(in.Send))
	for i, id := range in.Send {
		ids[i] = int64(id)
	}
	return m.svc.DecideHeld(ctx, in.Batch, ids, in.Skip)
}

func (m *Module) status(ctx *app.Ctx, in AnnounceIn) (*Status, error) {
	return m.svc.Status(ctx, in.Kind, int64(in.ID))
}

func (m *Module) announce(ctx *app.Ctx, in AnnounceIn) (*Result, error) {
	return m.svc.Announce(ctx, in.Kind, int64(in.ID))
}

func (m *Module) unsubscribeInfo(ctx *app.Ctx, in TokenIn) (*Prefs, error) {
	return m.svc.UnsubscribeInfo(ctx, in.Token)
}

func (m *Module) unsubscribe(ctx *app.Ctx, in TokenIn) (*Prefs, error) {
	return m.svc.Unsubscribe(ctx, in.Token)
}

func (m *Module) myPrefs(ctx *app.Ctx, _ NoIn) (*Prefs, error) { return m.svc.MyPrefs(ctx) }

func (m *Module) setMyPrefs(ctx *app.Ctx, in PrefsIn) (*Prefs, error) {
	return m.svc.SetMyPrefs(ctx, in.Accepts)
}
