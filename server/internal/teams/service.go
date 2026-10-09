package teams

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/base64"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// ModerationSink 是 AI 内容审核的入口（规则 90、107）。送审失败只记日志、绝不阻塞
// 操作；审核域（M6）落地后在 main 里接上，没接就不送。
type ModerationSink interface {
	Submit(ctx context.Context, targetType string, targetID int64, field, text, url string, authorID int64) error
}

// ListedEntry 是一份还列着某个人的、已提交的赛事报名名单（规则 99）。
type ListedEntry struct {
	Title     string
	ClosesAt  *time.Time
	DetailURL string
}

// RosterGuard 是战队和赛事报名之间的两个问题（规则 99、104）。赛事域（M6）落地后在
// main 里接上；没接就当没有任何报名，解散不受拦、退队信不附名单。
type RosterGuard interface {
	// LiveRegistrations 返回战队还有进行中（待审或已通过）、赛事仍是草稿或已发布的
	// 报名所在赛事的标题，按报名截止时间排。
	LiveRegistrations(ctx context.Context, q db.DBTX, teamID int64) ([]string, error)
	// EntriesStillListing 返回仍列着 userID 的、进行中的报名。
	EntriesStillListing(ctx context.Context, q db.DBTX, teamID, userID int64) ([]ListedEntry, error)
}

// Service 协调战队域的业务规则（设计 7）。
type Service struct {
	d       *db.DB
	store   *Store
	siteURL string
	limiter *ratelimit.Enforcer
	media   *media.Service
	mod     ModerationSink
	rosters RosterGuard
}

// NewService 造战队服务。limiter、media 可以是 nil（apigen、不涉及的测试）。
func NewService(d *db.DB, siteURL string, limiter *ratelimit.Enforcer, m *media.Service) *Service {
	return &Service{d: d, store: NewStore(d), siteURL: strings.TrimRight(siteURL, "/"), limiter: limiter, media: m}
}

// SetModeration 接上 AI 审核。
func (s *Service) SetModeration(m ModerationSink) { s.mod = m }

// SetRosterGuard 接上赛事报名的检查。
func (s *Service) SetRosterGuard(g RosterGuard) { s.rosters = g }

// ---------------------------------------------------------------------------
// 小工具
// ---------------------------------------------------------------------------

func deny(msg string) *api.Error { return api.NewErr(http.StatusForbidden, "forbidden", msg) }

func refuse(msg string) *api.Error { return api.NewErr(http.StatusConflict, "refused", msg) }

func isUnique(err error) bool {
	return err != nil && strings.Contains(err.Error(), "UNIQUE constraint failed")
}

func requireLogin(ctx *app.Ctx) (*app.Viewer, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	return ctx.Viewer, nil
}

func (s *Service) user(ctx context.Context, q db.DBTX, id int64) (*UserBrief, error) {
	return s.store.GetUserBrief(ctx, q, id)
}

// isManager 报 viewer 是不是这支队的队长，或超管。
func (s *Service) isManager(ctx context.Context, q db.DBTX, v *app.Viewer, teamID int64) (bool, error) {
	if v == nil {
		return false, nil
	}
	if v.Superuser {
		return true, nil
	}
	m, err := s.store.GetMembership(ctx, q, teamID, v.ID)
	if err != nil {
		return false, err
	}
	return m != nil && m.Role == RoleCaptain, nil
}

func (s *Service) submitModeration(ctx context.Context, t *Team, authorID int64, name, description bool) {
	if s.mod == nil {
		return
	}
	url := fmt.Sprintf("/teams/%d/", t.ID)
	if name {
		if err := s.mod.Submit(ctx, "team_name", t.ID, "name", t.Name, url, authorID); err != nil {
			slog.Warn("送审失败", "target", "team_name", "id", t.ID, "err", err.Error())
		}
	}
	if description && t.Description != "" {
		if err := s.mod.Submit(ctx, "team_description", t.ID, "description", t.Description, url, authorID); err != nil {
			slog.Warn("送审失败", "target", "team_description", "id", t.ID, "err", err.Error())
		}
	}
}

