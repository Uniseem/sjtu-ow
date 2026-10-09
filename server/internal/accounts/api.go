package accounts

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// SessionIn 是 GET /api/session 的入参（空）。
type SessionIn struct{}

// SessionUser 是 GET /api/session 返回的用户信息。
type SessionUser struct {
	ID            int64    `json:"id"`
	Nickname      string   `json:"nickname"`
	Email         string   `json:"email"`
	Admin         bool     `json:"admin"`
	Superuser     bool     `json:"superuser"`
	Caps          []string `json:"caps"`
	EmailVerified bool     `json:"email_verified"`
	IsSJTU        bool     `json:"is_sjtu"`
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

// VerifyEmailIn 是 POST /api/auth/verify-email 的入参。
type VerifyEmailIn struct {
	Email string `json:"email"`
	Code  string `json:"code"`
}

// VerifyEmailOut 是 POST /api/auth/verify-email 的出参。
type VerifyEmailOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// LoginIn 是 POST /api/auth/login 的入参。
type LoginIn struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

// LoginOut 是 POST /api/auth/login 的出参。
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

// ChangePasswordIn 是 POST /api/auth/change-password 的入参。
type ChangePasswordIn struct {
	OldPassword     string `json:"old_password"`
	Password        string `json:"password"`
	ConfirmPassword string `json:"confirm_password"`
}

// ChangePasswordOut 是 POST /api/auth/change-password 的出参。
type ChangePasswordOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// LogoutIn 是 POST /api/auth/logout 的入参。
type LogoutIn struct{}

// LogoutOut 是 POST /api/auth/logout 的出参。
type LogoutOut struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// ReauthIn 是 POST /api/auth/reauthenticate 的入参。
type ReauthIn = ReauthInput

// ReauthOut 是 POST /api/auth/reauthenticate 的出参。
type ReauthOut = ReauthResult

// RequestEmailChangeIn 是 POST /api/auth/email/change 的入参。
type RequestEmailChangeIn = RequestEmailChangeInput

// RequestEmailChangeOut 是 POST /api/auth/email/change 的出参。
type RequestEmailChangeOut = RequestEmailChangeResult

// ConfirmEmailChangeIn 是 POST /api/auth/email/change/confirm 的入参。
type ConfirmEmailChangeIn = ConfirmEmailChangeInput

// ConfirmEmailChangeOut 是 POST /api/auth/email/change/confirm 的出参。
type ConfirmEmailChangeOut = ConfirmEmailChangeResult

// DeleteAccountIn 是 POST /api/auth/delete-account 的入参。
type DeleteAccountIn = DeleteAccountInput

// DeleteAccountOut 是 POST /api/auth/delete-account 的出参。
type DeleteAccountOut = DeleteAccountResult

// GetProfileIn 是 GET /api/me/profile 的入参。
type GetProfileIn struct{}

// GetProfileOut 是 GET /api/me/profile 的出参。
type GetProfileOut = ProfileResult

// PatchProfileIn 是 PATCH /api/me/profile 的入参。
type PatchProfileIn = UpdateProfileInput

// PatchProfileOut 是 PATCH /api/me/profile 的出参。
type PatchProfileOut = UpdateProfileResult

// AddGameAccountIn 是 POST /api/me/game-accounts 的入参。
type AddGameAccountIn = AddGameAccountInput

// AddGameAccountOut 是 POST /api/me/game-accounts 的出参。
type AddGameAccountOut = GameAccountResult

// UpdateGameAccountIn 是 PATCH /api/me/game-accounts/{id} 的入参。
type UpdateGameAccountIn = UpdateGameAccountInput

// UpdateGameAccountOut 是 PATCH /api/me/game-accounts/{id} 的出参。
type UpdateGameAccountOut = GameAccountResult

// DeleteGameAccountIn 是 DELETE /api/me/game-accounts/{id} 的入参。
type DeleteGameAccountIn struct {
	ID api.ID `path:"id"`
}

// DeleteGameAccountOut 是 DELETE /api/me/game-accounts/{id} 的出参。
type DeleteGameAccountOut = DeleteResult

// AddContactIn 是 POST /api/me/contacts 的入参。
type AddContactIn = AddContactInput

// AddContactOut 是 POST /api/me/contacts 的出参。
type AddContactOut = ContactResult

// DeleteContactIn 是 DELETE /api/me/contacts/{id} 的入参。
type DeleteContactIn struct {
	ID api.ID `path:"id"`
}

// DeleteContactOut 是 DELETE /api/me/contacts/{id} 的出参。
type DeleteContactOut = DeleteResult

// ExportAccountIn 是 GET /api/me/export 的入参。
type ExportAccountIn struct{}

// ExportAccountOut 是 GET /api/me/export 的出参。
type ExportAccountOut = AccountExportData

// ListUsersIn 是 GET /api/admin/users 的入参。
type ListUsersIn = ListUsersInput

// ListUsersOut 是 GET /api/admin/users 的出参。
type ListUsersOut = ListUsersResult

// GetUserDetailIn 是 GET /api/admin/users/{id} 的入参。
type GetUserDetailIn = UserDetailInput

// GetUserDetailOut 是 GET /api/admin/users/{id} 的出参。
type GetUserDetailOut = UserDetailResult

// DeactivateUserIn 是 POST /api/admin/users/{id}/deactivate 的入参。
type DeactivateUserIn = DeactivateUserInput

// DeactivateUserOut 是 POST /api/admin/users/{id}/deactivate 的出参。
type DeactivateUserOut = DeactivateResult

// ActivateUserIn 是 POST /api/admin/users/{id}/activate 的入参。
type ActivateUserIn = ReactivateUserInput

// ActivateUserOut 是 POST /api/admin/users/{id}/activate 的出参。
type ActivateUserOut = ReactivateResult

// UpdateUserRolesIn 是 PATCH /api/admin/users/{id}/roles 的入参。
type UpdateUserRolesIn = UpdateUserRolesInput

// UpdateUserRolesOut 是 PATCH /api/admin/users/{id}/roles 的出参。
type UpdateUserRolesOut = UpdateUserRolesResult

// UpdateUserRulesIn 是 PATCH /api/admin/users/{id}/rules 的入参。
type UpdateUserRulesIn = UpdateUserRulesInput

// UpdateUserRulesOut 是 PATCH /api/admin/users/{id}/rules 的出参。
type UpdateUserRulesOut = UpdateUserRulesResult

// GetRoleRestrictionsIn 是 GET /api/admin/feature-role-restrictions 的入参。
type GetRoleRestrictionsIn struct{}

// GetRoleRestrictionsOut 是 GET /api/admin/feature-role-restrictions 的出参。
type GetRoleRestrictionsOut = FeatureRoleRestrictionsResult

// SetRoleRestrictionsIn 是 PUT /api/admin/feature-role-restrictions 的入参。
type SetRoleRestrictionsIn = SetFeatureRoleRestrictionsInput

// SetRoleRestrictionsOut 是 PUT /api/admin/feature-role-restrictions 的出参。
type SetRoleRestrictionsOut = SetFeatureRoleRestrictionsResult

// UploadAvatarIn 是 POST /api/me/avatar 的入参。
type UploadAvatarIn struct {
	FileName string `json:"file_name"`
	DataURL  string `json:"data_url"`
}

// UploadAvatarOut 是 POST /api/me/avatar 的出参。
type UploadAvatarOut struct {
	Image *media.Image `json:"image"`
}

// DeleteAvatarOut 是 DELETE /api/me/avatar 的出参。
type DeleteAvatarOut struct {
	Result string `json:"result"`
}

// ListAvatarsIn 是 GET /api/admin/avatars 的入参。
type ListAvatarsIn struct {
	Status   string `query:"status"`
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
}

// ListAvatarsOut 是 GET /api/admin/avatars 的出参。
type ListAvatarsOut struct {
	Items    []AvatarSubmission `json:"items"`
	Total    int                `json:"total"`
	Page     int                `json:"page"`
	PageSize int                `json:"page_size"`
}

// TakeDownAvatarIn 是 POST /api/admin/avatars/{id}/take-down 的入参。
type TakeDownAvatarIn struct {
	ID   api.ID `path:"id"`
	Note string `json:"note"`
}

// TakeDownAvatarOut 是 POST /api/admin/avatars/{id}/take-down 的出参。
type TakeDownAvatarOut struct {
	Result string `json:"result"`
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
	// 会话与认证
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
	api.Post(r, "/api/auth/change-password", api.Member, m.changePassword,
		api.Limit(ratelimit.AuthChangePassword))
	api.Post(r, "/api/auth/logout", api.Member, m.logout,
		api.NoLimit("退出登录无需限流"))
	api.Post(r, "/api/auth/login", api.Public, m.login,
		api.Limit(ratelimit.AuthLogin))

	// 重认证与改邮箱 (规则 6、7)
	api.Post(r, "/api/auth/reauthenticate", api.Member, m.reauthenticate,
		api.Limit(ratelimit.AuthReauthenticate))
	api.Post(r, "/api/auth/email/change", api.Member, m.requestEmailChange,
		api.Limit(ratelimit.AuthManageEmail))
	api.Post(r, "/api/auth/email/change/confirm", api.Member, m.confirmEmailChange,
		api.Limit(ratelimit.AuthManageEmail))

	// 账号注销与导出 (规则 28–32, 37–38)
	api.Post(r, "/api/auth/delete-account", api.Member, m.deleteAccount,
		api.Limit(ratelimit.AccountDeleteTry))
	api.Get(r, "/api/me/export", api.Member, m.exportAccount,
		api.Limit(ratelimit.AccountExport))

	// 个人中心 (Profile, 规则 18–21)
	api.Get(r, "/api/me/profile", api.Member, m.getProfile)
	api.Patch(r, "/api/me/profile", api.Member, m.patchProfile,
		api.NoLimit("修改个人资料无需限流"))

	// 游戏 ID 管理 (规则 16–17)
	api.Post(r, "/api/me/game-accounts", api.Member, m.addGameAccount,
		api.NoLimit("绑定游戏ID由上限5个控制"))
	api.Patch(r, "/api/me/game-accounts/{id}", api.Member, m.updateGameAccount,
		api.NoLimit("更新段位无需限流"))
	api.Delete(r, "/api/me/game-accounts/{id}", api.Member, m.deleteGameAccount,
		api.NoLimit("删除游戏ID无需限流"))

	// 联系方式管理 (规则 18–19)
	api.Post(r, "/api/me/contacts", api.Member, m.addContact,
		api.NoLimit("添加联系方式由类型唯一约束控制"))
	api.Delete(r, "/api/me/contacts/{id}", api.Member, m.deleteContact,
		api.NoLimit("删除联系方式无需限流"))

	// 后台管理接口 (Superuser 门，规则 33–36, 39–42)
	api.Get(r, "/api/admin/users", api.Superuser, m.listUsers,
		api.Nav("users", "list"))
	api.Get(r, "/api/admin/users/{id}", api.Superuser, m.getUserDetail,
		api.Nav("users", "detail"))
	api.Post(r, "/api/admin/users/{id}/deactivate", api.Superuser, m.deactivateUser,
		api.NoLimit("管理员停用用户"))
	api.Post(r, "/api/admin/users/{id}/activate", api.Superuser, m.activateUser,
		api.NoLimit("管理员启用用户"))
	api.Patch(r, "/api/admin/users/{id}/roles", api.Superuser, m.updateUserRoles,
		api.NoLimit("管理员分配角色"))
	api.Patch(r, "/api/admin/users/{id}/rules", api.Superuser, m.updateUserRules,
		api.NoLimit("管理员修改单人规则"))
	api.Get(r, "/api/admin/feature-role-restrictions", api.Superuser, m.getRoleRestrictions,
		api.Nav("roles", "restrictions"))
	api.Put(r, "/api/admin/feature-role-restrictions", api.Superuser, m.setRoleRestrictions,
		api.NoLimit("管理员修改角色限制"))

	// 头像管理 (规则 221)
	api.Post(r, "/api/me/avatar", api.Member, m.uploadAvatar,
		api.Limit(ratelimit.AvatarUpload))
	api.Delete(r, "/api/me/avatar", api.Member, m.deleteAvatar,
		api.NoLimit("移除头像无需限流"))

	// 管理员头像审核 (设计 14.1)
	api.Get(r, "/api/admin/avatars", api.Cap(CapModerationReview), m.listAvatars,
		api.Nav("review", "avatars"))
	api.Post(r, "/api/admin/avatars/{id}/take-down", api.Cap(CapModerationReview), m.takeDownAvatar,
		api.Nav("review", "avatars"), api.NoLimit("下架头像"))
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
	var caps []string
	if ctx.Viewer != nil && ctx.Viewer.Caps != nil {
		for c := range ctx.Viewer.Caps {
			caps = append(caps, string(c))
		}
	}
	if caps == nil {
		caps = []string{}
	}
	return SessionOut{
		User: &SessionUser{
			ID:            u.ID,
			Nickname:      u.Nickname,
			Email:         u.Email,
			Admin:         RunsAdmin(u, ctx.Viewer),
			Superuser:     u.IsSuperuser || (ctx.Viewer != nil && ctx.Viewer.Superuser),
			Caps:          caps,
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

func (m *Module) changePassword(ctx *app.Ctx, in ChangePasswordIn) (ChangePasswordOut, error) {
	res, err := m.svc.ChangePassword(ctx, ChangePasswordInput(in))
	if err != nil {
		return ChangePasswordOut{}, err
	}
	return ChangePasswordOut{
		Result:  res.Result,
		Message: res.Message,
	}, nil
}

func (m *Module) logout(ctx *app.Ctx, _ LogoutIn) (LogoutOut, error) {
	res, err := m.svc.Logout(ctx)
	if err != nil {
		return LogoutOut{}, err
	}
	return LogoutOut{
		Result:  res.Result,
		Message: res.Message,
	}, nil
}

func (m *Module) reauthenticate(ctx *app.Ctx, in ReauthIn) (ReauthOut, error) {
	res, err := m.svc.Reauthenticate(ctx, in)
	if err != nil {
		return ReauthOut{}, err
	}
	return *res, nil
}

func (m *Module) requestEmailChange(ctx *app.Ctx, in RequestEmailChangeIn) (RequestEmailChangeOut, error) {
	res, err := m.svc.RequestEmailChange(ctx, in)
	if err != nil {
		return RequestEmailChangeOut{}, err
	}
	return *res, nil
}

func (m *Module) confirmEmailChange(ctx *app.Ctx, in ConfirmEmailChangeIn) (ConfirmEmailChangeOut, error) {
	res, err := m.svc.ConfirmEmailChange(ctx, in)
	if err != nil {
		return ConfirmEmailChangeOut{}, err
	}
	return *res, nil
}

func (m *Module) deleteAccount(ctx *app.Ctx, in DeleteAccountIn) (DeleteAccountOut, error) {
	res, err := m.svc.DeleteAccount(ctx, in)
	if err != nil {
		return DeleteAccountOut{}, err
	}
	return *res, nil
}

func (m *Module) getProfile(ctx *app.Ctx, _ GetProfileIn) (GetProfileOut, error) {
	res, err := m.svc.GetProfile(ctx)
	if err != nil {
		return GetProfileOut{}, err
	}
	return *res, nil
}

func (m *Module) patchProfile(ctx *app.Ctx, in PatchProfileIn) (PatchProfileOut, error) {
	res, err := m.svc.UpdateProfile(ctx, in)
	if err != nil {
		return PatchProfileOut{}, err
	}
	return *res, nil
}

func (m *Module) addGameAccount(ctx *app.Ctx, in AddGameAccountIn) (AddGameAccountOut, error) {
	res, err := m.svc.AddGameAccount(ctx, in)
	if err != nil {
		return AddGameAccountOut{}, err
	}
	return *res, nil
}

func (m *Module) updateGameAccount(ctx *app.Ctx, in UpdateGameAccountIn) (UpdateGameAccountOut, error) {
	res, err := m.svc.UpdateGameAccount(ctx, in)
	if err != nil {
		return UpdateGameAccountOut{}, err
	}
	return *res, nil
}

func (m *Module) deleteGameAccount(ctx *app.Ctx, in DeleteGameAccountIn) (DeleteGameAccountOut, error) {
	res, err := m.svc.DeleteGameAccount(ctx, int64(in.ID))
	if err != nil {
		return DeleteGameAccountOut{}, err
	}
	return *res, nil
}

func (m *Module) addContact(ctx *app.Ctx, in AddContactIn) (AddContactOut, error) {
	res, err := m.svc.AddContact(ctx, in)
	if err != nil {
		return AddContactOut{}, err
	}
	return *res, nil
}

func (m *Module) deleteContact(ctx *app.Ctx, in DeleteContactIn) (DeleteContactOut, error) {
	res, err := m.svc.DeleteContact(ctx, int64(in.ID))
	if err != nil {
		return DeleteContactOut{}, err
	}
	return *res, nil
}

func (m *Module) exportAccount(ctx *app.Ctx, _ ExportAccountIn) (ExportAccountOut, error) {
	res, err := m.svc.ExportAccount(ctx)
	if err != nil {
		return ExportAccountOut{}, err
	}
	return *res, nil
}

func (m *Module) listUsers(ctx *app.Ctx, in ListUsersIn) (ListUsersOut, error) {
	res, err := m.svc.ListUsers(ctx, in)
	if err != nil {
		return ListUsersOut{}, err
	}
	return *res, nil
}

func (m *Module) getUserDetail(ctx *app.Ctx, in GetUserDetailIn) (GetUserDetailOut, error) {
	res, err := m.svc.GetUserDetail(ctx, in)
	if err != nil {
		return GetUserDetailOut{}, err
	}
	return *res, nil
}

func (m *Module) deactivateUser(ctx *app.Ctx, in DeactivateUserIn) (DeactivateUserOut, error) {
	res, err := m.svc.DeactivateUser(ctx, in)
	if err != nil {
		return DeactivateUserOut{}, err
	}
	return *res, nil
}

func (m *Module) activateUser(ctx *app.Ctx, in ActivateUserIn) (ActivateUserOut, error) {
	res, err := m.svc.ReactivateUser(ctx, in)
	if err != nil {
		return ActivateUserOut{}, err
	}
	return *res, nil
}

func (m *Module) updateUserRoles(ctx *app.Ctx, in UpdateUserRolesIn) (UpdateUserRolesOut, error) {
	res, err := m.svc.UpdateUserRoles(ctx, in)
	if err != nil {
		return UpdateUserRolesOut{}, err
	}
	return *res, nil
}

func (m *Module) updateUserRules(ctx *app.Ctx, in UpdateUserRulesIn) (UpdateUserRulesOut, error) {
	res, err := m.svc.UpdateUserRules(ctx, in)
	if err != nil {
		return UpdateUserRulesOut{}, err
	}
	return *res, nil
}

func (m *Module) getRoleRestrictions(ctx *app.Ctx, _ GetRoleRestrictionsIn) (GetRoleRestrictionsOut, error) {
	res, err := m.svc.GetFeatureRoleRestrictions(ctx)
	if err != nil {
		return GetRoleRestrictionsOut{}, err
	}
	return *res, nil
}

func (m *Module) setRoleRestrictions(ctx *app.Ctx, in SetRoleRestrictionsIn) (SetRoleRestrictionsOut, error) {
	res, err := m.svc.SetFeatureRoleRestrictions(ctx, in)
	if err != nil {
		return SetRoleRestrictionsOut{}, err
	}
	return *res, nil
}

func (m *Module) uploadAvatar(ctx *app.Ctx, in UploadAvatarIn) (UploadAvatarOut, error) {
	img, err := m.svc.SubmitAvatar(ctx, in.FileName, in.DataURL)
	if err != nil {
		return UploadAvatarOut{}, err
	}
	return UploadAvatarOut{Image: img}, nil
}

func (m *Module) deleteAvatar(ctx *app.Ctx, _ struct{}) (DeleteAvatarOut, error) {
	if err := m.svc.RemoveAvatar(ctx); err != nil {
		return DeleteAvatarOut{}, err
	}
	return DeleteAvatarOut{Result: "ok"}, nil
}

func (m *Module) listAvatars(ctx *app.Ctx, in ListAvatarsIn) (ListAvatarsOut, error) {
	items, total, err := m.svc.ListAvatars(ctx, in.Status, in.Page, in.PageSize)
	if err != nil {
		return ListAvatarsOut{}, err
	}
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 {
		pageSize = 50
	}
	return ListAvatarsOut{
		Items:    items,
		Total:    total,
		Page:     page,
		PageSize: pageSize,
	}, nil
}

func (m *Module) takeDownAvatar(ctx *app.Ctx, in TakeDownAvatarIn) (TakeDownAvatarOut, error) {
	if err := m.svc.TakeDownAvatar(ctx, int64(in.ID), in.Note); err != nil {
		return TakeDownAvatarOut{}, err
	}
	return TakeDownAvatarOut{Result: "ok"}, nil
}
