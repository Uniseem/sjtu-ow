package accounts

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
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
	version, is_active, is_superuser, deactivation_note, motto, main_role, flex_roles, show_rank,
	avatar_image_id, created_at, updated_at`

func scanUser(row interface {
	Scan(dest ...any) error
}) (*User, error) {
	var u User
	var isSJTU, isActive, isSuperuser, showRank int
	var agreedTerms, agreedCB, created, updated string
	var emailVerified, passwordChanged sql.NullString
	var avatarID sql.NullInt64
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
		&u.MainRole,
		&u.FlexRoles,
		&showRank,
		&avatarID,
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
	if avatarID.Valid {
		v := avatarID.Int64
		u.AvatarImageID = &v
	}
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
		version, is_active, is_superuser, deactivation_note, motto, main_role, flex_roles, show_rank,
		created_at, updated_at
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		u.Email, u.EmailNorm, u.PasswordHash, u.Nickname, isSJTU,
		db.FormatUTC(u.AgreedTermsAt), db.FormatUTC(u.AgreedCrossBorderAt), verifiedStr, pwdChangedStr,
		version, isActive, isSuperuser, u.DeactivationNote, u.Motto, u.MainRole, u.FlexRoles, showRank,
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

// GetByIDTx 在事务内按 ID 读用户。
func (s *Store) GetByIDTx(ctx context.Context, tx *db.Tx, id int64) (*User, error) {
	row := tx.QueryRowContext(ctx, `SELECT `+userColumns+` FROM users WHERE id = ?`, id)
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

// GetLatestEmailCodeTx 在事务内读最近一条验证码记录。
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

// UpdatePasswordHash 换密码哈希。
func (s *Store) UpdatePasswordHash(ctx context.Context, tx *db.Tx, userID int64, hash string, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ? WHERE id = ?`,
		hash, db.FormatUTC(at), db.FormatUTC(at), userID)
	return err
}

// -------------------------------------------------------------
// 个人资料 (Profile)、游戏 ID (GameAccount) 与联系方式 (Contact)
// -------------------------------------------------------------

// UpdateUserProfile 更新用户个人资料（昵称、宣言、位置、段位公开、交大标志等）。
func (s *Store) UpdateUserProfile(ctx context.Context, tx *db.Tx, userID int64, nickname, motto, mainRole, flexRoles string, showRank, isSJTU bool, at time.Time) error {
	showRankInt := 0
	if showRank {
		showRankInt = 1
	}
	isSJTUInt := 0
	if isSJTU {
		isSJTUInt = 1
	}
	_, err := tx.ExecContext(ctx, `UPDATE users SET
		nickname = ?,
		motto = ?,
		main_role = ?,
		flex_roles = ?,
		show_rank = ?,
		is_sjtu = ?,
		version = version + 1,
		updated_at = ?
		WHERE id = ?`,
		nickname, motto, mainRole, flexRoles, showRankInt, isSJTUInt, db.FormatUTC(at), userID)
	return err
}

func scanGameAccount(row interface{ Scan(dest ...any) error }) (*GameAccount, error) {
	var ga GameAccount
	var tank, damage, support sql.NullInt64
	var stamped, created, updated string
	err := row.Scan(&ga.ID, &ga.UserID, &ga.Battletag, &ga.BattletagNorm, &tank, &damage, &support, &stamped, &created, &updated)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if tank.Valid {
		v := int(tank.Int64)
		ga.RankTank = &v
	}
	if damage.Valid {
		v := int(damage.Int64)
		ga.RankDamage = &v
	}
	if support.Valid {
		v := int(support.Int64)
		ga.RankSupport = &v
	}
	if t, err := db.ParseUTC(stamped); err == nil {
		ga.RanksUpdatedAt = t
	}
	if t, err := db.ParseUTC(created); err == nil {
		ga.CreatedAt = t
	}
	if t, err := db.ParseUTC(updated); err == nil {
		ga.UpdatedAt = t
	}
	return &ga, nil
}

const gameAccountCols = `id, user_id, battletag, battletag_norm, rank_tank, rank_damage, rank_support, ranks_updated_at, created_at, updated_at`

