package members

import (
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// Module 负责成员展示和分组的路由。
type Module struct{ svc *Service }

// NewModule 造成员模块。
func NewModule(svc *Service) *Module { return &Module{svc: svc} }

// ShowcaseIn 是 GET /api/members。
type ShowcaseIn struct {
	Role string `query:"role"`
	Free bool   `query:"free"`
}

// MemberIDIn 只带用户编号。
type MemberIDIn struct {
	ID api.ID `path:"id"`
}

// GroupIDIn 只带分组编号。
type GroupIDIn struct {
	ID api.ID `path:"id"`
}

// GroupsOut 是分组列表。
type GroupsOut struct {
	Groups []GroupSummary `json:"groups"`
}

// GroupOut 包一个新建的分组。
type GroupOut struct {
	Group *Group `json:"group"`
}

// PatchGroupIn 是 PATCH /api/admin/member-groups/{id}（自动保存协议 v2）。
type PatchGroupIn struct {
	ID          api.ID       `path:"id"`
	BaseVersion int64        `json:"base_version"`
	Changes     GroupChanges `json:"changes"`
}

// PeopleIn 是组内搜人。
type PeopleIn struct {
	ID api.ID `path:"id"`
	Q  string `query:"q"`
}

// PeopleOut 是搜人的结果。
type PeopleOut struct {
	Results []Person `json:"results"`
}

// AddMemberIn 是把人加进分组。
type AddMemberIn struct {
	ID     api.ID `path:"id"`
	UserID int64  `json:"user_id"`
}

// MembershipIn 是对分组里某条成员关系的动作。
type MembershipIn struct {
	ID api.ID `path:"id"`
}

// MoveIn 是组内排序。
type MoveIn struct {
	ID   api.ID `path:"id"`
	Step int    `json:"step"`
}

// TitleIn 是改职务。
type TitleIn struct {
	ID    api.ID `path:"id"`
	Title string `json:"title"`
}

// OkOut 是没有内容要回的动作的答复。
type OkOut struct {
	Result string `json:"result"`
}

// Routes 注册成员域的接口。
func (m *Module) Routes(r *api.Registry) {
	api.Get(r, "/api/members", api.Public, m.showcase)
	api.Get(r, "/api/members/{id}", api.Public, m.detail)

	cap := api.Cap(accounts.CapMemberGroups)
	nav := api.Nav("members", "groups")
	api.Get(r, "/api/admin/member-groups", cap, m.listGroups, nav)
	api.Post(r, "/api/admin/member-groups", cap, m.createGroup, nav, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/member-groups/{id}", cap, m.getGroup, nav)
	api.Patch(r, "/api/admin/member-groups/{id}", cap, m.patchGroup, nav, api.NoLimit("后台自动保存"))
	api.Delete(r, "/api/admin/member-groups/{id}", cap, m.deleteGroup, nav, api.NoLimit("后台，有能力的门"))
	api.Get(r, "/api/admin/member-groups/{id}/people", cap, m.people, nav)
	api.Post(r, "/api/admin/member-groups/{id}/people", cap, m.addMember, nav, api.NoLimit("后台，有能力的门"))
	api.Delete(r, "/api/admin/member-group-people/{id}", cap, m.removeMember, nav, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/member-group-people/{id}/move", cap, m.moveMember, nav, api.NoLimit("后台，有能力的门"))
	api.Post(r, "/api/admin/member-group-people/{id}/title", cap, m.setTitle, nav, api.NoLimit("后台，有能力的门"))
}

func (m *Module) showcase(ctx *app.Ctx, in ShowcaseIn) (*ShowcaseResult, error) {
	return m.svc.Showcase(ctx.Context, ShowcaseInput(in), ctx.Now().UTC())
}

func (m *Module) detail(ctx *app.Ctx, in MemberIDIn) (*Page, error) {
	return m.svc.Detail(ctx, int64(in.ID))
}

func (m *Module) listGroups(ctx *app.Ctx, _ struct{}) (GroupsOut, error) {
	g, err := m.svc.ListGroups(ctx)
	return GroupsOut{Groups: g}, err
}

func (m *Module) createGroup(ctx *app.Ctx, _ struct{}) (GroupOut, error) {
	g, err := m.svc.CreateGroup(ctx)
	return GroupOut{Group: g}, err
}

func (m *Module) getGroup(ctx *app.Ctx, in GroupIDIn) (*GroupDetail, error) {
	return m.svc.GetGroup(ctx, int64(in.ID))
}

func (m *Module) patchGroup(ctx *app.Ctx, in PatchGroupIn) (*GroupSaveResult, error) {
	return m.svc.UpdateGroup(ctx, int64(in.ID), in.BaseVersion, in.Changes)
}

func (m *Module) deleteGroup(ctx *app.Ctx, in GroupIDIn) (OkOut, error) {
	return OkOut{Result: "ok"}, m.svc.DeleteGroup(ctx, int64(in.ID))
}

func (m *Module) people(ctx *app.Ctx, in PeopleIn) (PeopleOut, error) {
	p, err := m.svc.SearchPeople(ctx, int64(in.ID), in.Q)
	return PeopleOut{Results: p}, err
}

func (m *Module) addMember(ctx *app.Ctx, in AddMemberIn) (*GroupDetail, error) {
	return m.svc.AddMember(ctx, int64(in.ID), in.UserID)
}

func (m *Module) removeMember(ctx *app.Ctx, in MembershipIn) (*GroupDetail, error) {
	return m.svc.RemoveMember(ctx, int64(in.ID))
}

func (m *Module) moveMember(ctx *app.Ctx, in MoveIn) (*GroupDetail, error) {
	return m.svc.MoveMember(ctx, int64(in.ID), in.Step)
}

func (m *Module) setTitle(ctx *app.Ctx, in TitleIn) (*GroupDetail, error) {
	return m.svc.SetTitle(ctx, int64(in.ID), in.Title)
}
