package accounts

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// SessionIn 是 GET /api/session 的入参（空）。
type SessionIn struct{}

// SessionUser 是 GET /api/session 返回的用户信息。
// 格式与 web/apps/site/src/entry-server.ts 和 viewer.ts 完全对齐。
type SessionUser struct {
	ID            int64  `json:"id"`
	Nickname      string `json:"nickname"`
	Email         string `json:"email"`
	Admin         bool   `json:"admin"`
	EmailVerified bool   `json:"email_verified"`
	IsSJTU        bool   `json:"is_sjtu"`
}

// SessionOut 是 GET /api/session 的出参。访客为 { "user": null }。
type SessionOut struct {
	User *SessionUser `json:"user"`
}

// Module 提供账号域接口注册。
type Module struct {
	svc *Service
}

// NewModule 创建账号域接口模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// Routes 注册账号域接口（12 号文档 5.3）。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/session", api.Public, m.getSession)
}

func (m *Module) getSession(ctx *app.Ctx, _ SessionIn) (SessionOut, error) {
	if ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID == 0 {
		return SessionOut{User: nil}, nil
	}
	u, err := m.svc.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return SessionOut{User: nil}, err
	}
	if u == nil || !u.IsActive {
		return SessionOut{User: nil}, nil
	}
	return SessionOut{
		User: &SessionUser{
			ID:            u.ID,
			Nickname:      u.Nickname,
			Email:         u.Email,
			Admin:         RunsAdmin(u, ctx.Viewer),
			EmailVerified: ctx.Viewer.EmailVerified,
			IsSJTU:        u.IsSJTU,
		},
	}, nil
}