// GetGameAccountsByUserID 读用户的所有游戏 ID。
func (s *Store) GetGameAccountsByUserID(ctx context.Context, userID int64) ([]GameAccount, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT `+gameAccountCols+` FROM game_accounts WHERE user_id = ? ORDER BY id ASC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var list []GameAccount
	for rows.Next() {
		ga, err := scanGameAccount(rows)
		if err != nil {
			return nil, err
		}
		if ga != nil {
			list = append(list, *ga)
		}
	}
	return list, rows.Err()
}

// GetGameAccountByID 按 ID 读单个游戏 ID。
func (s *Store) GetGameAccountByID(ctx context.Context, id int64) (*GameAccount, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT `+gameAccountCols+` FROM game_accounts WHERE id = ?`, id)
	return scanGameAccount(row)
}

// GetGameAccountByBattletagNorm 按规范化 BattleTag 查找游戏 ID（唯一性检查，规则 17）。
func (s *Store) GetGameAccountByBattletagNorm(ctx context.Context, norm string) (*GameAccount, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT `+gameAccountCols+` FROM game_accounts WHERE battletag_norm = ?`, norm)
	return scanGameAccount(row)
}

// CountGameAccountsByUserID 计算用户已绑定的游戏 ID 数量（上限 5 个，规则 16）。
func (s *Store) CountGameAccountsByUserID(ctx context.Context, userID int64) (int, error) {
	var cnt int
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM game_accounts WHERE user_id = ?`, userID).Scan(&cnt)
	return cnt, err
}

// InsertGameAccount 插入新游戏 ID。
func (s *Store) InsertGameAccount(ctx context.Context, tx *db.Tx, ga *GameAccount) (int64, error) {
	res, err := tx.ExecContext(ctx, `INSERT INTO game_accounts (
		user_id, battletag, battletag_norm, rank_tank, rank_damage, rank_support, ranks_updated_at, created_at, updated_at
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		ga.UserID, ga.Battletag, ga.BattletagNorm, ga.RankTank, ga.RankDamage, ga.RankSupport,
		db.FormatUTC(ga.RanksUpdatedAt), db.FormatUTC(ga.CreatedAt), db.FormatUTC(ga.UpdatedAt))
	if err != nil {
		return 0, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return 0, err
	}
	ga.ID = id
	return id, nil
}

// UpdateGameAccount 更新游戏 ID 的段位信息。
func (s *Store) UpdateGameAccount(ctx context.Context, tx *db.Tx, ga *GameAccount) error {
	_, err := tx.ExecContext(ctx, `UPDATE game_accounts SET
		rank_tank = ?,
		rank_damage = ?,
		rank_support = ?,
		ranks_updated_at = ?,
		updated_at = ?
		WHERE id = ? AND user_id = ?`,
		ga.RankTank, ga.RankDamage, ga.RankSupport,
		db.FormatUTC(ga.RanksUpdatedAt), db.FormatUTC(ga.UpdatedAt), ga.ID, ga.UserID)
	return err
}

// DeleteGameAccount 删除游戏 ID。
func (s *Store) DeleteGameAccount(ctx context.Context, tx *db.Tx, id int64, userID int64) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM game_accounts WHERE id = ? AND user_id = ?`, id, userID)
	return err
}

const contactCols = `id, user_id, type, value, created_at, updated_at`

func scanContact(row interface{ Scan(dest ...any) error }) (*Contact, error) {
	var c Contact
	var created, updated string
	err := row.Scan(&c.ID, &c.UserID, &c.Type, &c.Value, &created, &updated)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if t, err := db.ParseUTC(created); err == nil {
		c.CreatedAt = t
	}
	if t, err := db.ParseUTC(updated); err == nil {
		c.UpdatedAt = t
	}
	return &c, nil
}

// GetContactsByUserID 读用户的所有联系方式。
func (s *Store) GetContactsByUserID(ctx context.Context, userID int64) ([]Contact, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT `+contactCols+` FROM contacts WHERE user_id = ? ORDER BY id ASC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var list []Contact
	for rows.Next() {
		c, err := scanContact(rows)
		if err != nil {
			return nil, err
		}
		if c != nil {
			list = append(list, *c)
		}
	}
	return list, rows.Err()
}

// GetContactByID 按 ID 读单个联系方式。
func (s *Store) GetContactByID(ctx context.Context, id int64) (*Contact, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT `+contactCols+` FROM contacts WHERE id = ?`, id)
	return scanContact(row)
}

