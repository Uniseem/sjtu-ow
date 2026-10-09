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
	MainRole            string
	FlexRoles           string
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

// GameAccount 是绑定的守望先锋游戏 ID（对应 game_accounts 表，规则 16–17）。
type GameAccount struct {
	ID             int64
	UserID         int64
	Battletag      string
	BattletagNorm  string
	RankTank       *int
	RankDamage     *int
	RankSupport    *int
	RanksUpdatedAt time.Time
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// NormalizeBattletag 规范化 BattleTag（小写）。
func NormalizeBattletag(tag string) string {
	return strings.ToLower(strings.TrimSpace(tag))
}

// Contact 是用户的联系方式（对应 contacts 表，规则 18–19）。
type Contact struct {
	ID        int64
	UserID    int64
	Type      string
	Value     string
	CreatedAt time.Time
	UpdatedAt time.Time
}

// 联系方式类型常量（对齐 Django ContactType，规则 19）。
const (
	ContactQQ     = "qq"
	ContactWeChat = "wechat"
	ContactPhone  = "phone"
	ContactOther  = "other"
)

// AllContactTypes 全部合法的联系方式类型。
var AllContactTypes = map[string]string{
	ContactQQ:     "QQ",
	ContactWeChat: "微信",
	ContactPhone:  "手机号",
	ContactOther:  "其他",
}

// IsValidContactType 检查联系方式类型是否合法。
func IsValidContactType(t string) bool {
	_, ok := AllContactTypes[t]
	return ok
}
