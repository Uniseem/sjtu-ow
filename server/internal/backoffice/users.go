package backoffice

import (
	"context"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type UserSearchIn struct {
	Sort   string `query:"sort"`
	Query  string `query:"q"`
	Role   string `query:"role"`
	Active string `query:"active"`
	SJTU   string `query:"sjtu"`
	Page   int    `query:"page"`
}
type UserRow struct {
	ID            int64    `json:"id"`
	Email         string   `json:"email"`
	Nickname      string   `json:"nickname"`
	IsSJTU        bool     `json:"is_sjtu"`
	IsActive      bool     `json:"is_active"`
	IsSuperuser   bool     `json:"is_superuser"`
	EmailVerified bool     `json:"email_verified"`
	CreatedAt     string   `json:"created_at"`
	Roles         []string `json:"roles"`
}
type UserSearchOut struct {
	Users    []UserRow   `json:"users"`
	Total    int         `json:"total"`
	Page     int         `json:"page"`
	PageSize int         `json:"page_size"`
	Roles    []RoleGroup `json:"roles"`
}

// This expression mirrors CanUse(article_submit), including the explicit allow
// taking priority over role restrictions, and the contributor recursion rule.
const contributorWhere = `u.is_active = 1 AND u.email_verified_at IS NOT NULL AND (
 u.is_superuser = 1 OR
 EXISTS (SELECT 1 FROM feature_user_rules ur WHERE ur.user_id = u.id AND ur.feature = 'article_submit' AND ur.denied = 0) OR (
  NOT EXISTS (SELECT 1 FROM feature_user_rules ur WHERE ur.user_id = u.id AND ur.feature = 'article_submit') AND
  NOT EXISTS (SELECT 1 FROM feature_role_restrictions rr WHERE rr.feature = 'article_submit' AND (
   rr.role = 'contributor' OR
   rr.role = CASE WHEN u.is_sjtu = 1 THEN 'sjtu_user' ELSE 'external_user' END OR
   EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.role = rr.role)
  ))
 )
)`

func userWhere(in UserSearchIn) (string, []any, error) {
	clauses := []string{"1 = 1"}
	args := []any{}
	if query := strings.TrimSpace(in.Query); query != "" {
		escaped := strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`).Replace(query)
		clauses = append(clauses, `(u.nickname LIKE ? ESCAPE '\' OR u.email LIKE ? ESCAPE '\')`)
		args = append(args, "%"+escaped+"%", "%"+escaped+"%")
	}
	for _, field := range []struct{ key, column, value string }{{"active", "u.is_active", in.Active}, {"sjtu", "u.is_sjtu", in.SJTU}} {
		if field.value == "" {
			continue
		}
		if field.value != "yes" && field.value != "no" {
			return "", nil, api.InvalidFields(map[string][]string{field.key: {"请选择有效条件。"}})
		}
		enabled := 0
		if field.value == "yes" {
			enabled = 1
		}
		clauses = append(clauses, field.column+" = ?")
		args = append(args, enabled)
	}
	if in.Role != "" {
		switch in.Role {
		case accounts.RoleSJTU:
			clauses = append(clauses, "u.is_sjtu = 1")
		case accounts.RoleExternal:
			clauses = append(clauses, "u.is_sjtu = 0")
		case accounts.RoleContributor:
			clauses = append(clauses, "("+contributorWhere+")")
		default:
			clauses = append(clauses, "EXISTS (SELECT 1 FROM user_roles ur WHERE ur.user_id = u.id AND ur.role = ?)")
			args = append(args, in.Role)
		}
	}
	return strings.Join(clauses, " AND "), args, nil
}
func readUsers(ctx context.Context, q db.DBTX, in UserSearchIn) (UserSearchOut, error) {
	out := UserSearchOut{Users: []UserRow{}, Roles: []RoleGroup{}, Page: in.Page, PageSize: 50}
	if out.Page < 1 {
		out.Page = 1
	}
	if out.Page > 1000000 {
		return out, api.Invalid("页码超出范围。")
	}
	roles, err := knownRoles(ctx, q)
	if err != nil {
		return out, err
	}
	out.Roles = roles
	if in.Role != "" {
		known := false
		for _, role := range roles {
			if role.Name == in.Role {
				known = true
				break
			}
		}
		if !known {
			return out, api.InvalidFields(map[string][]string{"role": {"请选择有效角色。"}})
		}
	}
	where, args, err := userWhere(in)
	if err != nil {
		return out, err
	}
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM users u WHERE `+where, args...).Scan(&out.Total); err != nil {
		return out, err
	}
	order := "u.created_at DESC, u.id DESC"
	if in.Sort == "nickname" {
		order = "u.nickname, u.id"
	} else if in.Sort != "" {
		return out, api.InvalidFields(map[string][]string{"sort": {"请选择有效排序。"}})
	}
	rowArgs := append(append([]any{}, args...), out.PageSize, (out.Page-1)*out.PageSize)
	rows, err := q.QueryContext(ctx, `SELECT u.id, u.email, u.nickname, u.is_sjtu, u.is_active, u.is_superuser, u.email_verified_at IS NOT NULL, u.created_at FROM users u WHERE `+where+` ORDER BY `+order+` LIMIT ? OFFSET ?`, rowArgs...)
	if err != nil {
		return out, err
	}
	ids := []any{}
	for rows.Next() {
		var row UserRow
		row.Roles = []string{}
		if err := rows.Scan(&row.ID, &row.Email, &row.Nickname, &row.IsSJTU, &row.IsActive, &row.IsSuperuser, &row.EmailVerified, &row.CreatedAt); err != nil {
			rows.Close()
			return out, err
		}
		out.Users = append(out.Users, row)
		ids = append(ids, row.ID)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	if len(ids) == 0 {
		return out, nil
	}
	placeholders := strings.TrimSuffix(strings.Repeat("?,", len(ids)), ",")
	rows, err = q.QueryContext(ctx, `SELECT user_id, role FROM user_roles WHERE user_id IN (`+placeholders+`) ORDER BY role`, ids...)
	if err != nil {
		return out, err
	}
	byUser := map[int64][]string{}
	for rows.Next() {
		var user int64
		var role string
		if err := rows.Scan(&user, &role); err != nil {
			rows.Close()
			return out, err
		}
		byUser[user] = append(byUser[user], role)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	// Contributor membership is derived server-side, never invented by a role checkbox.
	rows, err = q.QueryContext(ctx, `SELECT u.id FROM users u WHERE u.id IN (`+placeholders+`) AND (`+contributorWhere+`)`, ids...)
	if err != nil {
		return out, err
	}
	submitters := map[int64]bool{}
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return out, err
		}
		submitters[id] = true
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return out, err
	}
	for i := range out.Users {
		row := &out.Users[i]
		row.Roles = append(row.Roles, byUser[row.ID]...)
		row.Roles = append(row.Roles, accounts.DerivedRoles(row.IsSJTU, row.IsActive, row.EmailVerified, submitters[row.ID])...)
	}
	return out, nil
}
func (s *Service) searchUsers(ctx *app.Ctx, in UserSearchIn) (UserSearchOut, error) {
	if err := require(ctx, "", true); err != nil {
		return UserSearchOut{}, err
	}
	return readUsers(ctx.Context, s.d.ReadPool(), in)
}