// GetContactByUserAndType 按用户和类型查找联系方式（每种只能填一条，规则 19）。
func (s *Store) GetContactByUserAndType(ctx context.Context, userID int64, cType string) (*Contact, error) {
	row := s.d.ReadPool().QueryRowContext(ctx, `SELECT `+contactCols+` FROM contacts WHERE user_id = ? AND type = ?`, userID, cType)
	return scanContact(row)
}

// InsertContact 插入联系方式。
func (s *Store) InsertContact(ctx context.Context, tx *db.Tx, c *Contact) (int64, error) {
	res, err := tx.ExecContext(ctx, `INSERT INTO contacts (
		user_id, type, value, created_at, updated_at
	) VALUES (?, ?, ?, ?, ?)`,
		c.UserID, c.Type, c.Value, db.FormatUTC(c.CreatedAt), db.FormatUTC(c.UpdatedAt))
	if err != nil {
		return 0, err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return 0, err
	}
	c.ID = id
	return id, nil
}

// DeleteContact 删除联系方式。
func (s *Store) DeleteContact(ctx context.Context, tx *db.Tx, id int64, userID int64) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM contacts WHERE id = ? AND user_id = ?`, id, userID)
	return err
}

// -------------------------------------------------------------
// 改邮箱 (Email Change)
// -------------------------------------------------------------

// EmailChange 是 email_changes 表的一行。
type EmailChange struct {
	UserID       int64
	NewEmail     string
	NewEmailNorm string
	CodeHash     string
	Attempts     int
	CreatedAt    time.Time
	ExpiresAt    time.Time
}

func scanEmailChange(row interface{ Scan(dest ...any) error }) (*EmailChange, error) {
	var ec EmailChange
	var created, expires string
	err := row.Scan(&ec.UserID, &ec.NewEmail, &ec.NewEmailNorm, &ec.CodeHash, &ec.Attempts, &created, &expires)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if t, err := db.ParseUTC(created); err == nil {
		ec.CreatedAt = t
	}
	if t, err := db.ParseUTC(expires); err == nil {
		ec.ExpiresAt = t
	}
	return &ec, nil
}

// InsertEmailChange 插入或替换换绑邮箱的中间记录。
func (s *Store) InsertEmailChange(ctx context.Context, tx *db.Tx, ec *EmailChange) error {
	_, err := tx.ExecContext(ctx, `INSERT INTO email_changes (
		user_id, new_email, new_email_norm, code_hash, attempts, created_at, expires_at
	) VALUES (?, ?, ?, ?, 0, ?, ?)
	ON CONFLICT (user_id) DO UPDATE SET
		new_email = excluded.new_email,
		new_email_norm = excluded.new_email_norm,
		code_hash = excluded.code_hash,
		attempts = 0,
		created_at = excluded.created_at,
		expires_at = excluded.expires_at`,
		ec.UserID, ec.NewEmail, ec.NewEmailNorm, ec.CodeHash,
		db.FormatUTC(ec.CreatedAt), db.FormatUTC(ec.ExpiresAt))
	return err
}

// GetEmailChangeTx 在事务内读当前用户的换绑记录。
func (s *Store) GetEmailChangeTx(ctx context.Context, tx *db.Tx, userID int64) (*EmailChange, error) {
	row := tx.QueryRowContext(ctx, `SELECT user_id, new_email, new_email_norm, code_hash, attempts, created_at, expires_at
		FROM email_changes WHERE user_id = ?`, userID)
	return scanEmailChange(row)
}

// BumpEmailChangeAttempts 增加换绑邮箱尝试次数。
func (s *Store) BumpEmailChangeAttempts(ctx context.Context, tx *db.Tx, userID int64) error {
	_, err := tx.ExecContext(ctx, `UPDATE email_changes SET attempts = attempts + 1 WHERE user_id = ?`, userID)
	return err
}

// DeleteEmailChange 删除换绑邮箱记录。
func (s *Store) DeleteEmailChange(ctx context.Context, tx *db.Tx, userID int64) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM email_changes WHERE user_id = ?`, userID)
	return err
}

