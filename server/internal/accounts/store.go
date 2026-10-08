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

// GetByEmailNormTx 在事务内按小写规范化邮箱读用户。
func (s *Store) GetByEmailNormTx(ctx context.Context, tx *db.Tx, emailNorm string) (*User, error) {
	row := tx.QueryRowContext(ctx, `SELECT `+userColumns+` FROM users WHERE email_norm = ?`, emailNorm)
	u, err := scanUser(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	return u, err
}

// EmailCode 是 email_codes 表的一行。
type EmailCode struct {
	ID        int64
	Purpose   string
	EmailNorm string
	CodeHash  string
	Attempts  int
	CreatedAt time.Time
	ExpiresAt time.Time
}

// InsertEmailCode 插入验证码哈希（15 分钟有效、最多 3 次尝试，规则 2）。
func (s *Store) InsertEmailCode(ctx context.Context, tx *db.Tx, purpose, emailNorm, codeHash string, createdAt, expiresAt time.Time) error {
	_, err := tx.ExecContext(ctx, `INSERT INTO email_codes (purpose, email_norm, code_hash, attempts, created_at, expires_at)
		VALUES (?, ?, ?, 0, ?, ?)`, purpose, emailNorm, codeHash, db.FormatUTC(createdAt), db.FormatUTC(expiresAt))
	return err
}

// DeleteEmailCodes 删除指定用途与邮箱的所有旧验证码。
func (s *Store) DeleteEmailCodes(ctx context.Context, tx *db.Tx, purpose, emailNorm string) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM email_codes WHERE purpose = ? AND email_norm = ?`, purpose, emailNorm)
	return err
}

// GetLatestEmailCode 读最近一条验证码记录（测试与校验用）。
func (s *Store) GetLatestEmailCode(ctx context.Context, purpose, emailNorm string) (*EmailCode, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT id, purpose, email_norm, code_hash, attempts, created_at, expires_at
		FROM email_codes WHERE purpose = ? AND email_norm = ? ORDER BY id DESC LIMIT 1`, purpose, emailNorm)
	return scanEmailCode(row)
}

// GetLatestEmailCodeTx 在事务内读最近一条验证码记录（核验走这里，检查与
// 写尝试次数在同一个写事务里，12 号文档 5.6「检查—写入同事务」）。
func (s *Store) GetLatestEmailCodeTx(ctx context.Context, tx *db.Tx, purpose, emailNorm string) (*EmailCode, error) {
	row := tx.QueryRowContext(ctx, `SELECT id, purpose, email_norm, code_hash, attempts, created_at, expires_at
		FROM email_codes WHERE purpose = ? AND email_norm = ? ORDER BY id DESC LIMIT 1`, purpose, emailNorm)
	return scanEmailCode(row)
}

func scanEmailCode(row interface{ Scan(dest ...any) error }) (*EmailCode, error) {
	var c EmailCode
	var created, expires string
	err := row.Scan(&c.ID, &c.Purpose, &c.EmailNorm, &c.CodeHash, &c.Attempts, &created, &expires)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if t, err := db.ParseUTC(created); err == nil {
		c.CreatedAt = t
	}
	if t, err := db.ParseUTC(expires); err == nil {
		c.ExpiresAt = t
	}
	return &c, nil
}

// BumpEmailCodeAttempts 核验失败时把尝试次数加一。
func (s *Store) BumpEmailCodeAttempts(ctx context.Context, tx *db.Tx, id int64) error {
	_, err := tx.ExecContext(ctx, `UPDATE email_codes SET attempts = attempts + 1 WHERE id = ?`, id)
	return err
}

// DeleteEmailCode 按编号删单条验证码（3 次用尽作废）。
func (s *Store) DeleteEmailCode(ctx context.Context, tx *db.Tx, id int64) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM email_codes WHERE id = ?`, id)
	return err
}

// MarkEmailVerified 置邮箱已验证（核验通过的写事务里）。
func (s *Store) MarkEmailVerified(ctx context.Context, tx *db.Tx, userID int64, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE users SET email_verified_at = ?, updated_at = ? WHERE id = ?`,
		db.FormatUTC(at), db.FormatUTC(at), userID)
	return err
}

// UpdatePasswordHash 换密码哈希（PBKDF2 验过后升级 Argon2；改密码轮次复用）。
func (s *Store) UpdatePasswordHash(ctx context.Context, tx *db.Tx, userID int64, hash string, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ? WHERE id = ?`,
		hash, db.FormatUTC(at), db.FormatUTC(at), userID)
	return err
}
