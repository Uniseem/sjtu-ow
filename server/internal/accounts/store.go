package accounts

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Store 是账号域的数据读写层。
type Store struct {
	d *db.DB
}

// NewStore 创建账号存储。
func NewStore(d *db.DB) *Store {
	return &Store{d: d}
}

const userColumns = `id, email, email_norm, password_hash, nickname, is_sjtu,
	agreed_terms_at, agreed_cross_border_at, email_verified_at, password_changed_at,
	version, is_active, is_superuser, deactivation_note, motto, show_rank,
	created_at, updated_at`

func scanUser(row interface {
	Scan(dest ...any) error
}) (*User, error) {
	var u User
	var isSJTU, isActive, isSuperuser, showRank int
	var agreedTerms, agreedCB, created, updated string
	var emailVerified, passwordChanged sql.NullString
	err := row.Scan(
		&u.ID,
		&u.Email,
		&u.EmailNorm,
		&u.PasswordHash,
		&u.Nickname,
		&isSJTU,
		&agreedTerms,
		&agreedCB,
		&emailVerified,
		&passwordChanged,
		&u.Version,
		&isActive,
		&isSuperuser,
		&u.DeactivationNote,
		&u.Motto,
		&showRank,
		&created,
		&updated,
	)
	if err != nil {
		return nil, err
	}
	u.IsSJTU = isSJTU == 1
	u.IsActive = isActive == 1
	u.IsSuperuser = isSuperuser == 1
	u.ShowRank = showRank == 1
	if t, err := db.ParseUTC(agreedTerms); err == nil {
		u.AgreedTermsAt = t
	}
	if t, err := db.ParseUTC(agreedCB); err == nil {
		u.AgreedCrossBorderAt = t
	}
	if t, err := db.ParseUTC(created); err == nil {
		u.CreatedAt = t
	}
	if t, err := db.ParseUTC(updated); err == nil {
		u.UpdatedAt = t
	}
	if emailVerified.Valid && emailVerified.String != "" {
		if t, err := db.ParseUTC(emailVerified.String); err == nil {
			u.EmailVerifiedAt = &t
		}
	}
	if passwordChanged.Valid && passwordChanged.String != "" {
		if t, err := db.ParseUTC(passwordChanged.String); err == nil {
			u.PasswordChangedAt = &t
		}
	}
	return &u, nil
}

// GetByID 按 ID 读用户。没找到返回 (nil, nil)。
func (s *Store) GetByID(ctx context.Context, id int64) (*User, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT `+userColumns+` FROM users WHERE id = ?`, id)
	u, err := scanUser(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return u, err
}

// GetByEmailNorm 按小写规范化邮箱读用户。
func (s *Store) GetByEmailNorm(ctx context.Context, emailNorm string) (*User, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT `+userColumns+` FROM users WHERE email_norm = ?`, emailNorm)
	u, err := scanUser(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return u, err
}

// GetUserRoles 读用户的存储角色。
func (s *Store) GetUserRoles(ctx context.Context, userID int64) ([]string, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT role FROM user_roles WHERE user_id = ? ORDER BY role`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var roles []string
	for rows.Next() {
		var role string
		if err := rows.Scan(&role); err != nil {
			return nil, err
		}
		roles = append(roles, role)
	}
	return roles, rows.Err()
}

// GetFeatureUserRules 读用户的单人功能规则（true 表示允许，false 表示禁止）。
func (s *Store) GetFeatureUserRules(ctx context.Context, userID int64) (map[app.Feature]bool, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT feature, denied FROM feature_user_rules WHERE user_id = ?`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	rules := make(map[app.Feature]bool)
	for rows.Next() {
		var feat string
		var denied int
		if err := rows.Scan(&feat, &denied); err != nil {
			return nil, err
		}
		rules[app.Feature(feat)] = (denied == 0)
	}
	return rules, rows.Err()
}