// UpdateUserEmail 更新用户的登录邮箱（换绑成功时调用）。
func (s *Store) UpdateUserEmail(ctx context.Context, tx *db.Tx, userID int64, email, emailNorm string, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE users SET
		email = ?,
		email_norm = ?,
		email_verified_at = ?,
		updated_at = ?
		WHERE id = ?`,
		email, emailNorm, db.FormatUTC(at), db.FormatUTC(at), userID)
	return err
}

// -------------------------------------------------------------
// 账号停用、启用与注销 (Deactivation, Activation & Anonymization)
// -------------------------------------------------------------

// DeactivateUserTx 停用账号（设置 is_active=0，记录原因，规则 33）。
func (s *Store) DeactivateUserTx(ctx context.Context, tx *db.Tx, userID int64, note string, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE users SET
		is_active = 0,
		deactivation_note = ?,
		updated_at = ?
		WHERE id = ?`,
		note, db.FormatUTC(at), userID)
	return err
}

// ReactivateUserTx 重新启用账号（清空停用原因，置 is_active=1，规则 36）。
func (s *Store) ReactivateUserTx(ctx context.Context, tx *db.Tx, userID int64, at time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE users SET
		is_active = 1,
		deactivation_note = '',
		updated_at = ?
		WHERE id = ?`,
		db.FormatUTC(at), userID)
	return err
}

// AnonymizeUserTx 原地匿名化注销用户（规则 30）。
// email -> deleted-{id}@deleted.invalid
// nickname -> 已注销用户
// password_hash -> ! (unusable password)
// 清除个人设置与管理权限，is_active=0, is_superuser=0。
func (s *Store) AnonymizeUserTx(ctx context.Context, tx *db.Tx, userID int64, at time.Time) error {
	deletedEmail := fmt.Sprintf("deleted-%d@deleted.invalid", userID)
	_, err := tx.ExecContext(ctx, `UPDATE users SET
		email = ?,
		email_norm = ?,
		password_hash = '!',
		nickname = '已注销用户',
		is_sjtu = 0,
		is_active = 0,
		is_superuser = 0,
		deactivation_note = '用户自行注销',
		motto = '',
		main_role = '',
		flex_roles = '',
		show_rank = 0,
		version = version + 1,
		updated_at = ?
		WHERE id = ?`,
		deletedEmail, deletedEmail, db.FormatUTC(at), userID)
	return err
}

// DeleteUserDataTx 清除注销用户的自有数据（规则 31）。
func (s *Store) DeleteUserDataTx(ctx context.Context, tx *db.Tx, userID int64) error {
	queries := []string{
		`DELETE FROM game_accounts WHERE user_id = ?`,
		`DELETE FROM contacts WHERE user_id = ?`,
		`DELETE FROM user_roles WHERE user_id = ?`,
		`DELETE FROM feature_user_rules WHERE user_id = ?`,
		`DELETE FROM email_changes WHERE user_id = ?`,
	}
	for _, q := range queries {
		if _, err := tx.ExecContext(ctx, q, userID); err != nil {
			return err
		}
	}
	return nil
}

// LeaveTeamsAndGroupsTx 注销账号时退出所有战队、删退役记录、撤回待审申请、移出所有成员分组
// （规则 31：现行站 leave_all_teams 加 MemberGroupMembership）。在任队长的人进不到这里，
// 服务层先拦下了（规则 29）。
func (s *Store) LeaveTeamsAndGroupsTx(ctx context.Context, tx *db.Tx, userID int64, at time.Time) error {
	stmts := []struct {
		q    string
		args []any
	}{
		{`DELETE FROM team_memberships WHERE user_id = ?`, []any{userID}},
		{`DELETE FROM team_alumni WHERE user_id = ?`, []any{userID}},
		{`UPDATE team_applications SET status = 'cancelled', decided_at = ?
			WHERE applicant_id = ? AND status = 'pending'`, []any{db.FormatUTC(at), userID}},
		{`DELETE FROM member_group_memberships WHERE user_id = ?`, []any{userID}},
	}
	for _, st := range stmts {
		if _, err := tx.ExecContext(ctx, st.q, st.args...); err != nil {
			return err
		}
	}
	return nil
}

// LeaveTournamentsTx 注销账号时退出所有进行中的临时队伍并删个人报名（规则 31）。整队报名的
// 名单快照保留（昵称、游戏 ID 都是当时定格的）。退出后没人的临时队伍自动解散。
func (s *Store) LeaveTournamentsTx(ctx context.Context, tx *db.Tx, userID int64, at time.Time) error {
	// 内战报名：先撤（报名占着游戏 ID）；已被分队或进了替补的，给那场内战打「名单有变动」标记（规则 31、158）。
	if _, err := tx.ExecContext(ctx, `UPDATE scrims SET roster_changed_at = ?, board_version = board_version + 1
		WHERE id IN (SELECT scrim_id FROM scrim_signups WHERE user_id = ? AND (is_selected = 1 OR team <> ''))`,
		db.FormatUTC(at), userID); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `DELETE FROM scrim_signups WHERE user_id = ?`, userID); err != nil {
		return err
	}
	rows, err := tx.QueryContext(ctx, `SELECT DISTINCT m.registration_id FROM registration_members m
		JOIN registrations r ON r.id = m.registration_id
		WHERE m.user_id = ? AND m.is_active = 1 AND r.team_id IS NULL AND r.status IN ('pending', 'approved')`, userID)
	if err != nil {
		return err
	}
	var regs []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return err
		}
		regs = append(regs, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	stamp := db.FormatUTC(at)
	for _, id := range regs {
		if _, err := tx.ExecContext(ctx, `DELETE FROM registration_members WHERE registration_id = ? AND user_id = ?`, id, userID); err != nil {
			return err
		}
		var left int
		if err := tx.QueryRowContext(ctx, `SELECT COUNT(*) FROM registration_members WHERE registration_id = ?`, id).Scan(&left); err != nil {
			return err
		}
		if left > 0 {
			continue
		}
		var from string
		var version int64
		if err := tx.QueryRowContext(ctx, `SELECT status, roster_version FROM registrations WHERE id = ?`, id).Scan(&from, &version); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `UPDATE registrations SET status = 'withdrawn', status_note = '最后一名成员退出，队伍自动解散', updated_at = ? WHERE id = ?`, stamp, id); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO registration_status_logs
			(registration_id, action, from_status, to_status, actor_type, roster_version, note, created_at)
			VALUES (?, 'dissolve', ?, 'withdrawn', 'system', ?, '最后一名成员退出，队伍自动解散', ?)`, id, from, version, stamp); err != nil {
			return err
		}
	}
	if _, err := tx.ExecContext(ctx, `UPDATE individual_signups SET registration_id = NULL WHERE user_id = ?`, userID); err != nil {
		return err
	}
	_, err = tx.ExecContext(ctx, `DELETE FROM individual_signups WHERE user_id = ?`, userID)
	return err
}

