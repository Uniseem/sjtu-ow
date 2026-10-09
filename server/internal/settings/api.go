package settings

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责全站设置相关的 HTTP 路由。
type Module struct {
	svc *Service
}

// NewModule 创建全站设置模块。
func NewModule(svc *Service) *Module {
	return &Module{svc: svc}
}

// GetSettingsOut 是 GET /api/admin/settings 的响应。
type GetSettingsOut struct {
	Settings *SiteSettingsDTO `json:"settings"`
}

// PatchSettingsIn 是 PATCH /api/admin/settings 的入参。
type PatchSettingsIn = UpdateSettingsInput

// PatchSettingsOut 是 PATCH /api/admin/settings 的响应。
type PatchSettingsOut struct {
	Settings *SiteSettingsDTO `json:"settings"`
}

// TestEmailOut 是 POST /api/admin/settings/test-email 的响应。
type TestEmailOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// Routes 注册设置路由。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/admin/settings", api.Superuser, m.get, api.Nav("settings", "site"))
	api.Patch(r, "/api/admin/settings", api.Superuser, m.patch, api.Nav("settings", "site"),
		api.NoLimit("超管修改设置"))
	api.Post(r, "/api/admin/settings/test-email", api.Superuser, m.testEmail, api.Nav("settings", "site"),
		api.NoLimit("超管测试发信"))
}

func (m *Module) get(ctx *app.Ctx, _ struct{}) (GetSettingsOut, error) {
	s, err := m.svc.Get(ctx.Context)
	if err != nil {
		return GetSettingsOut{}, err
	}
	return GetSettingsOut{Settings: s}, nil
}

func (m *Module) patch(ctx *app.Ctx, in PatchSettingsIn) (PatchSettingsOut, error) {
	s, err := m.svc.Update(ctx, in)
	if err != nil {
		return PatchSettingsOut{}, err
	}
	return PatchSettingsOut{Settings: s}, nil
}

func (m *Module) testEmail(ctx *app.Ctx, _ struct{}) (TestEmailOut, error) {
	msg, err := m.svc.SendTestEmail(ctx)
	if err != nil {
		return TestEmailOut{}, err
	}
	return TestEmailOut{Result: "ok", Message: msg}, nil
}