// GetFeatureRoleRestrictions 读所有角色级功能限制。返回 map[role]map[feature]true。
func (s *Store) GetFeatureRoleRestrictions(ctx context.Context) (map[string]map[app.Feature]bool, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT role, feature FROM feature_role_restrictions`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	restrs := make(map[string]map[app.Feature]bool)
	for rows.Next() {
		var role, feat string
		if err := rows.Scan(&role, &feat); err != nil {
			return nil, err
		}
		if restrs[role] == nil {
			restrs[role] = make(map[app.Feature]bool)
		}
		restrs[role][app.Feature(feat)] = true
	}
	return restrs, rows.Err()
}

// InsertUser 插入新用户。
func (s *Store) InsertUser(ctx context.Context, tx *db.Tx, u *User) (int64, error) {
	var verifiedStr, pwdChangedStr any
	if u.EmailVerifiedAt != nil {
		verifiedStr = db.FormatUTC(*u.EmailVerifiedAt)
	}
	if u.PasswordChangedAt != nil {
		pwdChangedStr = db.FormatUTC(*u.PasswordChangedAt)
	}
	var isSJTU, isActive, isSuperuser, showRank int
	if u.IsSJTU {
		isSJTU = 1
	}
	if u.IsActive {
		isActive = 1
	}
	if u.IsSuperuser {
		isSuperuser = 1
	}
	if u.ShowRank {
		showRank = 1
	}
	version := u.Version
	if version == 0 {
		version = 1
	}

	res, err := tx.ExecContext(ctx, `INSERT INTO users (
		email, email_norm, password_hash, nickname, is_sjtu,
		agreed_terms_at, agreed_cross_border_at, email_verified_at, password_changed_at,
		version, is_active, is_superuser, deactivation_note, motto, show_rank,
		created_at, updated_at
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		u.Email, u.EmailNorm, u.PasswordHash, u.Nickname, isSJTU,
		db.FormatUTC(u.AgreedTermsAt), db.FormatUTC(u.AgreedCrossBorderAt), verifiedStr, pwdChangedStr,
		version, isActive, isSuperuser, u.DeactivationNote, u.Motto, showRank,
		db.FormatUTC(u.CreatedAt), db.FormatUTC(u.UpdatedAt),
	)
	if err != nil {
		return 0, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return 0, err
	}
	u.ID = id
	return id, nil
}

// AssignRole 为用户授予管理角色。
func (s *Store) AssignRole(ctx context.Context, tx *db.Tx, userID int64, role string, createdAt time.Time) error {
	_, err := tx.ExecContext(ctx, `INSERT INTO user_roles (user_id, role, created_at)
		VALUES (?, ?, ?) ON CONFLICT DO NOTHING`, userID, role, db.FormatUTC(createdAt))
	return err
}

// SetFeatureUserRule 设置单用户功能规则。
func (s *Store) SetFeatureUserRule(ctx context.Context, tx *db.Tx, userID int64, feature app.Feature, denied bool, createdAt time.Time) error {
	d := 0
	if denied {
		d = 1
	}
	_, err := tx.ExecContext(ctx, `INSERT INTO feature_user_rules (user_id, feature, denied, created_at)
		VALUES (?, ?, ?, ?) ON CONFLICT (user_id, feature) DO UPDATE SET denied = excluded.denied`,
		userID, string(feature), d, db.FormatUTC(createdAt))
	return err
}

// SetFeatureRoleRestriction 设置角色级功能限制。
func (s *Store) SetFeatureRoleRestriction(ctx context.Context, tx *db.Tx, role string, feature app.Feature, createdAt time.Time) error {
	_, err := tx.ExecContext(ctx, `INSERT INTO feature_role_restrictions (role, feature, created_at)
		VALUES (?, ?, ?) ON CONFLICT DO NOTHING`, role, string(feature), db.FormatUTC(createdAt))
	return err
}