// SuspendTeamActivityTx 停用账号时撤回它的待审入队申请，并让它任队长的战队停止招募
// （规则 35：队长账号停了，战队收不了申请，就别再显示成招募中；下一任队长再打开）。
func (s *Store) SuspendTeamActivityTx(ctx context.Context, tx *db.Tx, userID int64, at time.Time) error {
	if _, err := tx.ExecContext(ctx, `UPDATE team_applications SET status = 'cancelled', decided_at = ?
		WHERE applicant_id = ? AND status = 'pending'`, db.FormatUTC(at), userID); err != nil {
		return err
	}
	_, err := tx.ExecContext(ctx, `UPDATE teams SET is_recruiting = 0, version = version + 1, updated_at = ?
		WHERE disbanded_at IS NULL AND is_recruiting = 1 AND id IN
			(SELECT team_id FROM team_memberships WHERE user_id = ? AND role = 'captain')`,
		db.FormatUTC(at), userID)
	return err
}

// -------------------------------------------------------------
// 后台用户管理 (Admin User Management)
// -------------------------------------------------------------

// ListUsers 分页查询用户列表。根据 searchEmail 决定是否支持按邮箱搜索（规则 39）。
func (s *Store) ListUsers(ctx context.Context, limit, offset int, search string, searchEmail bool) ([]*User, error) {
	search = strings.TrimSpace(search)
	var query string
	var args []any

	if search != "" {
		if searchEmail {
			query = `SELECT ` + userColumns + ` FROM users WHERE nickname LIKE ? OR email LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?`
			term := "%" + search + "%"
			args = []any{term, term, limit, offset}
		} else {
			query = `SELECT ` + userColumns + ` FROM users WHERE nickname LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?`
			term := "%" + search + "%"
			args = []any{term, limit, offset}
		}
	} else {
		query = `SELECT ` + userColumns + ` FROM users ORDER BY id DESC LIMIT ? OFFSET ?`
		args = []any{limit, offset}
	}

	rows, err := s.d.ReadPool().QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var list []*User
	for rows.Next() {
		u, err := scanUser(rows)
		if err != nil {
			return nil, err
		}
		if u != nil {
			list = append(list, u)
		}
	}
	return list, rows.Err()
}

