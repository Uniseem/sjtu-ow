package accounts

import (
	"context"
	"log/slog"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ProfileChanges 区分遗漏、空字符串和明确的false。旧整表请求仍走旧分支。
type ProfileChanges struct {
	Nickname  *string `json:"nickname,omitempty"`
	IsSJTU    *bool   `json:"is_sjtu,omitempty"`
	Motto     *string `json:"motto,omitempty"`
	MainRole  *string `json:"main_role,omitempty"`
	FlexRoles *string `json:"flex_roles,omitempty"`
	ShowRank  *bool   `json:"show_rank,omitempty"`
}

// ProfileValues 只包括本人可编辑的资料，绝不返回密码、邮箱凭证或权限字段。
type ProfileValues struct {
	Nickname  string `json:"nickname"`
	IsSJTU    bool   `json:"is_sjtu"`
	Motto     string `json:"motto"`
	MainRole  string `json:"main_role"`
	FlexRoles string `json:"flex_roles"`
	ShowRank  bool   `json:"show_rank"`
}

type ProfileCurrent struct {
	Version int64         `json:"version"`
	Values  ProfileValues `json:"values"`
}

func profileValues(u *User) ProfileValues {
	return ProfileValues{
		Nickname:  u.Nickname,
		IsSJTU:    u.IsSJTU,
		Motto:     u.Motto,
		MainRole:  u.MainRole,
		FlexRoles: u.FlexRoles,
		ShowRank:  u.ShowRank,
	}
}

func validRole(role string) bool {
	return role == "tank" || role == "damage" || role == "support"
}

func cleanFlexRoles(value, main string) (string, bool) {
	wanted := map[string]bool{}
	for _, part := range strings.Split(value, ",") {
		role := strings.TrimSpace(part)
		if role == "" {
			continue
		}
		if !validRole(role) {
			return "", false
		}
		if role != main {
			wanted[role] = true
		}
	}
	var out []string
	for _, role := range []string{"tank", "damage", "support"} {
		if wanted[role] {
			out = append(out, role)
		}
	}
	return strings.Join(out, ","), true
}

func (s *Service) patchProfile(ctx *app.Ctx, in UpdateProfileInput) (*UpdateProfileResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if in.BaseVersion == nil || *in.BaseVersion < 0 {
		return nil, api.Invalid("请提供资料版本。")
	}
	now := s.clock.Now().UTC()
	out := &UpdateProfileResult{
		Result:  "ok",
		Message: "资料已保存。",
		Saved:   []string{},
		Fields:  map[string][]string{},
		SavedAt: now,
	}
	var before, after ProfileValues
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		u, err := s.store.GetByIDTx(txCtx, tx, ctx.Viewer.ID)
		if err != nil {
			return err
		}
		if u == nil || !u.IsActive {
			return api.Unauthorized("账号不存在或已停用")
		}
		before = profileValues(u)
		if u.Version != *in.BaseVersion {
			return api.Stale(ProfileCurrent{Version: u.Version, Values: before})
		}
		after = before
		ch := in.Changes
		if ch.Nickname != nil {
			value := strings.TrimSpace(*ch.Nickname)
			if err := ValidateNickname(value); err != nil {
				out.Fields["nickname"] = []string{err.Error()}
			} else {
				after.Nickname = value
				out.Saved = append(out.Saved, "nickname")
			}
		}
		if ch.Motto != nil {
			value := strings.TrimSpace(*ch.Motto)
			if err := ValidateMotto(value); err != nil {
				out.Fields["motto"] = []string{err.Error()}
			} else {
				after.Motto = value
				out.Saved = append(out.Saved, "motto")
			}
		}
		if ch.IsSJTU != nil {
			after.IsSJTU = *ch.IsSJTU
			out.Saved = append(out.Saved, "is_sjtu")
		}
		if ch.ShowRank != nil {
			after.ShowRank = *ch.ShowRank
			out.Saved = append(out.Saved, "show_rank")
		}
		// 主、副位置共同规范化：组中一个错误就不保存这个组。
		if ch.MainRole != nil || ch.FlexRoles != nil {
			main, flex := before.MainRole, before.FlexRoles
			if ch.MainRole != nil {
				main = strings.TrimSpace(*ch.MainRole)
			}
			if ch.FlexRoles != nil {
				flex = *ch.FlexRoles
			}
			mainOK := main == "" || validRole(main)
			cleaned, flexOK := cleanFlexRoles(flex, main)
			if !mainOK {
				out.Fields["main_role"] = []string{"请选择有效的主位置。"}
			}
			if !flexOK {
				out.Fields["flex_roles"] = []string{"请选择有效的位置。"}
			}
			if mainOK && flexOK {
				after.MainRole, after.FlexRoles = main, cleaned
				if ch.MainRole != nil {
					out.Saved = append(out.Saved, "main_role")
				}
				if ch.FlexRoles != nil {
					out.Saved = append(out.Saved, "flex_roles")
				}
			}
		}
		out.Version = u.Version
		if len(out.Saved) > 0 {
			if err := s.store.UpdateUserProfile(txCtx, tx, u.ID,
				after.Nickname, after.Motto, after.MainRole, after.FlexRoles,
				after.ShowRank, after.IsSJTU, now); err != nil {
				return err
			}
			out.Version++
		}
		out.Values = &after
		return nil
	})
	if err != nil {
		return nil, err
	}
	if len(out.Fields) > 0 {
		out.Message = "部分已保存，请检查标出的字段。"
	}
	// 联网送审在写事务结束后，沿用旧资料服务的失败只记录规则。
	if s.mod != nil {
		if after.Nickname != before.Nickname {
			if err := s.mod.Submit(ctx.Context, "nickname", ctx.Viewer.ID, "nickname", after.Nickname, "", ctx.Viewer.ID); err != nil {
				slog.Warn("昵称送审失败", "user", ctx.Viewer.ID, "err", err.Error())
			}
		}
		if after.Motto != "" && after.Motto != before.Motto {
			if err := s.mod.Submit(ctx.Context, "motto", ctx.Viewer.ID, "motto", after.Motto, "/members/", ctx.Viewer.ID); err != nil {
				slog.Warn("宣言送审失败", "user", ctx.Viewer.ID, "err", err.Error())
			}
		}
	}
	return out, nil
}
