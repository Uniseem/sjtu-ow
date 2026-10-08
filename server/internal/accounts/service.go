package accounts

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math/big"
	netmail "net/mail"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
)

// Service 是账号域的业务服务。
type Service struct {
	d       *db.DB
	store   *Store
	clock   clock.Clock
	siteURL string
}

// NewService 创建账号服务。
func NewService(d *db.DB, c clock.Clock, siteURL string) *Service {
	if c == nil {
		c = clock.System{}
	}
	return &Service{
		d:       d,
		store:   NewStore(d),
		clock:   c,
		siteURL: siteURL,
	}
}

// Store 返回底层的 Store。
func (s *Service) Store() *Store {
	return s.store
}

// RegisterInput 是用户注册的入参。
type RegisterInput struct {
	Email            string
	Nickname         string
	Password         string
	ConfirmPassword  string
	IsSJTU           *bool
	AgreeTerms       bool
	AgreeCrossBorder bool
}

// RegisterResult 是用户注册的结果。
type RegisterResult struct {
	Email   string
	Message string
}

func validateEmail(s string) bool {
	s = strings.TrimSpace(s)
	if len(s) < 3 || len(s) > 254 {
		return false
	}
	addr, err := netmail.ParseAddress(s)
	if err != nil || addr.Address != s {
		return false
	}
	parts := strings.Split(s, "@")
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return false
	}
	domain := parts[1]
	if !strings.Contains(domain, ".") || strings.HasPrefix(domain, ".") || strings.HasSuffix(domain, ".") {
		return false
	}
	return true
}

func generateEmailCode() (string, string, error) {
	n, err := rand.Int(rand.Reader, big.NewInt(1000000))
	if err != nil {
		return "", "", err
	}
	code := fmt.Sprintf("%06d", n.Int64())
	sum := sha256.Sum256([]byte(code))
	return code, hex.EncodeToString(sum[:]), nil
}

// Register 处理新用户注册（规则 R001–R005、R010）。
func (s *Service) Register(ctx context.Context, in RegisterInput) (*RegisterResult, error) {
	fields := make(map[string][]string)

	trimmedEmail := strings.TrimSpace(in.Email)
	if trimmedEmail == "" {
		fields["email"] = []string{"请输入邮箱地址。"}
	} else if !validateEmail(trimmedEmail) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}

	trimmedNickname := strings.TrimSpace(in.Nickname)
	runeLen := len([]rune(trimmedNickname))
	if trimmedNickname == "" {
		fields["nickname"] = []string{"请输入昵称。"}
	} else if runeLen < 2 || runeLen > 16 {
		fields["nickname"] = []string{"昵称长度需在 2 到 16 个字符之间。"}
	}

	if in.Password == "" {
		fields["password"] = []string{"请输入密码。"}
	} else {
		pwdErrs := auth.Validate(in.Password, trimmedEmail, trimmedNickname)
		if len(pwdErrs) > 0 {
			fields["password"] = pwdErrs
		}
	}

	if in.ConfirmPassword == "" {
		fields["confirm_password"] = []string{"请再次输入密码。"}
	} else if in.ConfirmPassword != in.Password {
		fields["confirm_password"] = []string{"两次输入的密码不一致。"}
	}

	if in.IsSJTU == nil {
		fields["is_sjtu"] = []string{"请选择是否来自上海交通大学。"}
	}

	if !in.AgreeTerms {
		fields["agree_terms"] = []string{"请阅读并同意用户协议和隐私政策。"}
	}

	if !in.AgreeCrossBorder {
		fields["agree_cross_border"] = []string{"请同意将个人信息存储在境外服务器。"}
	}

	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	emailNorm := strings.ToLower(trimmedEmail)

	// 事务外完成昂贵的密码哈希和验证码计算（12 号文档 5.6/5.7）
	pwdHash, err := auth.Hash(ctx, in.Password)
	if err != nil {
		return nil, err
	}

	code, codeHash, err := generateEmailCode()
	if err != nil {
		return nil, err
	}

	now := s.clock.Now().UTC()
	siteURL := strings.TrimRight(s.siteURL, "/")
	if siteURL == "" {
		siteURL = "https://sjtu.ow-shanghaiuniversity.com"
	}

	err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		existing, err := s.store.GetByEmailNormTx(ctx, tx, emailNorm)
		if err != nil {
			return err
		}
		if existing != nil {
			// 防枚举：邮箱已注册过时不新建账号、不存验证码，发送已注册提醒信（R004）
			letter := mail.Letter{
				Subject:    "这个邮箱已经注册过",
				Lead:       fmt.Sprintf("有人用这个邮箱（%s）在 SJTU-OW 注册，但它已经注册过了，所以没有新建账号。", trimmedEmail),
				Paragraphs: []string{"如果你是本人，只是忘了注册过，可以直接找回密码："},
				Action:     []string{"找回密码", siteURL + "/accounts/password/reset/"},
				Note:       "如果不是你本人的操作，请忽略这封邮件，你的账号不受影响。",
				Reason:     "你收到这封邮件，是因为有人在本站填写了这个邮箱。",
			}
			_, err = outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: trimmedEmail, Name: existing.Nickname}}, now)
			return err
		}

		// 未注册：新建未验证用户（R001、R002）
		u := &User{
			Email:               trimmedEmail,
			EmailNorm:           emailNorm,
			PasswordHash:        pwdHash,
			Nickname:            trimmedNickname,
			IsSJTU:              *in.IsSJTU,
			AgreedTermsAt:       now,
			AgreedCrossBorderAt: now,
			EmailVerifiedAt:     nil, // 未验证
			PasswordChangedAt:   &now,
			Version:             1,
			IsActive:            true,
			IsSuperuser:         false,
			CreatedAt:           now,
			UpdatedAt:           now,
		}
		if _, err := s.store.InsertUser(ctx, tx, u); err != nil {
			return err
		}

		// 存入 6 位验证码（15 分钟有效，最多 3 次尝试，R002）
		if err := s.store.DeleteEmailCodes(ctx, tx, "signup", emailNorm); err != nil {
			return err
		}
		if err := s.store.InsertEmailCode(ctx, tx, "signup", emailNorm, codeHash, now, now.Add(15*time.Minute)); err != nil {
			return err
		}

		// 发送验证码邮件（经 outbox 直接入队 jobs.LaneMail）
		letter := mail.Letter{
			Subject: "邮箱验证码",
			Lead:    "你正在注册 SJTU-OW，或者给账号换一个邮箱。请在页面上输入下面的验证码：",
			Code:    code,
			Note:    "验证码 15 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，不会有任何变化。",
			Reason:  "你收到这封邮件，是因为有人在本站填写了这个邮箱。",
		}
		_, err = outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: trimmedEmail, Name: trimmedNickname}}, now)
		return err
	})
	if err != nil {
		return nil, err
	}

	return &RegisterResult{
		Email:   trimmedEmail,
		Message: "验证码已发送至你的邮箱，15 分钟内有效。",
	}, nil
}