// ---------------------------------------------------------------------------
// 资料校验（规则 83、87、90、106）
// ---------------------------------------------------------------------------

func validName(name string) (string, string) {
	name = strings.TrimSpace(name)
	n := utf8.RuneCountInString(name)
	if n < NameMin || n > NameMax {
		return name, fmt.Sprintf("队名要 %d 到 %d 个字。", NameMin, NameMax)
	}
	return name, ""
}

func validDescription(v string) (string, string) {
	v = strings.TrimSpace(v)
	if utf8.RuneCountInString(v) > DescriptionMax {
		return v, fmt.Sprintf("简介最多 %d 字。", DescriptionMax)
	}
	return v, ""
}

func validContact(v string) (string, string) {
	v = strings.TrimSpace(v)
	if utf8.RuneCountInString(v) > MemberContactMax {
		return v, fmt.Sprintf("队内联系方式最多 %d 字。", MemberContactMax)
	}
	return v, ""
}

// checkLogo 要求队标是自己传的、在「队标」集合里的图（规则 106）。
func (s *Service) checkLogo(ctx context.Context, q db.DBTX, v *app.Viewer, imageID int64) string {
	var uploader sql.NullInt64
	var key sql.NullString
	err := q.QueryRowContext(ctx, `SELECT i.uploader_id, c.key FROM images i
		LEFT JOIN image_collections c ON c.id = i.collection_id WHERE i.id = ?`, imageID).Scan(&uploader, &key)
	if err != nil {
		return "队标图片不存在。"
	}
	if !key.Valid || key.String != "team_logo" {
		return "队标要先用队标上传入口上传。"
	}
	if !v.Superuser && (!uploader.Valid || uploader.Int64 != v.ID) {
		return "只能用自己上传的图片当队标。"
	}
	return ""
}

// UploadLogoInput 是队标上传（规则 106：只收 JPG、PNG、WebP，不超过 5MB）。
type UploadLogoInput struct {
	FileName string
	FileSize int64
	Reader   io.Reader
}

// UploadLogo 把队标存进「队标」集合，返回图片。图片管线（尺寸、转码、去 EXIF）在
// media.Upload，这里只管战队自己的两条限制。
func (s *Service) UploadLogo(ctx *app.Ctx, in UploadLogoInput) (*media.Image, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	if s.media == nil {
		return nil, fmt.Errorf("图片服务没有接上")
	}
	if !v.CanUse(accounts.FeatureTeamCreate) {
		return nil, api.Forbidden()
	}
	if in.FileSize > LogoMaxBytes {
		return nil, api.InvalidFields(map[string][]string{"logo": {"队标不能超过 5MB。"}})
	}
	switch strings.ToLower(filepath.Ext(in.FileName)) {
	case ".jpg", ".jpeg", ".png", ".webp":
	default:
		return nil, api.InvalidFields(map[string][]string{"logo": {"队标只支持 JPG、PNG 或 WebP。"}})
	}
	return s.media.Upload(ctx, media.UploadInput{
		Title: "队标", FileName: in.FileName, CollectionKey: "team_logo",
		Reader: in.Reader, FileSize: in.FileSize,
	})
}

func parseDataURL(s string) ([]byte, error) {
	s = strings.TrimSpace(s)
	if strings.HasPrefix(s, "data:") {
		parts := strings.SplitN(s, ",", 2)
		if len(parts) == 2 {
			return base64.StdEncoding.DecodeString(parts[1])
		}
	}
	return base64.StdEncoding.DecodeString(s)
}

