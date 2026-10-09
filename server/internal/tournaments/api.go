package tournaments

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责赛事域的路由。
type Module struct{ svc *Service }

// NewModule 造赛事模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// OkOut 是没有内容要回的动作的答复。
type OkOut struct {
	Result string `json:"result"`
}

// IDIn 只带编号。
type IDIn struct {
	ID api.ID `path:"id"`
}

// GroupsOut 是列表页。
type GroupsOut struct {
	Groups []Group `json:"groups"`
}

// SubmitIn 是 POST /api/tournaments/{id}/registrations。
type SubmitIn struct {
	ID       api.ID           `path:"id"`
	TeamID   int64            `json:"team_id"`
	Accounts map[string]int64 `json:"accounts"`
}

// RegistrationOut 包一条报名。
type RegistrationOut struct {
	Registration *Registration `json:"registration"`
}

// SignupIn 是 POST /api/tournaments/{id}/signup。
type SignupIn struct {
	ID            api.ID   `path:"id"`
	GameAccountID int64    `json:"game_account_id"`
	Roles         []string `json:"roles"`
}

// SignupOut 包个人报名。
type SignupOut struct {
	Signup *SignupView `json:"signup"`
}

// LeaveOut 是退出临时队的答复。
type LeaveOut struct {
	Dissolved bool `json:"dissolved"`
}

// MineOut 是 GET /api/me/registrations。
type MineOut struct {
	Registrations []MyRegistration `json:"registrations"`
}

// PatchIn 是 PATCH /api/admin/tournaments/{id}（自动保存协议 v2）。
type PatchIn struct {
	ID          api.ID  `path:"id"`
	BaseVersion int64   `json:"base_version"`
	Changes     Changes `json:"changes"`
}

// TournamentOut 包一项赛事。
type TournamentOut struct {
	Tournament *Tournament `json:"tournament"`
}

// AdminListOut 是后台赛事列表。
type AdminListOut struct {
	Tournaments []AdminRow `json:"tournaments"`
}

// ReasonIn 是取消赛事的说明。
type ReasonIn struct {
	ID     api.ID `path:"id"`
	Reason string `json:"reason"`
}

// NoteIn 是「通知报名的人」。
type NoteIn struct {
	ID   api.ID `path:"id"`
	Note string `json:"note"`
}

// NotifyOut 是通知的结果。
type NotifyOut struct {
	Recipients int `json:"recipients"`
}

// ReviewIn 是审核页的筛选。
type ReviewIn struct {
	ID     api.ID `path:"id"`
	Status string `query:"status"`
}

// ReviewOut 是审核页。
type ReviewOut struct {
	Registrations []ReviewRow `json:"registrations"`
}

// RejectIn 是驳回。
type RejectIn struct {
	ID   api.ID `path:"id"`
	Note string `json:"note"`
}

// LayoutIn 是编队板的保存。
type LayoutIn struct {
	ID    api.ID       `path:"id"`
	Teams []LayoutTeam `json:"teams"`
}