// CountUsers 统计满足条件的用户总数。
func (s *Store) CountUsers(ctx context.Context, search string, searchEmail bool) (int, error) {
	search = strings.TrimSpace(search)
	var query string
	var args []any

	if search != "" {
		if searchEmail {
			query = `SELECT COUNT(*) FROM users WHERE nickname LIKE ? OR email LIKE ?`
			term := "%" + search + "%"
			args = []any{term, term}
		} else {
			query = `SELECT COUNT(*) FROM users WHERE nickname LIKE ?`
			term := "%" + search + "%"
			args = []any{term}
		}
	} else {
		query = `SELECT COUNT(*) FROM users`
	}

	var cnt int
	err := s.d.ReadPool().QueryRowContext(ctx, query, args...).Scan(&cnt)
	return cnt, err
}

// SetUserRolesTx 全量替换用户的管理角色。
func (s *Store) SetUserRolesTx(ctx context.Context, tx *db.Tx, userID int64, roles []string, at time.Time) error {
	if _, err := tx.ExecContext(ctx, `DELETE FROM user_roles WHERE user_id = ?`, userID); err != nil {
		return err
	}
	atStr := db.FormatUTC(at)
	for _, r := range roles {
		if _, err := tx.ExecContext(ctx, `INSERT INTO user_roles (user_id, role, created_at) VALUES (?, ?, ?)`,
			userID, r, atStr); err != nil {
			return err
		}
	}
	return nil
}