// SetTeamLogo 设置战队队标（规则 106）。
func (s *Service) SetTeamLogo(ctx *app.Ctx, teamID int64, fileName, dataURL string) (*media.Image, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}

	t, err := s.store.GetTeam(ctx.Context, s.d.ReadPool(), teamID)
	if err != nil {
		return nil, err
	}
	if t == nil {
		return nil, api.NotFound("战队不存在")
	}
	mgr, err := s.isManager(ctx.Context, s.d.ReadPool(), v, teamID)
	if err != nil {
		return nil, err
	}
	if !mgr {
		return nil, api.Forbidden()
	}

	raw, err := parseDataURL(dataURL)
	if err != nil || len(raw) == 0 {
		return nil, api.Invalid("队标图片数据解析失败")
	}

	img, err := s.UploadLogo(ctx, UploadLogoInput{
		FileName: fileName,
		FileSize: int64(len(raw)),
		Reader:   bytes.NewReader(raw),
	})
	if err != nil {
		return nil, err
	}

	oldLogo := t.LogoImageID
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `UPDATE teams SET logo_image_id = ?, version = version + 1, updated_at = ? WHERE id = ?`,
			img.ID, db.FormatUTC(ctx.Now().UTC()), teamID)
		return err
	})
	if err != nil {
		return nil, err
	}

	if oldLogo != nil {
		s.discardLogo(ctx, *oldLogo)
	}

	return img, nil
}

// discardLogo 一张没有战队再用的队标连文件一起删掉（规则 106，219）。只删「队标」集合里的。
func (s *Service) discardLogo(ctx *app.Ctx, imageID int64) {
	if s.media == nil || imageID <= 0 {
		return
	}
	var key sql.NullString
	var used int
	rd := s.d.ReadPool()
	_ = rd.QueryRowContext(ctx.Context, `SELECT c.key FROM images i
		LEFT JOIN image_collections c ON c.id = i.collection_id WHERE i.id = ?`, imageID).Scan(&key)
	_ = rd.QueryRowContext(ctx.Context, `SELECT COUNT(*) FROM teams WHERE logo_image_id = ?`, imageID).Scan(&used)
	if !key.Valid || key.String != "team_logo" || used > 0 {
		return
	}
	if err := s.media.DeleteImage(ctx, imageID); err != nil {
		slog.Warn("删除队标失败", "image", imageID, "err", err.Error())
	}
}

// ---------------------------------------------------------------------------
// 建队（规则 83–86）
// ---------------------------------------------------------------------------

// CreateTeamInput 是建队的入参。
type CreateTeamInput struct {
	Name            string   `json:"name"`
	Description     string   `json:"description"`
	IsRecruiting    *bool    `json:"is_recruiting,omitempty"`
	RecruitingRoles []string `json:"recruiting_roles,omitempty"`
	LogoImageID     *int64   `json:"logo_image_id,omitempty"`
}

// createBlocker 说明这个人现在为什么建不了队，没有就返回空串。
func (s *Service) createBlocker(ctx context.Context, q db.DBTX, v *app.Viewer) (string, error) {
	if !v.CanUse(accounts.FeatureTeamCreate) {
		return accounts.FeatureDeniedMessage, nil
	}
	lim, err := s.store.GetLimits(ctx, q)
	if err != nil {
		return "", err
	}
	n, err := s.store.CaptainedCount(ctx, q, v.ID)
	if err != nil {
		return "", err
	}
	if n >= lim.MaxCaptained {
		return fmt.Sprintf("每人最多同时担任 %d 支战队的队长。", lim.MaxCaptained), nil
	}
	return "", nil
}

