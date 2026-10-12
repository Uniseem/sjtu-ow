package backoffice

import (
	"context"
	"database/sql"
	"strings"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func (m *Module) managementRoutes(r *api.Registry) {
	users := api.Nav("members", "users")
	roles := api.Nav("members", "roles")
	reviews := api.Nav("review", "registrations")
	api.Get(r, "/api/admin/users/search", api.Superuser, m.searchUsers, users)
	api.Get(r, "/api/admin/home", api.Cap(accounts.CapAdminEnter), m.home, api.Nav("home", "home"))
	api.Patch(r, "/api/admin/users/{id}", api.Superuser, m.patchUser, users, api.NoLimit("后台超管逐字段自动保存，乐观版本保护"))
	api.Get(r, "/api/admin/users/{id}/feature-rules", api.Superuser, m.userRules, users)
	api.Post(r, "/api/admin/users/{id}/feature-rules", api.Superuser, m.addUserRule, users, api.NoLimit("超管单条功能规则，唯一约束保护"))
	api.Delete(r, "/api/admin/users/{id}/feature-rules/{rule}", api.Superuser, m.deleteUserRule, users, api.NoLimit("超管删除本人指定的单条规则"))
	api.Get(r, "/api/admin/roles", api.Superuser, m.roles, roles)
	api.Post(r, "/api/admin/roles/{id}/restrictions", api.Superuser, m.addRestriction, roles, api.NoLimit("超管单角色单功能唯一限制"))
	api.Delete(r, "/api/admin/roles/{id}/restrictions/{rule}", api.Superuser, m.deleteRestriction, roles, api.NoLimit("超管删除指定角色的单功能限制"))
	api.Get(r, "/api/admin/registrations", api.Cap(accounts.CapTournamentsManage), m.registrations, reviews)
	api.Get(r, "/api/admin/registrations/{id}", api.Cap(accounts.CapTournamentsManage), m.registration, reviews)
	api.Post(r, "/api/admin/registrations/export", api.Cap(accounts.CapTournamentsManage), m.exportRegistrations, reviews, api.NoLimit("后台按筛选导出，隐私导出留操作记录"))
	api.Post(r, "/api/admin/registrations/bulk-approve", api.Cap(accounts.CapTournamentsManage), m.bulkApprove, reviews, api.NoLimit("干部批量审核，最多50份，各调用原赛事事务服务"))
}

func require(ctx *app.Ctx, cap app.Cap, superuser bool) error {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.ID <= 0 || ctx.Viewer.Disabled {
		return api.Unauthorized("要先登录")
	}
	if superuser {
		if !ctx.Viewer.Superuser {
			return api.Forbidden()
		}
	} else if !ctx.Viewer.HasCap(cap) {
		return api.Forbidden()
	}
	return nil
}

func requireUser(ctx context.Context, q db.DBTX, id int64) error {
	var count int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM users WHERE id = ?`, id).Scan(&count); err != nil {
		return err
	}
	if count == 0 {
		return api.NotFound("用户不存在")
	}
	return nil
}

type IDIn struct {
	ID api.ID `path:"id"`
}
type UserChanges struct {
	Nickname *string `json:"nickname,omitempty"`
	IsSJTU   *bool   `json:"is_sjtu,omitempty"`
}
type PatchUserIn struct {
	ID          api.ID      `path:"id"`
	BaseVersion int64       `json:"base_version"`
	Changes     UserChanges `json:"changes"`
}
type SaveOut struct {
	Values  map[string]any      `json:"values,omitempty"`
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	SavedAt string              `json:"saved_at"`
}

func (s *Service) patchUser(ctx *app.Ctx, in PatchUserIn) (SaveOut, error) {
	out := SaveOut{Saved: []string{}, Fields: map[string][]string{}, Values: map[string]any{}}
	if err := require(ctx, "", true); err != nil {
		return out, err
	}
	if in.BaseVersion < 1 {
		return out, api.InvalidFields(map[string][]string{"base_version": {"请先重新加载资料。"}})
	}
	now := ctx.Now().UTC()
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		var version int64
		var nickname string
		var sjtu int
		err := tx.QueryRowContext(txCtx, `SELECT version, nickname, is_sjtu FROM users WHERE id = ?`, int64(in.ID)).Scan(&version, &nickname, &sjtu)
		if err == sql.ErrNoRows {
			return api.NotFound("用户不存在")
		}
		if err != nil {
			return err
		}
		out.Version = version
		if in.BaseVersion != version {
			return api.Stale(map[string]any{"version": version, "values": map[string]any{"nickname": nickname, "is_sjtu": sjtu == 1}})
		}
		changed := false
		if in.Changes.Nickname != nil {
			next := strings.TrimSpace(*in.Changes.Nickname)
			if err := accounts.ValidateNickname(next); err != nil {
				out.Fields["nickname"] = []string{err.Error()}
			} else {
				changed = changed || next != nickname
				nickname = next
				out.Saved = append(out.Saved, "nickname")
				out.Values["nickname"] = nickname
			}
		}
		if in.Changes.IsSJTU != nil {
			next := 0
			if *in.Changes.IsSJTU {
				next = 1
			}
			changed = changed || sjtu != next
			sjtu = next
			out.Saved = append(out.Saved, "is_sjtu")
			out.Values["is_sjtu"] = sjtu == 1
		}
		if changed {
			if _, err := tx.ExecContext(txCtx, `UPDATE users SET nickname = ?, is_sjtu = ?, version = version + 1, updated_at = ? WHERE id = ? AND version = ?`, nickname, sjtu, db.FormatUTC(now), int64(in.ID), version); err != nil {
				return err
			}
			out.Version++
			if err := audit.Record(txCtx, tx, ctx.Viewer.ID, "user.update", "user", int64(in.ID), map[string]any{"saved": out.Saved}, now); err != nil {
				return err
			}
		}
		return nil
	})
	out.SavedAt = db.FormatUTC(now)
	return out, err
}

type FeatureChoice struct {
	Key   string `json:"key"`
	Label string `json:"label"`
}
type FeatureRule struct {
	ID      int64  `json:"id"`
	Feature string `json:"feature"`
	Allowed bool   `json:"allowed"`
	Note    string `json:"note"`
}
type UserRulesOut struct {
	Rules    []FeatureRule   `json:"rules"`
	Features []FeatureChoice `json:"features"`
}

var features = []FeatureChoice{
	{"team_create", "创建战队"}, {"team_apply", "申请加入战队"}, {"tournament_register", "报名赛事"},
	{"scrim_signup", "报名内战"}, {"article_submit", "投稿"}, {"article_comment", "评论文章"}, {"avatar_upload", "上传头像"},
}

func featureID(name string) int64 {
	for i, choice := range features {
		if choice.Key == name {
			return int64(i + 1)
		}
	}
	return 0
}
func featureName(id int64) string {
	if id < 1 || id > int64(len(features)) {
		return ""
	}
	return features[id-1].Key
}
func featureChoices() []FeatureChoice { return append([]FeatureChoice{}, features...) }

func readUserRules(ctx context.Context, q db.DBTX, id int64) (UserRulesOut, error) {
	out := UserRulesOut{Rules: []FeatureRule{}, Features: featureChoices()}
	if err := requireUser(ctx, q, id); err != nil {
		return out, err
	}
	rows, err := q.QueryContext(ctx, `SELECT feature, denied, note FROM feature_user_rules WHERE user_id = ? ORDER BY feature`, id)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var rule FeatureRule
		var denied int
		if err := rows.Scan(&rule.Feature, &denied, &rule.Note); err != nil {
			return out, err
		}
		rule.ID = featureID(rule.Feature)
		rule.Allowed = denied == 0
		if rule.ID > 0 {
			out.Rules = append(out.Rules, rule)
		}
	}
	return out, rows.Err()
}
func (s *Service) userRules(ctx *app.Ctx, in IDIn) (UserRulesOut, error) {
	if err := require(ctx, "", true); err != nil {
		return UserRulesOut{}, err
	}
	return readUserRules(ctx.Context, s.d.ReadPool(), int64(in.ID))
}

type AddUserRuleIn struct {
	ID      api.ID `path:"id"`
	Feature string `json:"feature"`
	Allowed bool   `json:"allowed"`
	Note    string `json:"note"`
}
type RuleIDIn struct {
	ID   api.ID `path:"id"`
	Rule api.ID `path:"rule"`
}

func noteProblem(note string) error {
	if utf8.RuneCountInString(note) > 200 {
		return api.InvalidFields(map[string][]string{"note": {"说明不能超过200字。"}})
	}
	return nil
}
func (s *Service) addUserRule(ctx *app.Ctx, in AddUserRuleIn) (UserRulesOut, error) {
	if err := require(ctx, "", true); err != nil {
		return UserRulesOut{}, err
	}
	if featureID(in.Feature) == 0 {
		return UserRulesOut{}, api.InvalidFields(map[string][]string{"feature": {"请选择有效功能。"}})
	}
	in.Note = strings.TrimSpace(in.Note)
	if err := noteProblem(in.Note); err != nil {
		return UserRulesOut{}, err
	}
	now := ctx.Now().UTC()
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := requireUser(txCtx, tx, int64(in.ID)); err != nil {
			return err
		}
		var count int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM feature_user_rules WHERE user_id = ? AND feature = ?`, int64(in.ID), in.Feature).Scan(&count); err != nil {
			return err
		}
		if count > 0 {
			return api.InvalidFields(map[string][]string{"feature": {"这项功能已有单独规则，请先删除原规则。"}})
		}
		denied := 1
		if in.Allowed {
			denied = 0
		}
		if _, err := tx.ExecContext(txCtx, `INSERT INTO feature_user_rules (user_id, feature, denied, note, created_at) VALUES (?, ?, ?, ?, ?)`, int64(in.ID), in.Feature, denied, in.Note, db.FormatUTC(now)); err != nil {
			return err
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "feature_rule.add", "user", int64(in.ID), map[string]any{"feature": in.Feature, "allowed": in.Allowed, "note": in.Note}, now)
	})
	if err != nil {
		return UserRulesOut{}, err
	}
	return readUserRules(ctx.Context, s.d.ReadPool(), int64(in.ID))
}
func (s *Service) deleteUserRule(ctx *app.Ctx, in RuleIDIn) (UserRulesOut, error) {
	if err := require(ctx, "", true); err != nil {
		return UserRulesOut{}, err
	}
	feature := featureName(int64(in.Rule))
	if feature == "" {
		return UserRulesOut{}, api.NotFound("规则不存在")
	}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := requireUser(txCtx, tx, int64(in.ID)); err != nil {
			return err
		}
		result, err := tx.ExecContext(txCtx, `DELETE FROM feature_user_rules WHERE user_id = ? AND feature = ?`, int64(in.ID), feature)
		if err != nil {
			return err
		}
		n, err := result.RowsAffected()
		if err != nil {
			return err
		}
		if n == 0 {
			return api.NotFound("规则不存在")
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "feature_rule.delete", "user", int64(in.ID), map[string]any{"feature": feature}, ctx.Now().UTC())
	})
	if err != nil {
		return UserRulesOut{}, err
	}
	return readUserRules(ctx.Context, s.d.ReadPool(), int64(in.ID))
}