// Routes 注册赛事域的接口。
func (m *Module) Routes(r *api.Registry) {
	reg := api.Feature(accounts.FeatureTournamentRegister)
	api.Get(r, "/api/tournaments", api.Public, m.list)
	api.Get(r, "/api/tournaments/{id}", api.Public, m.detail)
	api.Get(r, "/api/registrations/{id}", api.Member, m.registration)
	api.Get(r, "/api/me/registrations", api.Member, m.mine)

	api.Post(r, "/api/tournaments/{id}/registrations", reg, m.submit, api.NoLimit("队长提交，预检拦住重复，名单唯一约束兜底"))
	api.Post(r, "/api/registrations/{id}/withdraw", api.Member, m.withdraw, api.NoLimit("只有队长，只在截止前"))
	api.Post(r, "/api/registrations/{id}/leave", api.Member, m.leave, api.NoLimit("只有名单上的人，只在截止前"))
	api.Post(r, "/api/tournaments/{id}/signup", reg, m.signup, api.NoLimit("每人每项赛事一条，更新同一条"))
	api.Delete(r, "/api/tournaments/{id}/signup", api.Member, m.cancelSignup, api.NoLimit("只能取消自己的"))

	cap := api.Cap(accounts.CapTournamentsManage)
	list, review, board := api.Nav("tournaments", "list"), api.Nav("tournaments", "review"), api.Nav("tournaments", "board")
	api.Get(r, "/api/admin/tournaments", cap, m.adminList, list)
	api.Post(r, "/api/admin/tournaments", cap, m.create, list, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/tournaments/{id}", cap, m.adminGet, list)
	api.Patch(r, "/api/admin/tournaments/{id}", cap, m.patch, list, api.NoLimit("后台自动保存"))
	api.Delete(r, "/api/admin/tournaments/{id}", cap, m.delete, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/tournaments/{id}/publish", cap, m.publish, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/tournaments/{id}/finish", cap, m.finish, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/tournaments/{id}/cancel", cap, m.cancel, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/tournaments/{id}/copy", cap, m.copy, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/tournaments/{id}/notify", cap, m.notify, list, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/tournaments/{id}/registrations", cap, m.review, review)
	api.Post(r, "/api/admin/registrations/{id}/approve", cap, m.approve, review, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/registrations/{id}/reject", cap, m.reject, review, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/tournaments/{id}/board", cap, m.board, board)
	api.Post(r, "/api/admin/tournaments/{id}/board", cap, m.formTeams, board, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/registrations/{id}/dissolve", cap, m.dissolve, board, api.NoLimit("后台，有能力的门"))
}

func (m *Module) list(ctx *app.Ctx, _ struct{}) (GroupsOut, error) {
	g, err := m.svc.List(ctx.Context, ctx.Now().UTC())
	return GroupsOut{Groups: g}, err
}

func (m *Module) detail(ctx *app.Ctx, in IDIn) (*Page, error) { return m.svc.Detail(ctx, int64(in.ID)) }

func (m *Module) registration(ctx *app.Ctx, in IDIn) (*RegistrationPage, error) {
	return m.svc.RegistrationDetail(ctx, int64(in.ID))
}

func (m *Module) mine(ctx *app.Ctx, _ struct{}) (MineOut, error) {
	rows, err := m.svc.MyRegistrations(ctx)
	return MineOut{Registrations: rows}, err
}

func (m *Module) submit(ctx *app.Ctx, in SubmitIn) (RegistrationOut, error) {
	r, err := m.svc.Submit(ctx, SubmitInput{TournamentID: int64(in.ID), TeamID: in.TeamID, Accounts: in.Accounts})
	return RegistrationOut{Registration: r}, err
}

func (m *Module) withdraw(ctx *app.Ctx, in IDIn) (RegistrationOut, error) {
	r, err := m.svc.Withdraw(ctx, int64(in.ID))
	return RegistrationOut{Registration: r}, err
}

func (m *Module) leave(ctx *app.Ctx, in IDIn) (LeaveOut, error) {
	d, err := m.svc.LeaveAdhoc(ctx, int64(in.ID))
	return LeaveOut{Dissolved: d}, err
}

func (m *Module) signup(ctx *app.Ctx, in SignupIn) (SignupOut, error) {
	s, err := m.svc.SignUpIndividual(ctx, SignupInput{TournamentID: int64(in.ID), GameAccountID: in.GameAccountID, Roles: in.Roles})
	return SignupOut{Signup: s}, err
}

func (m *Module) cancelSignup(ctx *app.Ctx, in IDIn) (OkOut, error) {
	return OkOut{Result: "ok"}, m.svc.CancelIndividual(ctx, int64(in.ID))
}

func (m *Module) adminList(ctx *app.Ctx, _ struct{}) (AdminListOut, error) {
	rows, err := m.svc.AdminList(ctx)
	return AdminListOut{Tournaments: rows}, err
}

func (m *Module) create(ctx *app.Ctx, _ struct{}) (TournamentOut, error) {
	t, err := m.svc.CreateTournament(ctx)
	return TournamentOut{Tournament: t}, err
}

func (m *Module) adminGet(ctx *app.Ctx, in IDIn) (*AdminDetail, error) {
	return m.svc.AdminGet(ctx, int64(in.ID))
}

func (m *Module) patch(ctx *app.Ctx, in PatchIn) (*SaveResult, error) {
	return m.svc.UpdateTournament(ctx, int64(in.ID), in.BaseVersion, in.Changes)
}

func (m *Module) delete(ctx *app.Ctx, in IDIn) (OkOut, error) {
	return OkOut{Result: "ok"}, m.svc.DeleteTournament(ctx, int64(in.ID))
}

func (m *Module) publish(ctx *app.Ctx, in IDIn) (TournamentOut, error) {
	t, err := m.svc.Publish(ctx, int64(in.ID))
	return TournamentOut{Tournament: t}, err
}

func (m *Module) finish(ctx *app.Ctx, in IDIn) (TournamentOut, error) {
	t, err := m.svc.Finish(ctx, int64(in.ID))
	return TournamentOut{Tournament: t}, err
}

func (m *Module) cancel(ctx *app.Ctx, in ReasonIn) (TournamentOut, error) {
	t, err := m.svc.Cancel(ctx, int64(in.ID), in.Reason)
	return TournamentOut{Tournament: t}, err
}

func (m *Module) copy(ctx *app.Ctx, in IDIn) (TournamentOut, error) {
	t, err := m.svc.Copy(ctx, int64(in.ID))
	return TournamentOut{Tournament: t}, err
}

func (m *Module) notify(ctx *app.Ctx, in NoteIn) (NotifyOut, error) {
	n, err := m.svc.NotifyParticipants(ctx, int64(in.ID), in.Note)
	return NotifyOut{Recipients: n}, err
}

func (m *Module) review(ctx *app.Ctx, in ReviewIn) (ReviewOut, error) {
	rows, err := m.svc.ReviewList(ctx, int64(in.ID), in.Status)
	return ReviewOut{Registrations: rows}, err
}

func (m *Module) approve(ctx *app.Ctx, in IDIn) (RegistrationOut, error) {
	r, err := m.svc.Approve(ctx, int64(in.ID))
	return RegistrationOut{Registration: r}, err
}

func (m *Module) reject(ctx *app.Ctx, in RejectIn) (RegistrationOut, error) {
	r, err := m.svc.Reject(ctx, int64(in.ID), in.Note)
	return RegistrationOut{Registration: r}, err
}

func (m *Module) board(ctx *app.Ctx, in IDIn) (*Board, error) {
	return m.svc.GetBoard(ctx, int64(in.ID))
}

func (m *Module) formTeams(ctx *app.Ctx, in LayoutIn) (*FormResult, error) {
	return m.svc.FormTeams(ctx, int64(in.ID), in.Teams)
}

func (m *Module) dissolve(ctx *app.Ctx, in IDIn) (OkOut, error) {
	return OkOut{Result: "ok"}, m.svc.DissolveTeam(ctx, int64(in.ID))
}