// CreateTeam 建队，建的人当队长（规则 83–85）。
func (s *Service) CreateTeam(ctx *app.Ctx, in CreateTeamInput) (*Team, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	fields := map[string][]string{}
	name, msg := validName(in.Name)
	if msg != "" {
		fields["name"] = []string{msg}
	}
	desc, msg := validDescription(in.Description)
	if msg != "" {
		fields["description"] = []string{msg}
	}
	recruiting := true
	if in.IsRecruiting != nil {
		recruiting = *in.IsRecruiting
	}
	if in.LogoImageID != nil {
		if m := s.checkLogo(ctx.Context, s.d.ReadPool(), v, *in.LogoImageID); m != "" {
			fields["logo_image_id"] = []string{m}
		}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}
	if blocker, err := s.createBlocker(ctx.Context, s.d.ReadPool(), v); err != nil {
		return nil, err
	} else if blocker != "" {
		return nil, api.InvalidFields(map[string][]string{"__all__": {blocker}})
	}
	if taken, err := s.store.NameTaken(ctx.Context, s.d.ReadPool(), name, 0); err != nil {
		return nil, err
	} else if taken {
		return nil, api.InvalidFields(map[string][]string{"name": {NameTaken}})
	}
	// 只有表单合法、也没有重名才数一次（规则 84）。
	if s.limiter != nil {
		retry, ok, err := s.limiter.Allow(ctx.Context, fmt.Sprintf("u:%d", v.ID), ratelimit.TeamCreate)
		if err != nil {
			return nil, err
		}
		if !ok {
			return nil, api.TooManyRequests(retry)
		}
	}

	now := ctx.Now().UTC()
	var team *Team
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		// 事务里再查一遍（规则 85）：两个请求同时过了外面的检查，不能都建成。
		if blocker, err := s.createBlocker(txCtx, tx, v); err != nil {
			return err
		} else if blocker != "" {
			return api.InvalidFields(map[string][]string{"__all__": {blocker}})
		}
		if taken, err := s.store.NameTaken(txCtx, tx, name, 0); err != nil {
			return err
		} else if taken {
			return api.InvalidFields(map[string][]string{"name": {NameTaken}})
		}
		var logo any
		if in.LogoImageID != nil {
			logo = *in.LogoImageID
		}
		res, err := tx.ExecContext(txCtx, `INSERT INTO teams
			(name, description, logo_image_id, is_recruiting, recruiting_roles, member_contact, version, created_at, updated_at)
			VALUES (?, ?, ?, ?, ?, '', 1, ?, ?)`,
			name, desc, logo, b2i(recruiting), accounts.JoinRoles(in.RecruitingRoles),
			db.FormatUTC(now), db.FormatUTC(now))
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `INSERT INTO team_memberships (team_id, user_id, role, joined_at)
			VALUES (?, ?, 'captain', ?)`, id, v.ID, db.FormatUTC(now)); err != nil {
			return err
		}
		team, err = s.store.GetTeam(txCtx, tx, id)
		return err
	})
	if isUnique(err) {
		return nil, api.InvalidFields(map[string][]string{"name": {NameTaken}})
	}
	if err != nil {
		if in.LogoImageID != nil {
			s.discardLogo(ctx, *in.LogoImageID) // 建队失败，刚传的队标立刻删掉（规则 106）
		}
		return nil, err
	}
	s.submitModeration(ctx.Context, team, v.ID, true, true)
	return team, nil
}

// ---------------------------------------------------------------------------
// 改资料（规则 87、106、107；自动保存协议 v2）
// ---------------------------------------------------------------------------

// ProfileChanges 是这次要改的字段，没出现的不动。
type ProfileChanges struct {
	Name            *string   `json:"name,omitempty"`
	Description     *string   `json:"description,omitempty"`
	IsRecruiting    *bool     `json:"is_recruiting,omitempty"`
	RecruitingRoles *[]string `json:"recruiting_roles,omitempty"`
	MemberContact   *string   `json:"member_contact,omitempty"`
	LogoImageID     *int64    `json:"logo_image_id,omitempty"`
	RemoveLogo      *bool     `json:"remove_logo,omitempty"`
}

// SaveResult 是自动保存的回答（12 号文档 5.5）：存了哪些、哪些字段有问题。
type SaveResult struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	SavedAt time.Time           `json:"saved_at"`
}

