package ops

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// SuperuserOptions 超管创建参数（12 号文档 5.7、规则 15）。
type SuperuserOptions struct {
	Email    string
	Nickname string
	Password string
	IsSJTU   bool
}

// CreateSuperuser 创建直接已验证的超级管理员账号。
func CreateSuperuser(ctx context.Context, d *db.DB, opts SuperuserOptions) error {
	if d == nil {
		return fmt.Errorf("数据库连接为空")
	}

	email := strings.TrimSpace(opts.Email)
	if email == "" || !strings.Contains(email, "@") {
		return fmt.Errorf("邮箱格式无效：%q", email)
	}

	nickname := strings.TrimSpace(opts.Nickname)
	if nickname == "" {
		nickname = "超级管理员"
	}

	if opts.Password == "" {
		return fmt.Errorf("密码不能为空")
	}

	// 密码安全强度校验（Django 兼容 4 条规则）
	if msgs := auth.Validate(opts.Password, email, nickname); len(msgs) > 0 {
		return fmt.Errorf("密码不满足安全要求：%s", strings.Join(msgs, "；"))
	}

	norm := accounts.NormalizeEmail(email)

	// 计算 Argon2id 哈希
	hash, err := auth.Hash(ctx, opts.Password)
	if err != nil {
		return fmt.Errorf("计算密码哈希失败: %w", err)
	}

	now := time.Now().UTC()
	nowStr := db.FormatUTC(now)
	isSJTU := 0
	if opts.IsSJTU {
		isSJTU = 1
	}

	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		// 检查邮箱是否已存在
		var existingID int64
		err := tx.QueryRowContext(txCtx, "SELECT id FROM users WHERE email_norm = ?", norm).Scan(&existingID)
		if err == nil {
			return fmt.Errorf("邮箱已被注册：%s", email)
		} else if err != sql.ErrNoRows {
			return fmt.Errorf("查询用户失败: %w", err)
		}

		// 插入超级管理员（规则 15：服务端背书直接已验证）
		_, err = tx.ExecContext(txCtx, `INSERT INTO users (
			email, email_norm, password_hash, nickname, is_sjtu,
			agreed_terms_at, agreed_cross_border_at, email_verified_at, password_changed_at,
			version, is_active, is_superuser, deactivation_note, motto, main_role, flex_roles, show_rank,
			created_at, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 1, 1, 1, '', '', '', '', 0, ?, ?)`,
			email, norm, hash, nickname, isSJTU,
			nowStr, nowStr, nowStr,
			nowStr, nowStr,
		)
		if err != nil {
			return fmt.Errorf("创建超级管理员失败: %w", err)
		}
		return nil
	})
}