// SetUserRulesTx 全量替换用户的单人功能规则。
func (s *Store) SetUserRulesTx(ctx context.Context, tx *db.Tx, userID int64, rules map[app.Feature]bool, at time.Time) error {
	if _, err := tx.ExecContext(ctx, `DELETE FROM feature_user_rules WHERE user_id = ?`, userID); err != nil {
		return err
	}
	atStr := db.FormatUTC(at)
	for feat, allowed := range rules {
		denied := 0
		if !allowed {
			denied = 1
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO feature_user_rules (user_id, feature, denied, created_at) VALUES (?, ?, ?, ?)`,
			userID, string(feat), denied, atStr); err != nil {
			return err
		}
	}
	return nil
}

// ReplaceRoleRestrictionsTx 全量替换角色级功能限制。
func (s *Store) ReplaceRoleRestrictionsTx(ctx context.Context, tx *db.Tx, restrictions map[string]map[app.Feature]bool, at time.Time) error {
	if _, err := tx.ExecContext(ctx, `DELETE FROM feature_role_restrictions`); err != nil {
		return err
	}
	atStr := db.FormatUTC(at)
	for role, feats := range restrictions {
		for feat, restricted := range feats {
			if restricted {
				if _, err := tx.ExecContext(ctx, `INSERT INTO feature_role_restrictions (role, feature, created_at) VALUES (?, ?, ?)`,
					role, string(feat), atStr); err != nil {
					return err
				}
			}
		}
	}
	return nil
}

// CreateAvatarSubmission 写入一条头像审核记录。
func (s *Store) CreateAvatarSubmission(ctx context.Context, tx *db.Tx, sub *AvatarSubmission) error {
	var reviewedStr sql.NullString
	if sub.ReviewedAt != nil {
		reviewedStr = sql.NullString{String: db.FormatUTC(*sub.ReviewedAt), Valid: true}
	}
	var imgVal any
	if sub.ImageID != nil && *sub.ImageID > 0 {
		imgVal = *sub.ImageID
	}
	res, err := tx.ExecContext(ctx, `
		INSERT INTO avatar_submissions (user_id, image_id, status, handling_note, reviewed_at, created_at)
		VALUES (?, ?, ?, ?, ?, ?)
	`, sub.UserID, imgVal, sub.Status, sub.HandlingNote, reviewedStr, db.FormatUTC(sub.CreatedAt))
	if err != nil {
		return err
	}
	id, err := res.LastInsertId()
	if err != nil {
		return err
	}
	sub.ID = id
	return nil
}

// SetUserAvatar 更新用户当前头像。
func (s *Store) SetUserAvatar(ctx context.Context, tx *db.Tx, userID int64, imageID *int64, updatedAt time.Time) error {
	var imgVal any
	if imageID != nil && *imageID > 0 {
		imgVal = *imageID
	}
	_, err := tx.ExecContext(ctx, `
		UPDATE users SET avatar_image_id = ?, version = version + 1, updated_at = ? WHERE id = ?
	`, imgVal, db.FormatUTC(updatedAt), userID)
	return err
}

// UserUploadedFaceIDs 查询某个用户自己上传过的全部头像图片 ID。
func (s *Store) UserUploadedFaceIDs(ctx context.Context, userID int64) (map[int64]struct{}, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `
		SELECT DISTINCT image_id FROM avatar_submissions WHERE user_id = ? AND image_id IS NOT NULL
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make(map[int64]struct{})
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err == nil && id > 0 {
			out[id] = struct{}{}
		}
	}
	return out, rows.Err()
}

// ListAvatarSubmissions 查询待复核或全部头像提交记录。
func (s *Store) ListAvatarSubmissions(ctx context.Context, status string, page, pageSize int) ([]AvatarSubmission, int, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 50
	}
	if pageSize > 100 {
		pageSize = 100
	}

	whereClause := ""
	var args []any
	if status != "" {
		whereClause = "WHERE s.status = ?"
		args = append(args, status)
	}

	var total int
	countQ := fmt.Sprintf("SELECT COUNT(*) FROM avatar_submissions s %s", whereClause)
	if err := s.d.ReadPool().QueryRowContext(ctx, countQ, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	query := fmt.Sprintf(`
		SELECT s.id, s.user_id, COALESCE(u.nickname, ''), s.image_id, s.status, s.handling_note, s.reviewed_at, s.created_at
		FROM avatar_submissions s
		LEFT JOIN users u ON u.id = s.user_id
		%s
		ORDER BY s.id DESC
		LIMIT ? OFFSET ?
	`, whereClause)

	limitArgs := append(args, pageSize, (page-1)*pageSize)
	rows, err := s.d.ReadPool().QueryContext(ctx, query, limitArgs...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	items := make([]AvatarSubmission, 0, pageSize)
	for rows.Next() {
		var sub AvatarSubmission
		var imgID sql.NullInt64
		var revStr sql.NullString
		var atStr string
		if err := rows.Scan(&sub.ID, &sub.UserID, &sub.UserNickname, &imgID, &sub.Status, &sub.HandlingNote, &revStr, &atStr); err != nil {
			return nil, 0, err
		}
		if imgID.Valid {
			v := imgID.Int64
			sub.ImageID = &v
		}
		if revStr.Valid && revStr.String != "" {
			t, _ := db.ParseUTC(revStr.String)
			sub.ReviewedAt = &t
		}
		t, _ := db.ParseUTC(atStr)
		sub.CreatedAt = t
		items = append(items, sub)
	}
	return items, total, rows.Err()
}

// TakeDownAvatar 下架指定头像。
func (s *Store) TakeDownAvatar(ctx context.Context, submissionID int64, note string, reviewedAt time.Time) (*AvatarSubmission, error) {
	var sub AvatarSubmission
	var imgID sql.NullInt64
	var atStr string
	err := s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		err := tx.QueryRowContext(txCtx, `
			SELECT id, user_id, image_id, status, handling_note, created_at
			FROM avatar_submissions WHERE id = ?
		`, submissionID).Scan(&sub.ID, &sub.UserID, &imgID, &sub.Status, &sub.HandlingNote, &atStr)
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return sql.ErrNoRows
			}
			return err
		}
		if imgID.Valid {
			v := imgID.Int64
			sub.ImageID = &v
		}
		sub.CreatedAt, _ = db.ParseUTC(atStr)
		sub.Status = "taken_down"
		sub.HandlingNote = note
		sub.ReviewedAt = &reviewedAt

		// 更新 submission 状态
		_, err = tx.ExecContext(txCtx, `
			UPDATE avatar_submissions
			SET status = 'taken_down', handling_note = ?, reviewed_at = ?
			WHERE id = ?
		`, note, db.FormatUTC(reviewedAt), submissionID)
		if err != nil {
			return err
		}

		// 若用户当前头像正是这张，将其重置为 NULL
		if sub.ImageID != nil {
			_, err = tx.ExecContext(txCtx, `
				UPDATE users
				SET avatar_image_id = NULL, version = version + 1, updated_at = ?
				WHERE id = ? AND avatar_image_id = ?
			`, db.FormatUTC(reviewedAt), sub.UserID, *sub.ImageID)
			if err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return &sub, nil
}
