package accounts

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
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

// RegisterIn 是 POST /api/auth/register 的入参。
type RegisterIn struct {
	Email            string `json:"email"`
	Nickname         string `json:"nickname"`
	Password         string `json:"password"`
	ConfirmPassword  string `json:"confirm_password"`
	IsSJTU           *bool  `json:"is_sjtu"`
	AgreeTerms       bool   `json:"agree_terms"`
	AgreeCrossBorder bool   `json:"agree_cross_border"`
}

// RegisterOut 是 POST /api/auth/register 的出参。
type RegisterOut struct {
	Email   string `json:"email"`
	Message string `json:"message"`
}

// VerifyEmailIn 是 POST /api/auth/verify-email 的入参（邮箱 + 6 位码，
// 不需要会话，12 号文档 5.7）。
type VerifyEmailIn struct {
	Email string `json:"email"`
	Code  string `json:"code"`
}

// VerifyEmailOut 是 POST /api/auth/verify-email 的出参。令牌只进
// HttpOnly Cookie（ow_session），不出现在 JSON 里。
type VerifyEmailOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// LoginIn 是 POST /api/auth/login 的入参。
type LoginIn struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

// LoginOut 是 POST /api/auth/login 的出参。Result 是 "ok" 或
// "verify_required"（密码对但邮箱没验证过：新码已发，前端转验证页）。
type LoginOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// ResendCodeIn 是 POST /api/auth/resend-code 的入参。
type ResendCodeIn struct {
	Email string `json:"email"`
}

// ResendCodeOut 是 POST /api/auth/resend-code 的出参。
type ResendCodeOut struct {
	Email   string `json:"email"`
	Message string `json:"message"`
}

// ResetPasswordIn 是 POST /api/auth/reset-password 的入参。
type ResetPasswordIn struct {
	Email string `json:"email"`
}

// ResetPasswordOut 是 POST /api/auth/reset-password 的出参。
type ResetPasswordOut struct {
	Email   string `json:"email"`
	Message string `json:"message"`
}

// ResetPasswordConfirmIn 是 POST /api/auth/reset-password/confirm 的入参。
type ResetPasswordConfirmIn struct {
	Email           string `json:"email"`
	Code            string `json:"code"`
	Password        string `json:"password"`
	ConfirmPassword string `json:"confirm_password"`
}

// ResetPasswordConfirmOut 是 POST /api/auth/reset-password/confirm 的出参。
type ResetPasswordConfirmOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
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
	api.Post(r, "/api/auth/register", api.Public, m.register,
		api.Limit(ratelimit.AuthSignup))
	api.Post(r, "/api/auth/verify-email", api.Public, m.verifyEmail,
		api.Limit(ratelimit.AuthVerifyEmail))
	api.Post(r, "/api/auth/resend-code", api.Public, m.resendCode,
		api.Limit(ratelimit.AuthResendEmailCode))
	api.Post(r, "/api/auth/reset-password", api.Public, m.resetPassword,
		api.Limit(ratelimit.AuthResetPassword))
	api.Post(r, "/api/auth/reset-password/confirm", api.Public, m.resetPasswordConfirm,
		api.Limit(ratelimit.AuthResetPasswordConfirm))
	api.Post(r, "/api/auth/login", api.Public, m.login,
		api.Limit(ratelimit.AuthLogin))
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

func (m *Module) register(ctx *app.Ctx, in RegisterIn) (RegisterOut, error) {
	res, err := m.svc.Register(ctx.Context, RegisterInput(in))
	if err != nil {
		return RegisterOut{}, err
	}
	return RegisterOut{
		Email:   res.Email,
		Message: res.Message,
	}, nil
}

func (m *Module) verifyEmail(ctx *app.Ctx, in VerifyEmailIn) (VerifyEmailOut, error) {
	res, err := m.svc.VerifyEmail(ctx.Context, VerifyEmailInput(in))
	if err != nil {
		return VerifyEmailOut{}, err
	}
	ctx.SetSessionCookie(res.Token)
	return VerifyEmailOut{Result: "ok", Message: res.Message}, nil
}

func (m *Module) resendCode(ctx *app.Ctx, in ResendCodeIn) (ResendCodeOut, error) {
	res, err := m.svc.ResendCode(ctx.Context, ResendCodeInput(in))
	if err != nil {
		return ResendCodeOut{}, err
	}
	return ResendCodeOut{
		Email:   res.Email,
		Message: res.Message,
	}, nil
}

func (m *Module) resetPassword(ctx *app.Ctx, in ResetPasswordIn) (ResetPasswordOut, error) {
	res, err := m.svc.RequestPasswordReset(ctx.Context, ResetPasswordInput(in))
	if err != nil {
		return ResetPasswordOut{}, err
	}
	return ResetPasswordOut{
		Email:   res.Email,
		Message: res.Message,
	}, nil
}

func (m *Module) resetPasswordConfirm(ctx *app.Ctx, in ResetPasswordConfirmIn) (ResetPasswordConfirmOut, error) {
	res, err := m.svc.ResetPasswordConfirm(ctx.Context, ResetPasswordConfirmInput(in))
	if err != nil {
		return ResetPasswordConfirmOut{}, err
	}
	return ResetPasswordConfirmOut{
		Result:  res.Result,
		Message: res.Message,
	}, nil
}

func (m *Module) login(ctx *app.Ctx, in LoginIn) (LoginOut, error) {
	res, err := m.svc.Login(ctx.Context, LoginInput(in))
	if err != nil {
		return LoginOut{}, err
	}
	if res.Token != "" {
		ctx.SetSessionCookie(res.Token)
	}
	return LoginOut{Result: res.Result, Message: res.Message}, nil
}