// BuildViewer 根据用户 ID 从数据库组装 *app.Viewer（12 号文档 5.2、5.8）。
// 未登录或账号不存在返回 nil。停用账号返回 Disabled: true 的 Viewer。
func (s *Service) BuildViewer(ctx context.Context, userID int64) (*app.Viewer, error) {
	if userID <= 0 {
		return nil, nil
	}
	u, err := s.store.GetByID(ctx, userID)
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, nil
	}
	if !u.IsActive {
		return &app.Viewer{
			ID:       u.ID,
			Disabled: true,
		}, nil
	}

	storedRoles, err := s.store.GetUserRoles(ctx, u.ID)
	if err != nil {
		return nil, err
	}
	userRules, err := s.store.GetFeatureUserRules(ctx, u.ID)
	if err != nil {
		return nil, err
	}
	roleRestrs, err := s.store.GetFeatureRoleRestrictions(ctx)
	if err != nil {
		return nil, err
	}

	// 判定投稿者资格所需的前提
	canSubmit, _ := CanUse(u, FeatureArticleSubmit, userRules, roleRestrs, storedRoles)
	derived := DerivedRoles(u.IsSJTU, u.IsActive, u.EmailVerified(), canSubmit)

	// 汇总所有角色拥有的后台能力（Caps）
	caps := make(map[app.Cap]struct{})
	allRoles := append([]string(nil), storedRoles...)
	allRoles = append(allRoles, derived...)
	for _, r := range allRoles {
		for _, c := range CapsForRole(r) {
			caps[c] = struct{}{}
		}
	}

	// 预先算好单人受限的所有 Feature
	deniedMap := make(map[app.Feature]struct{})
	for feat := range allFeatures {
		allowed, _ := CanUse(u, feat, userRules, roleRestrs, storedRoles)
		if !allowed {
			deniedMap[feat] = struct{}{}
		}
	}

	return &app.Viewer{
		ID:            u.ID,
		Disabled:      false,
		EmailVerified: u.EmailVerified(),
		Superuser:     u.IsSuperuser,
		Caps:          caps,
		FeatureDenied: deniedMap,
	}, nil
}
