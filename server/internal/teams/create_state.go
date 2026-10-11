package teams

import (
	"bytes"
	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// CreateState is read before a member fills the form. The write rechecks it
// inside its transaction; this projection grants no durable permission.
type CreateState struct {
	MaxCaptained int    `json:"max_captained"`
	Blocker      string `json:"blocker"`
	CanCreate    bool   `json:"can_create"`
}

func (m *Module) createState(ctx *app.Ctx, _ struct{}) (*CreateState, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	limits, err := m.svc.store.GetLimits(ctx.Context, m.svc.d.ReadPool())
	if err != nil {
		return nil, err
	}
	blocker, err := m.svc.createBlocker(ctx.Context, m.svc.d.ReadPool(), viewer)
	if err != nil {
		return nil, err
	}
	return &CreateState{MaxCaptained: limits.MaxCaptained, Blocker: blocker, CanCreate: blocker == ""}, nil
}

// ProfileValues contains only the team's editable fields. In particular it
// excludes applications and private game IDs from a version-conflict receipt.
type ProfileValues struct {
	Name            string   `json:"name"`
	Description     string   `json:"description"`
	IsRecruiting    bool     `json:"is_recruiting"`
	RecruitingRoles []string `json:"recruiting_roles"`
	MemberContact   string   `json:"member_contact"`
	LogoImageID     *int64   `json:"logo_image_id"`
	RemoveLogo      bool     `json:"remove_logo"`
}
type ProfileCurrent struct {
	Version int64         `json:"version"`
	Values  ProfileValues `json:"values"`
}

func profileValues(t *Team) ProfileValues {
	return ProfileValues{Name: t.Name, Description: t.Description, IsRecruiting: t.IsRecruiting,
		RecruitingRoles: t.RecruitingRoles, MemberContact: t.MemberContact, LogoImageID: t.LogoImageID}
}
func (m *Module) adminDetail(ctx *app.Ctx, in TeamIDIn) (*AdminDetail, error) {
	page, err := m.svc.Detail(ctx, int64(in.ID))
	if err != nil {
		return nil, err
	}
	return &AdminDetail{TeamPage: *page, CanEdit: !page.Team.Disbanded(),
		CanAssignCaptain: !page.Team.Disbanded(), CanDisband: !page.Team.Disbanded()}, nil
}

type AdminDetail struct {
	TeamPage
	CanEdit          bool `json:"can_edit"`
	CanAssignCaptain bool `json:"can_assign_captain"`
	CanDisband       bool `json:"can_disband"`
}

func (m *Module) extraRoutes(r *api.Registry) {
	api.Get(r, "/api/teams/create-state", api.Member, m.createState)
	api.Post(r, "/api/teams/logo", api.Feature(accounts.FeatureTeamCreate), m.prepareLogo, api.BodyLimit(16<<20), api.NoLimit("服务层检查图片日限额及建队资格"))
	api.Get(r, "/api/admin/teams/{id}", api.Superuser, m.adminDetail, api.Nav("members", "teams"))
}

// A logo can be prepared before the team exists. It still goes through the
// same ownership, format and daily-upload checks as a captain's upload.
func (m *Module) prepareLogo(ctx *app.Ctx, in PrepareLogoIn) (UploadLogoOut, error) {
	viewer, err := requireLogin(ctx)
	if err != nil {
		return UploadLogoOut{}, err
	}
	blocker, err := m.svc.createBlocker(ctx.Context, m.svc.d.ReadPool(), viewer)
	if err != nil {
		return UploadLogoOut{}, err
	}
	if blocker != "" {
		return UploadLogoOut{}, api.InvalidFields(map[string][]string{"file": {blocker}})
	}
	data, err := parseDataURL(in.DataURL)
	if err != nil || len(data) == 0 {
		return UploadLogoOut{}, api.InvalidFields(map[string][]string{"file": {"队标图片数据解析失败"}})
	}
	image, err := m.svc.UploadLogo(ctx, UploadLogoInput{FileName: in.FileName, FileSize: int64(len(data)), Reader: bytes.NewReader(data)})
	return UploadLogoOut{Image: image}, err
}

type PrepareLogoIn struct {
	FileName string `json:"file_name"`
	DataURL  string `json:"data_url"`
}
