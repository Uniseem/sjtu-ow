package scrims

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责内战域的路由。
type Module struct{ svc *Service }

// NewModule 造内战模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// OkOut 是没有内容要回的动作的答复。
type OkOut struct {
	Result string `json:"result"`
}

// IDIn 只带编号。
type IDIn struct {
	ID api.ID `path:"id"`
}

// ListOut 是公开列表。
type ListOut struct {
	Scrims []Card `json:"scrims"`
}

// SignupIn 是 POST /api/scrims/{id}/signup。
type SignupIn struct {
	ID            api.ID   `path:"id"`
	GameAccountID int64    `json:"game_account_id"`
	Roles         []string `json:"roles"`
}

// SignupOut 包报名。
type SignupOut struct {
	SignupID int64    `json:"signup_id"`
	Roles    []string `json:"roles"`
}

// ScrimOut 包一场内战。
type ScrimOut struct {
	Scrim *Scrim `json:"scrim"`
}

// AdminListOut 是后台内战列表。
type AdminListOut struct {
	Scrims []AdminRow `json:"scrims"`
}

// AdminGetOut 是后台读一场内战。
type AdminGetOut struct {
	Scrim *Scrim    `json:"scrim"`
	Row   *AdminRow `json:"row"`
}

// PatchIn 是 PATCH /api/admin/scrims/{id}（自动保存协议 v2）。
type PatchIn struct {
	ID          api.ID  `path:"id"`
	BaseVersion int64   `json:"base_version"`
	Changes     Changes `json:"changes"`
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

// BoardIn 是读分队页。
type BoardIn struct {
	ID    api.ID `path:"id"`
	Order string `query:"order"`
}

// SelectionIn 是勾选上场名单和生成分队。
type SelectionIn struct {
	ID               api.ID  `path:"id"`
	SignupIDs        []int64 `json:"signup_ids"`
	BaseBoardVersion int64   `json:"base_board_version"`
}

// TeamsIn 是手工保存分队。
type TeamsIn struct {
	ID               api.ID        `path:"id"`
	Placements       []PlacementIn `json:"placements"`
	BaseBoardVersion int64         `json:"base_board_version"`
}

// Routes 注册内战域的接口。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/scrims", api.Public, m.list)
	api.Get(r, "/api/scrims/{id}", api.Public, m.detail)
	api.Post(r, "/api/scrims/{id}/signup", api.Feature(accounts.FeatureScrimSignup), m.signup,
		api.NoLimit("每人每场一条，更新同一条"))
	api.Delete(r, "/api/scrims/{id}/signup", api.Member, m.cancelSignup, api.NoLimit("只能取消自己的"))

	cap := api.Cap(accounts.CapScrimsManage)
	list, board := api.Nav("scrims", "list"), api.Nav("scrims", "board")
	api.Get(r, "/api/admin/scrims", cap, m.adminList, list)
	api.Post(r, "/api/admin/scrims", cap, m.create, list, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/scrims/{id}", cap, m.adminGet, list)
	api.Patch(r, "/api/admin/scrims/{id}", cap, m.patch, list, api.NoLimit("后台自动保存"))
	api.Delete(r, "/api/admin/scrims/{id}", cap, m.delete, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/publish", cap, m.publish, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/finish", cap, m.finish, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/cancel", cap, m.cancel, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/copy", cap, m.copy, list, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/notify", cap, m.notify, list, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/scrims/{id}/board", cap, m.board, board)
	api.Post(r, "/api/admin/scrims/{id}/board/selection", cap, m.selection, board, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/board/generate", cap, m.generate, board, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/scrims/{id}/board/teams", cap, m.teams, board, api.NoLimit("后台，有能力的门"))
}

func (m *Module) list(ctx *app.Ctx, _ struct{}) (ListOut, error) {
	l, err := m.svc.List(ctx.Context, ctx.Now().UTC())
	return ListOut{Scrims: l}, err
}

func (m *Module) detail(ctx *app.Ctx, in IDIn) (*Page, error) { return m.svc.Detail(ctx, int64(in.ID)) }

func (m *Module) signup(ctx *app.Ctx, in SignupIn) (SignupOut, error) {
	g, err := m.svc.SignUp(ctx, SignupInput{ScrimID: int64(in.ID), GameAccountID: in.GameAccountID, Roles: in.Roles})
	if err != nil {
		return SignupOut{}, err
	}
	return SignupOut{SignupID: g.ID, Roles: g.Roles()}, nil
}

func (m *Module) cancelSignup(ctx *app.Ctx, in IDIn) (OkOut, error) {
	return OkOut{Result: "ok"}, m.svc.CancelSignup(ctx, int64(in.ID))
}

func (m *Module) adminList(ctx *app.Ctx, _ struct{}) (AdminListOut, error) {
	rows, err := m.svc.AdminList(ctx)
	return AdminListOut{Scrims: rows}, err
}

func (m *Module) create(ctx *app.Ctx, _ struct{}) (ScrimOut, error) {
	sc, err := m.svc.CreateScrim(ctx)
	return ScrimOut{Scrim: sc}, err
}

func (m *Module) adminGet(ctx *app.Ctx, in IDIn) (AdminGetOut, error) {
	row, sc, err := m.svc.AdminGet(ctx, int64(in.ID))
	return AdminGetOut{Scrim: sc, Row: row}, err
}

func (m *Module) patch(ctx *app.Ctx, in PatchIn) (*SaveResult, error) {
	return m.svc.UpdateScrim(ctx, int64(in.ID), in.BaseVersion, in.Changes)
}

func (m *Module) delete(ctx *app.Ctx, in IDIn) (OkOut, error) {
	return OkOut{Result: "ok"}, m.svc.DeleteScrim(ctx, int64(in.ID))
}

func (m *Module) publish(ctx *app.Ctx, in IDIn) (ScrimOut, error) {
	sc, err := m.svc.Publish(ctx, int64(in.ID))
	return ScrimOut{Scrim: sc}, err
}

func (m *Module) finish(ctx *app.Ctx, in IDIn) (ScrimOut, error) {
	sc, err := m.svc.Finish(ctx, int64(in.ID))
	return ScrimOut{Scrim: sc}, err
}

func (m *Module) cancel(ctx *app.Ctx, in IDIn) (ScrimOut, error) {
	sc, err := m.svc.Cancel(ctx, int64(in.ID))
	return ScrimOut{Scrim: sc}, err
}

func (m *Module) copy(ctx *app.Ctx, in IDIn) (ScrimOut, error) {
	sc, err := m.svc.Copy(ctx, int64(in.ID))
	return ScrimOut{Scrim: sc}, err
}

func (m *Module) notify(ctx *app.Ctx, in NoteIn) (NotifyOut, error) {
	n, err := m.svc.NotifyParticipants(ctx, int64(in.ID), in.Note)
	return NotifyOut{Recipients: n}, err
}

func (m *Module) board(ctx *app.Ctx, in BoardIn) (*Board, error) {
	return m.svc.GetBoard(ctx, int64(in.ID), in.Order)
}

func (m *Module) selection(ctx *app.Ctx, in SelectionIn) (*Board, error) {
	return m.svc.SetSelection(ctx, int64(in.ID), in.SignupIDs, in.BaseBoardVersion)
}

func (m *Module) generate(ctx *app.Ctx, in SelectionIn) (*GenerateResult, error) {
	return m.svc.Generate(ctx, int64(in.ID), in.SignupIDs, in.BaseBoardVersion)
}

func (m *Module) teams(ctx *app.Ctx, in TeamsIn) (*Board, error) {
	return m.svc.SaveTeams(ctx, int64(in.ID), in.Placements, in.BaseBoardVersion)
}
