package backoffice

import (
	"context"
	"hash/fnv"
	"sort"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type RoleGroup struct {
	ID           int64         `json:"id"`
	Name         string        `json:"name"`
	Label        string        `json:"label"`
	Summary      string        `json:"summary"`
	People       int           `json:"people"`
	Assignable   bool          `json:"assignable"`
	Restrictions []FeatureRule `json:"restrictions"`
}
type RolesOut struct {
	Groups   []RoleGroup     `json:"groups"`
	Features []FeatureChoice `json:"features"`
}

var standardRoles = []RoleGroup{
	{ID: 1, Name: accounts.RoleContentEditor, Label: "内容编辑", Summary: "编辑、发布全站内容，管理分类、图片、成员分组和评论。", Assignable: true},
	{ID: 2, Name: accounts.RoleCertifiedAuthor, Label: "认证作者", Summary: "撰写并发布自己的文章，上传投稿图片。", Assignable: true},
	{ID: 3, Name: accounts.RoleTournamentAdmin, Label: "赛事管理员", Summary: "管理赛事，审核报名和编排队伍。", Assignable: true},
	{ID: 4, Name: accounts.RoleScrimAdmin, Label: "内战管理员", Summary: "管理内战，报名、分队和通知。", Assignable: true},
	{ID: 5, Name: accounts.RoleContributor, Label: "投稿者", Summary: "注册并验证邮箱后，可提交自己的文章。", Assignable: false},
	{ID: 6, Name: accounts.RoleSJTU, Label: "交大用户", Summary: "是否来自交大，由用户资料自动维护。", Assignable: false},
	{ID: 7, Name: accounts.RoleExternal, Label: "校外用户", Summary: "非交大用户，由用户资料自动维护。", Assignable: false},
}

// Built-in roles have documented fixed ids; manual roles use stable 52-bit ids.
// Neither map ordering nor inserting a new manual role can retarget a deletion.
func roleID(name string) int64 {
	for _, role := range standardRoles {
		if role.Name == name {
			return role.ID
		}
	}
	h := fnv.New64a()
	_, _ = h.Write([]byte(name))
	return int64(h.Sum64()&((1<<52)-1)) + 100
}
func standardRole(name string) (RoleGroup, bool) {
	for _, role := range standardRoles {
		if role.Name == name {
			return role, true
		}
	}
	return RoleGroup{}, false
}

func knownRoles(ctx context.Context, q db.DBTX) ([]RoleGroup, error) {
	out := append([]RoleGroup{}, standardRoles...)
	rows, err := q.QueryContext(ctx, `SELECT role FROM user_roles UNION SELECT role FROM feature_role_restrictions ORDER BY role`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	ids := map[int64]string{}
	for _, role := range out {
		ids[role.ID] = role.Name
	}
	for rows.Next() {
		var name string
		if err := rows.Scan(&name); err != nil {
			return nil, err
		}
		if _, builtin := standardRole(name); builtin {
			continue
		}
		id := roleID(name)
		if previous, exists := ids[id]; exists && previous != name {
			return nil, api.Invalid("角色编号冲突，请联系管理员。")
		}
		ids[id] = name
		out = append(out, RoleGroup{ID: id, Name: name, Label: name, Summary: "手工分组。功能限制在这里管理；角色权限在底层后台维护。", Assignable: true})
	}
	return out, rows.Err()
}

func roleByID(ctx context.Context, q db.DBTX, id int64) (RoleGroup, error) {
	roles, err := knownRoles(ctx, q)
	if err != nil {
		return RoleGroup{}, err
	}
	for _, role := range roles {
		if role.ID == id {
			return role, nil
		}
	}
	return RoleGroup{}, api.NotFound("角色不存在")
}

func readRoleRules(ctx context.Context, q db.DBTX) (map[string][]FeatureRule, error) {
	rows, err := q.QueryContext(ctx, `SELECT role, feature, note FROM feature_role_restrictions ORDER BY role, feature`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string][]FeatureRule{}
	for rows.Next() {
		var role string
		var restriction FeatureRule
		if err := rows.Scan(&role, &restriction.Feature, &restriction.Note); err != nil {
			return nil, err
		}
		restriction.ID = featureID(restriction.Feature)
		restriction.Allowed = false
		if restriction.ID > 0 {
			out[role] = append(out[role], restriction)
		}
	}
	return out, rows.Err()
}

type rolePerson struct {
	id        int64
	sjtu      bool
	active    bool
	verified  bool
	superuser bool
}

func rolePeople(ctx context.Context, q db.DBTX, restrictions map[string][]FeatureRule) (map[string]int, error) {
	// Four bounded-shape scans calculate real derived roles with no per-user SELECT.
	rows, err := q.QueryContext(ctx, `SELECT id, is_sjtu, is_active, email_verified_at IS NOT NULL, is_superuser FROM users`)
	if err != nil {
		return nil, err
	}
	people := []rolePerson{}
	for rows.Next() {
		var person rolePerson
		if err := rows.Scan(&person.id, &person.sjtu, &person.active, &person.verified, &person.superuser); err != nil {
			rows.Close()
			return nil, err
		}
		people = append(people, person)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	userRoles := map[int64][]string{}
	rows, err = q.QueryContext(ctx, `SELECT user_id, role FROM user_roles`)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var id int64
		var role string
		if err := rows.Scan(&id, &role); err != nil {
			rows.Close()
			return nil, err
		}
		userRoles[id] = append(userRoles[id], role)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	submissionRules := map[int64]bool{}
	rows, err = q.QueryContext(ctx, `SELECT user_id, denied FROM feature_user_rules WHERE feature = ?`, string(accounts.FeatureArticleSubmit))
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var id int64
		var denied bool
		if err := rows.Scan(&id, &denied); err != nil {
			rows.Close()
			return nil, err
		}
		submissionRules[id] = !denied
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	roleRestrictions := map[string]map[app.Feature]bool{}
	for role, rules := range restrictions {
		roleRestrictions[role] = map[app.Feature]bool{}
		for _, rule := range rules {
			roleRestrictions[role][app.Feature(rule.Feature)] = true
		}
	}
	counts := map[string]int{}
	for _, person := range people {
		stored := userRoles[person.id]
		for _, role := range stored {
			counts[role]++
		}
		rules := map[app.Feature]bool{}
		if allowed, exists := submissionRules[person.id]; exists {
			rules[accounts.FeatureArticleSubmit] = allowed
		}
		user := &accounts.User{ID: person.id, IsActive: person.active, IsSJTU: person.sjtu, IsSuperuser: person.superuser}
		canSubmit, err := accounts.CanUse(user, accounts.FeatureArticleSubmit, rules, roleRestrictions, stored)
		if err != nil {
			return nil, err
		}
		for _, role := range accounts.DerivedRoles(person.sjtu, person.active, person.verified, canSubmit) {
			counts[role]++
		}
	}
	return counts, nil
}

func readRoles(ctx context.Context, q db.DBTX) (RolesOut, error) {
	out := RolesOut{Groups: []RoleGroup{}, Features: featureChoices()}
	groups, err := knownRoles(ctx, q)
	if err != nil {
		return out, err
	}
	restrictions, err := readRoleRules(ctx, q)
	if err != nil {
		return out, err
	}
	counts, err := rolePeople(ctx, q, restrictions)
	if err != nil {
		return out, err
	}
	for _, group := range groups {
		group.People = counts[group.Name]
		group.Restrictions = append([]FeatureRule{}, restrictions[group.Name]...)
		out.Groups = append(out.Groups, group)
	}
	return out, nil
}
func (s *Service) roles(ctx *app.Ctx, _ struct{}) (RolesOut, error) {
	if err := require(ctx, "", true); err != nil {
		return RolesOut{}, err
	}
	return readRoles(ctx.Context, s.d.ReadPool())
}

type AddRestrictionIn struct {
	ID      api.ID `path:"id"`
	Feature string `json:"feature"`
	Note    string `json:"note"`
}

func (s *Service) addRestriction(ctx *app.Ctx, in AddRestrictionIn) (RolesOut, error) {
	if err := require(ctx, "", true); err != nil {
		return RolesOut{}, err
	}
	if featureID(in.Feature) == 0 {
		return RolesOut{}, api.InvalidFields(map[string][]string{"feature": {"请选择有效功能。"}})
	}
	in.Note = strings.TrimSpace(in.Note)
	if err := noteProblem(in.Note); err != nil {
		return RolesOut{}, err
	}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		role, err := roleByID(txCtx, tx, int64(in.ID))
		if err != nil {
			return err
		}
		var count int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM feature_role_restrictions WHERE role = ? AND feature = ?`, role.Name, in.Feature).Scan(&count); err != nil {
			return err
		}
		if count > 0 {
			return api.InvalidFields(map[string][]string{"feature": {"这项功能已经关闭。"}})
		}
		if _, err := tx.ExecContext(txCtx, `INSERT INTO feature_role_restrictions (role, feature, note, created_at) VALUES (?, ?, ?, ?)`, role.Name, in.Feature, in.Note, db.FormatUTC(ctx.Now().UTC())); err != nil {
			return err
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "role.restriction_add", "role", role.ID, map[string]any{"role": role.Name, "feature": in.Feature, "note": in.Note}, ctx.Now().UTC())
	})
	if err != nil {
		return RolesOut{}, err
	}
	return readRoles(ctx.Context, s.d.ReadPool())
}
func (s *Service) deleteRestriction(ctx *app.Ctx, in RuleIDIn) (RolesOut, error) {
	if err := require(ctx, "", true); err != nil {
		return RolesOut{}, err
	}
	feature := featureName(int64(in.Rule))
	if feature == "" {
		return RolesOut{}, api.NotFound("功能限制不存在")
	}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		role, err := roleByID(txCtx, tx, int64(in.ID))
		if err != nil {
			return err
		}
		result, err := tx.ExecContext(txCtx, `DELETE FROM feature_role_restrictions WHERE role = ? AND feature = ?`, role.Name, feature)
		if err != nil {
			return err
		}
		n, err := result.RowsAffected()
		if err != nil {
			return err
		}
		if n == 0 {
			return api.NotFound("功能限制不存在")
		}
		return audit.Record(txCtx, tx, ctx.Viewer.ID, "role.restriction_delete", "role", role.ID, map[string]any{"role": role.Name, "feature": feature}, ctx.Now().UTC())
	})
	if err != nil {
		return RolesOut{}, err
	}
	return readRoles(ctx.Context, s.d.ReadPool())
}

// RoleNames is useful to consumers rendering user role chips without changing permission keys.
func RoleNames() map[string]string {
	out := map[string]string{}
	for _, role := range standardRoles {
		out[role.Name] = role.Label
	}
	return out
}
func sortedRoles(viewer *app.Viewer) []string {
	if viewer.Superuser {
		return []string{"超级管理员"}
	}
	names := RoleNames()
	keys := make([]string, 0, len(viewer.Roles))
	for key := range viewer.Roles {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	out := []string{}
	for _, key := range keys {
		if label, ok := names[key]; ok {
			out = append(out, label)
		} else {
			out = append(out, key)
		}
	}
	return out
}
