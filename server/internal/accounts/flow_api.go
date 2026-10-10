package accounts

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

func (m *Module) registerAccountFlows(r *api.Registry) {
	api.Post(r, "/api/auth/reset-password/verify", api.Public, m.verifyResetCode, api.Limit(ratelimit.AuthResetPasswordConfirm))
	api.Get(r, "/api/auth/reset-password/state", api.Public, m.resetState, api.Limit(ratelimit.AuthResetPasswordConfirm))
	api.Post(r, "/api/auth/reset-password/complete", api.Public, m.completeReset, api.Limit(ratelimit.AuthResetPasswordConfirm))
	api.Get(r, "/api/auth/email/state", api.Member, m.emailState)
	api.Delete(r, "/api/auth/email/change", api.Member, m.cancelEmailChange, api.NoLimit("只删除当前账号的待验证邮箱"))
}

func (m *Module) verifyResetCode(ctx *app.Ctx, in ResetCodeInput) (VerifyEmailOut, error) {
	grant, err := m.svc.VerifyPasswordResetCode(ctx.Context, in)
	if err != nil {
		return VerifyEmailOut{}, err
	}
	ctx.SetResetCookie(grant.Token, grant.ExpiresAt)
	return VerifyEmailOut{Result: "ok", Message: "请设置新密码。"}, nil
}

func (m *Module) resetState(ctx *app.Ctx, _ struct{}) (*ResetState, error) {
	return m.svc.PasswordResetState(ctx.Context, ctx.ResetToken)
}

func (m *Module) completeReset(ctx *app.Ctx, in CompleteResetInput) (*ResetPasswordConfirmResult, error) {
	out, err := m.svc.CompletePasswordReset(ctx.Context, ctx.ResetToken, in)
	if err != nil {
		return nil, err
	}
	ctx.ClearResetCookie()
	ctx.ClearSessionCookie()
	return out, nil
}

func (m *Module) emailState(ctx *app.Ctx, _ struct{}) (*EmailState, error) {
	return m.svc.EmailChangeState(ctx)
}
func (m *Module) cancelEmailChange(ctx *app.Ctx, _ struct{}) (*ConfirmEmailChangeResult, error) {
	return m.svc.CancelEmailChange(ctx)
}