// UpdateTeam 按字段保存资料：合法的存，不合法的留旧值并报错。队长或超管才能改；
// 队名同样查重。base_version 落后就 409。
func (s *Service) UpdateTeam(ctx *app.Ctx, teamID, baseVersion int64, ch ProfileChanges) (*SaveResult, error) {
	v, err := requireLogin(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	res := &SaveResult{Fields: map[string][]string{}, SavedAt: now}
	var oldLogo *int64
	var nameChanged, descChanged bool
	var team *Team

	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		t, err := s.store.GetTeam(txCtx, tx, teamID)
		if err != nil {
			return err
		}
		if t == nil {
			return api.NotFound("战队不存在")
		}
		ok, err := s.isManager(txCtx, tx, v, teamID)
		if err != nil {
			return err
		}
		if !ok {
			return deny("只有队长可以修改战队资料。")
		}
		if t.Disbanded() {
			return refuse("战队已解散。")
		}
		if baseVersion != t.Version {
			return api.NewErr(http.StatusConflict, "stale", "另一个人刚改过，已换成最新内容")
		}

		var sets []string
		var args []any
		set := func(field, col string, val any) {
			sets = append(sets, col+" = ?")
			args = append(args, val)
			res.Saved = append(res.Saved, field)
		}
		if ch.Name != nil {
			name, msg := validName(*ch.Name)
			if msg == "" {
				if taken, err := s.store.NameTaken(txCtx, tx, name, teamID); err != nil {
					return err
				} else if taken {
					msg = NameTaken
				}
			}
			if msg != "" {
				res.Fields["name"] = []string{msg}
			} else if name != t.Name {
				set("name", "name", name)
				nameChanged = true
			}
		}
		if ch.Description != nil {
			desc, msg := validDescription(*ch.Description)
			if msg != "" {
				res.Fields["description"] = []string{msg}
			} else if desc != t.Description {
				set("description", "description", desc)
				descChanged = true
			}
		}
		if ch.IsRecruiting != nil && *ch.IsRecruiting != t.IsRecruiting {
			set("is_recruiting", "is_recruiting", b2i(*ch.IsRecruiting))
		}
		if ch.RecruitingRoles != nil {
			joined := accounts.JoinRoles(*ch.RecruitingRoles)
			if joined != strings.Join(t.RecruitingRoles, ",") {
				set("recruiting_roles", "recruiting_roles", joined)
			}
		}
		if ch.MemberContact != nil {
			c, msg := validContact(*ch.MemberContact)
			if msg != "" {
				res.Fields["member_contact"] = []string{msg}
			} else if c != t.MemberContact {
				set("member_contact", "member_contact", c)
			}
		}
		switch {
		case ch.RemoveLogo != nil && *ch.RemoveLogo && t.LogoImageID != nil:
			set("logo_image_id", "logo_image_id", nil)
			oldLogo = t.LogoImageID
		case ch.LogoImageID != nil && (t.LogoImageID == nil || *t.LogoImageID != *ch.LogoImageID):
			if m := s.checkLogo(txCtx, tx, v, *ch.LogoImageID); m != "" {
				res.Fields["logo_image_id"] = []string{m}
			} else {
				set("logo_image_id", "logo_image_id", *ch.LogoImageID)
				oldLogo = t.LogoImageID
			}
		}

		res.Version = t.Version
		if len(sets) > 0 {
			sets = append(sets, "version = version + 1", "updated_at = ?")
			args = append(args, db.FormatUTC(now), teamID)
			if _, err := tx.ExecContext(txCtx, `UPDATE teams SET `+strings.Join(sets, ", ")+` WHERE id = ?`, args...); err != nil {
				return err
			}
			res.Version = t.Version + 1
		}
		team, err = s.store.GetTeam(txCtx, tx, teamID)
		return err
	})
	if isUnique(err) {
		return nil, api.InvalidFields(map[string][]string{"name": {NameTaken}})
	}
	if err != nil {
		return nil, err
	}
	if len(res.Fields) == 0 {
		res.Fields = nil
	}
	if oldLogo != nil {
		s.discardLogo(ctx, *oldLogo)
	}
	if team != nil {
		s.submitModeration(ctx.Context, team, v.ID, nameChanged, descChanged)
	}
	return res, nil
}
