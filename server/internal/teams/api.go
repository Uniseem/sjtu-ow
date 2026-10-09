package teams

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

// Module 负责战队域的路由。
type Module struct{ svc *Service }

// NewModule 造战队模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// OkOut 是没有内容要回的动作的答复。
type OkOut struct {
	Result string `json:"result"`
}

var ok = OkOut{Result: "ok"}

// ListTeamsIn 是 GET /api/teams。
type ListTeamsIn struct {
	Recruiting bool   `query:"recruiting"`
	Role       string `query:"role"`
}

// TeamIDIn 只带战队编号。
type TeamIDIn struct {
	ID api.ID `path:"id"`
}

// CreateTeamIn 是 POST /api/teams。
type CreateTeamIn struct {
	Name            string   `json:"name"`
	Description     string   `json:"description"`
	IsRecruiting    *bool    `json:"is_recruiting,omitempty"`
	RecruitingRoles []string `json:"recruiting_roles,omitempty"`
	LogoImageID     *int64   `json:"logo_image_id,omitempty"`
}

// TeamOut 包一支战队。
type TeamOut struct {
	Team *Team `json:"team"`
}

// PatchTeamIn 是 PATCH /api/teams/{id}（自动保存协议 v2）。
type PatchTeamIn struct {
	ID          api.ID         `path:"id"`
	BaseVersion int64          `json:"base_version"`
	Changes     ProfileChanges `json:"changes"`
}

// ApplyIn 是 POST /api/teams/{id}/applications。
type ApplyIn struct {
	ID      api.ID   `path:"id"`
	Roles   []string `json:"roles"`
	Message string   `json:"message"`
}

// ApplicationOut 包一条申请。
type ApplicationOut struct {
	Application *Application `json:"application"`
}

// AppIDIn 只带申请编号。
type AppIDIn struct {
	ID api.ID `path:"id"`
}

// RejectIn 是 POST /api/team-applications/{id}/reject。
type RejectIn struct {
	ID   api.ID `path:"id"`
	Note string `json:"note"`
}

// MemberIn 是对队里某个人的动作。
type MemberIn struct {
	ID     api.ID `path:"id"`
	UserID api.ID `path:"user_id"`
}

// UserBody 是转让、指定队长的请求体。
type UserBody struct {
	ID     api.ID `path:"id"`
	UserID int64  `json:"user_id"`
}

// AlumnusIn 是去掉一条退役记录。
type AlumnusIn struct {
	ID api.ID `path:"id"`
}

// UploadLogoIn 是 POST /api/teams/{id}/logo 的入参。
type UploadLogoIn struct {
	ID       api.ID `path:"id"`
	FileName string `json:"file_name"`
	DataURL  string `json:"data_url"`
}

// UploadLogoOut 是 POST /api/teams/{id}/logo 的出参。
type UploadLogoOut struct {
	Image *media.Image `json:"image"`
}

// Routes 注册战队域的接口。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/teams", api.Public, m.list)
	api.Get(r, "/api/teams/{id}", api.Public, m.detail)

	api.Post(r, "/api/teams", api.Feature(accounts.FeatureTeamCreate), m.create,
		api.NoLimit("服务层只对通过校验的那几次计数（规则 84）"))
	api.Patch(r, "/api/teams/{id}", api.Member, m.patch,
		api.NoLimit("自动保存，按字段校验；改的人要是队长"))
	api.Post(r, "/api/teams/{id}/applications", api.Feature(accounts.FeatureTeamApply), m.apply,
		api.NoLimit("服务层按人每天 20 次（规则 89）"))
	api.Post(r, "/api/teams/{id}/logo", api.Member, m.uploadLogo,
		api.NoLimit("队长上传队标"))
	api.Get(r, "/api/teams/{id}/manage", api.Member, m.manage)
	api.Post(r, "/api/teams/{id}/leave", api.Member, m.leave, api.NoLimit("退队没有滥用面"))
	api.Post(r, "/api/teams/{id}/disband", api.Member, m.disband, api.NoLimit("解散有队长或超管的门"))
	api.Post(r, "/api/teams/{id}/transfer", api.Member, m.transfer, api.NoLimit("转让有队长或超管的门"))
	api.Post(r, "/api/teams/{id}/members/{user_id}/remove", api.Member, m.removeMember,
		api.NoLimit("移除有队长或超管的门"))

	api.Post(r, "/api/team-alumni/{id}/remove", api.Member, m.removeAlumnus,
		api.NoLimit("去掉退役记录有本人、队长、超管的门"))
	api.Post(r, "/api/team-applications/{id}/approve", api.Member, m.approve,
		api.NoLimit("审批有队长或超管的门"))
	api.Post(r, "/api/team-applications/{id}/reject", api.Member, m.reject,
		api.NoLimit("审批有队长或超管的门"))
	api.Post(r, "/api/team-applications/{id}/cancel", api.Member, m.cancel,
		api.NoLimit("只能撤回自己的申请"))
	api.Get(r, "/api/me/teams", api.Member, m.mine)

	api.Get(r, "/api/admin/teams", api.Superuser, m.adminList, api.Nav("members", "teams"))
	api.Patch(r, "/api/admin/teams/{id}", api.Superuser, m.patch, api.Nav("members", "teams"),
		api.NoLimit("超管后台的自动保存"))
	api.Post(r, "/api/admin/teams/{id}/assign-captain", api.Superuser, m.assignCaptain,
		api.Nav("members", "teams"), api.NoLimit("超管救援动作"))
	api.Post(r, "/api/admin/teams/{id}/disband", api.Superuser, m.disband,
		api.Nav("members", "teams"), api.NoLimit("超管动作"))
}

