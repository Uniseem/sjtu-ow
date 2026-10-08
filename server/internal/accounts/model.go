package accounts

import (
	"strings"
	"time"
)

// User 是新栈用户实体（对应 users 表，12 号文档 7）。
type User struct {
	ID                  int64
	Email               string
	EmailNorm           string
	PasswordHash        string
	Nickname            string
	IsSJTU              bool
	AgreedTermsAt       time.Time
	AgreedCrossBorderAt time.Time
	EmailVerifiedAt     *time.Time
	PasswordChangedAt   *time.Time
	Version             int64
	IsActive            bool
	IsSuperuser         bool
	DeactivationNote    string
	Motto               string
	ShowRank            bool
	CreatedAt           time.Time
	UpdatedAt           time.Time
}

// EmailVerified 检查邮箱是否已验证。
func (u *User) EmailVerified() bool {
	return u != nil && u.EmailVerifiedAt != nil && !u.EmailVerifiedAt.IsZero()
}

// NormalizeEmail 规范化邮箱（小写并去除两端空格）。
func NormalizeEmail(email string) string {
	return strings.ToLower(strings.TrimSpace(email))
}