func (m *Module) list(ctx *app.Ctx, in ListTeamsIn) (*ListResult, error) {
	return m.svc.List(ctx.Context, ListInput{RecruitingOnly: in.Recruiting, Role: in.Role})
}

func (m *Module) detail(ctx *app.Ctx, in TeamIDIn) (*TeamPage, error) {
	return m.svc.Detail(ctx, int64(in.ID))
}

func (m *Module) create(ctx *app.Ctx, in CreateTeamIn) (TeamOut, error) {
	t, err := m.svc.CreateTeam(ctx, CreateTeamInput(in))
	return TeamOut{Team: t}, err
}

func (m *Module) patch(ctx *app.Ctx, in PatchTeamIn) (*SaveResult, error) {
	return m.svc.UpdateTeam(ctx, int64(in.ID), in.BaseVersion, in.Changes)
}

func (m *Module) apply(ctx *app.Ctx, in ApplyIn) (ApplicationOut, error) {
	a, err := m.svc.Apply(ctx, ApplyInput{TeamID: int64(in.ID), Roles: in.Roles, Message: in.Message})
	return ApplicationOut{Application: a}, err
}

func (m *Module) manage(ctx *app.Ctx, in TeamIDIn) (*ManagePage, error) {
	return m.svc.Manage(ctx, int64(in.ID))
}

func (m *Module) leave(ctx *app.Ctx, in TeamIDIn) (OkOut, error) {
	return ok, m.svc.Leave(ctx, int64(in.ID))
}

func (m *Module) disband(ctx *app.Ctx, in TeamIDIn) (OkOut, error) {
	return ok, m.svc.Disband(ctx, int64(in.ID))
}

func (m *Module) transfer(ctx *app.Ctx, in UserBody) (OkOut, error) {
	return ok, m.svc.TransferCaptain(ctx, int64(in.ID), in.UserID)
}

func (m *Module) assignCaptain(ctx *app.Ctx, in UserBody) (OkOut, error) {
	return ok, m.svc.AssignCaptain(ctx, int64(in.ID), in.UserID)
}

func (m *Module) removeMember(ctx *app.Ctx, in MemberIn) (OkOut, error) {
	return ok, m.svc.RemoveMember(ctx, int64(in.ID), int64(in.UserID))
}

func (m *Module) removeAlumnus(ctx *app.Ctx, in AlumnusIn) (OkOut, error) {
	return ok, m.svc.RemoveAlumnus(ctx, int64(in.ID))
}

func (m *Module) approve(ctx *app.Ctx, in AppIDIn) (ApplicationOut, error) {
	a, err := m.svc.Approve(ctx, int64(in.ID))
	return ApplicationOut{Application: a}, err
}

func (m *Module) reject(ctx *app.Ctx, in RejectIn) (ApplicationOut, error) {
	a, err := m.svc.Reject(ctx, RejectInput{ID: int64(in.ID), Note: in.Note})
	return ApplicationOut{Application: a}, err
}

func (m *Module) cancel(ctx *app.Ctx, in AppIDIn) (ApplicationOut, error) {
	a, err := m.svc.Cancel(ctx, int64(in.ID))
	return ApplicationOut{Application: a}, err
}

func (m *Module) mine(ctx *app.Ctx, _ struct{}) (*MyTeamsResult, error) {
	return m.svc.MyTeams(ctx)
}

func (m *Module) adminList(ctx *app.Ctx, _ struct{}) (struct {
	Teams []AdminRow `json:"teams"`
}, error) {
	rows, err := m.svc.AdminList(ctx)
	return struct {
		Teams []AdminRow `json:"teams"`
	}{Teams: rows}, err
}

func (m *Module) uploadLogo(ctx *app.Ctx, in UploadLogoIn) (UploadLogoOut, error) {
	img, err := m.svc.SetTeamLogo(ctx, int64(in.ID), in.FileName, in.DataURL)
	if err != nil {
		return UploadLogoOut{}, err
	}
	return UploadLogoOut{Image: img}, nil
}
