package accounts

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"fmt"
	"math/big"
	"net/http"
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
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// Service 是账号域的业务服务。
type Service struct {
	d        *db.DB
	store    *Store
	clock    clock.Clock
	siteURL  string
	sessions *auth.Store
	// limiter 数登录失败（AuthLoginFailedKey 按账号，R006）；nil 表示不数
	// （apigen 场景；测试想要失败限流时传 ratelimit.NewEnforcer）。
	limiter *ratelimit.Enforcer
	// codeGen 造验证码（明文 + SHA-256 哈希）；测试换成固定码。
	codeGen func() (code, codeHash string, err error)
}

// NewService 创建账号服务。sessions 为 nil 时自建；limiter 为 nil 时登录失败
// 不按账号计数（注册表层的按 IP 限流不受影响）。
func NewService(d *db.DB, c clock.Clock, siteURL string, sessions *auth.Store, limiter *ratelimit.Enforcer) *Service {
	if c == nil {
		c = clock.System{}
	}
	if sessions == nil {
		sessions = auth.NewStore(d, c)
	}
	return &Service{
		d:        d,
		store:    NewStore(d),
		clock:    c,
		siteURL:  siteURL,
		sessions: sessions,
		limiter:  limiter,
		codeGen:  generateEmailCode,
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

	code, codeHash, err := s.codeGen()
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

// ResendCodeInput 是重新发送邮箱验证码的入参。
type ResendCodeInput struct {
	Email string
}

// ResendCodeResult 是重新发送邮箱验证码的结果。
type ResendCodeResult struct {
	Email   string
	Message string
}

// ResendCode 重新发送邮箱验证码（POST /api/auth/resend-code，12 号文档 5.7）。
// 业务契约：
// - R002：15 分钟有效、最多 3 次尝试、作废旧码发新码
// - R004：防止账号枚举（不存在、已停用、已验证、未验证均返回完全相同的成功响应）
// - R006：限流 1/10秒/账号（AuthResendEmailCodeKey）；接口层 10/分/IP（AuthResendEmailCode）
func (s *Service) ResendCode(ctx context.Context, in ResendCodeInput) (*ResendCodeResult, error) {
	trimmedEmail := strings.TrimSpace(in.Email)

	fields := make(map[string][]string)
	if trimmedEmail == "" {
		fields["email"] = []string{"请输入邮箱地址。"}
	} else if !validateEmail(trimmedEmail) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	emailNorm := strings.ToLower(trimmedEmail)

	// 先按账号限流（R006：10 秒内最多 1 次，在查库之前数，防枚举）
	if s.limiter != nil {
		retry, ok, err := s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResendEmailCodeKey)
		if err != nil {
			return nil, err
		}
		if !ok {
			return nil, api.TooManyRequests(retry)
		}
	}

	successRes := &ResendCodeResult{
		Email:   trimmedEmail,
		Message: "验证码已发送至你的邮箱，15 分钟内有效。",
	}

	u, err := s.store.GetByEmailNorm(ctx, emailNorm)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		// 账号不存在或已停用：静默成功，不发信（R004 防枚举）
		return successRes, nil
	}

	now := s.clock.Now().UTC()
	siteURL := strings.TrimRight(s.siteURL, "/")
	if siteURL == "" {
		siteURL = "https://sjtu.ow-shanghaiuniversity.com"
	}

	if u.EmailVerifiedAt != nil {
		// 账号已验证过：发提示信告知无需再次验证，不生成验证码（防枚举）
		err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
			letter := mail.Letter{
				Subject: "你的邮箱已完成验证",
				Lead:    "有人在 SJTU-OW 尝试为这个邮箱重新发送验证码，但该邮箱此前已经完成了验证，无需再次验证。",
				Action:  []string{"登录账号", siteURL + "/accounts/login/"},
				Note:    "如果你忘记了密码，可以通过找回密码重新设置。如果这不是你本人的操作，请忽略这封邮件，你的账号很安全。",
				Reason:  "你收到这封邮件，是因为有人在 SJTU-OW 尝试重新发送邮箱验证码。",
			}
			_, err := outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: u.Email, Name: u.Nickname}}, now)
			return err
		})
		if err != nil {
			return nil, err
		}
		return successRes, nil
	}

	// 未验证账号：作废旧码、生成新码入库、发信（R002）
	code, codeHash, err := s.codeGen()
	if err != nil {
		return nil, err
	}

	err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if err := s.store.DeleteEmailCodes(ctx, tx, "signup", emailNorm); err != nil {
			return err
		}
		if err := s.store.InsertEmailCode(ctx, tx, "signup", emailNorm, codeHash, now, now.Add(15*time.Minute)); err != nil {
			return err
		}
		letter := mail.Letter{
			Subject: "邮箱验证码",
			Lead:    "你的 SJTU-OW 邮箱验证码如下：",
			Code:    code,
			Note:    "验证码 15 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，不会有任何变化。",
			Reason:  "你收到这封邮件，是因为有人在 SJTU-OW 申请重新发送邮箱验证码。",
		}
		_, err := outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: u.Email, Name: u.Nickname}}, now)
		return err
	})
	if err != nil {
		return nil, err
	}

	return successRes, nil
}

// errBadCode 是核验失败的统一口径（R004 防枚举）：码不对、过期、用尽、
// 邮箱没注册，全都是同一句话，不泄露哪一条不成立。
var errBadCode = api.InvalidFields(map[string][]string{
	"code": {"验证码不正确或已过期。"},
})

// VerifyEmailInput 是邮箱验证码核验的入参。
type VerifyEmailInput struct {
	Email string
	Code  string
}

// VerifyEmailResult 是核验的结果。Token 是会话令牌（只进 HttpOnly Cookie，
// api 层负责写响应头，不进 JSON）。
type VerifyEmailResult struct {
	Token   string
	Message string
}

// VerifyEmail 凭「邮箱 + 6 位码」核验（12 号文档 5.7，241 起不需要会话）。
// 核验通过即登录：置 email_verified_at、删光该邮箱的 signup 码、建会话（R002、R008）。
func (s *Service) VerifyEmail(ctx context.Context, in VerifyEmailInput) (*VerifyEmailResult, error) {
	trimmedEmail := strings.TrimSpace(in.Email)
	code := strings.TrimSpace(in.Code)

	fields := make(map[string][]string)
	if trimmedEmail == "" {
		fields["email"] = []string{"请输入邮箱地址。"}
	} else if !validateEmail(trimmedEmail) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}
	if code == "" {
		fields["code"] = []string{"请输入验证码。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	emailNorm := strings.ToLower(trimmedEmail)
	now := s.clock.Now().UTC()

	// codeOK 是这次事务的结论。错码时事务仍然**提交**（attempts 的递增、
	// 用尽后的删码要保住），错误在外面报——跟着错误回滚的话计数就丢了，
	// 同一个码可以被无限试。
	var codeOK bool
	var verifiedUserID int64
	err := s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		u, err := s.store.GetByEmailNormTx(ctx, tx, emailNorm)
		if err != nil {
			return err
		}
		if u == nil {
			return nil
		}
		c, err := s.store.GetLatestEmailCodeTx(ctx, tx, "signup", emailNorm)
		if err != nil {
			return err
		}
		// 过期、用尽（R002：最多 3 次尝试）、没有码：不计数，直接失败
		if c == nil || !now.Before(c.ExpiresAt) || c.Attempts >= 3 {
			return nil
		}
		sum := sha256.Sum256([]byte(code))
		if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {
			if err := s.store.BumpEmailCodeAttempts(ctx, tx, c.ID); err != nil {
				return err
			}
			// 第 3 次错：码作废（R002）
			if c.Attempts+1 >= 3 {
				if err := s.store.DeleteEmailCode(ctx, tx, c.ID); err != nil {
					return err
				}
			}
			return nil
		}
		if err := s.store.MarkEmailVerified(ctx, tx, u.ID, now); err != nil {
			return err
		}
		if err := s.store.DeleteEmailCodes(ctx, tx, "signup", emailNorm); err != nil {
			return err
		}
		verifiedUserID = u.ID
		codeOK = true
		return nil
	})
	if err != nil {
		return nil, err
	}
	if !codeOK {
		return nil, errBadCode
	}

	token, err := s.sessions.Create(ctx, verifiedUserID)
	if err != nil {
		return nil, err
	}
	return &VerifyEmailResult{
		Token:   token,
		Message: "邮箱验证成功。接下来补全游戏 ID 和联系方式，就能报名内战和赛事了。",
	}, nil
}

// LoginInput 是登录的入参。
type LoginInput struct {
	Email    string
	Password string
}

// LoginResult 是登录的结果。Result 是 "ok" 或 "verify_required"
// （密码对、邮箱没验证过：已发新码，前端转验证页，不发会话）。
type LoginResult struct {
	Result  string
	Token   string
	Message string
}

// Login 只认邮箱 + 密码（12 号文档 5.7）。错误统一「邮箱或密码不正确」（R004）；
// 停用拒绝；未验证的发新码并提示去验证页；PBKDF2 的哈希验过即升级 Argon2。
// 限流：注册表按 IP 30 次/分（R006）；密码错按账号 5 次/300 秒（本函数里数）。
func (s *Service) Login(ctx context.Context, in LoginInput) (*LoginResult, error) {
	trimmedEmail := strings.TrimSpace(in.Email)

	fields := make(map[string][]string)
	if trimmedEmail == "" {
		fields["email"] = []string{"请输入邮箱地址。"}
	} else if !validateEmail(trimmedEmail) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}
	if in.Password == "" {
		fields["password"] = []string{"请输入密码。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	emailNorm := strings.ToLower(trimmedEmail)

	// 失败锁先查后数（R006：同账号 300 秒内 5 次失败）：锁定期内连正确密码
	// 也拒，免得爆破者可以一直试到撞对的那一次。
	if s.limiter != nil {
		n, retry, err := s.limiter.Count(ctx, "email:"+emailNorm, ratelimit.AuthLoginFailedKey)
		if err == nil && n >= int64(ratelimit.AuthLoginFailedKey.N) {
			return nil, api.TooManyRequests(retry)
		}
	}

	u, err := s.store.GetByEmailNorm(ctx, emailNorm)
	if err != nil {
		return nil, err
	}
	if u == nil {
		// 邮箱不存在也烧一遍 Argon2，让「邮箱不存在」和「密码不对」耗时一样（R004）
		if _, _, err := auth.Verify(ctx, "", in.Password); err != nil {
			return nil, err
		}
		s.hitLoginFailure(ctx, emailNorm)
		return nil, api.Unauthorized("邮箱或密码不正确")
	}

	// Argon2 在事务外算（一次约 100 MB，别占写锁）
	ok, upgrade, err := auth.Verify(ctx, u.PasswordHash, in.Password)
	if err != nil {
		return nil, err
	}
	if !ok {
		s.hitLoginFailure(ctx, emailNorm)
		return nil, api.Unauthorized("邮箱或密码不正确")
	}

	if !u.IsActive {
		// 密码已经对了，身份成立，可以说明原因（12 号文档 5.7「停用账号拒绝」）
		return nil, api.NewErr(http.StatusForbidden, "account_disabled", "这个账号已被停用，有疑问请联系管理员。")
	}

	now := s.clock.Now().UTC()

	if u.EmailVerifiedAt == nil {
		// 未验证：发一条新验证码（R002 重发），不发会话，前端转验证页
		code, codeHash, err := s.codeGen()
		if err != nil {
			return nil, err
		}
		err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
			if err := s.store.DeleteEmailCodes(ctx, tx, "signup", emailNorm); err != nil {
				return err
			}
			if err := s.store.InsertEmailCode(ctx, tx, "signup", emailNorm, codeHash, now, now.Add(15*time.Minute)); err != nil {
				return err
			}
			letter := mail.Letter{
				Subject: "邮箱验证码",
				Lead:    "有人用这个邮箱登录 SJTU-OW，但它还没有验证过。请输入下面的验证码完成验证：",
				Code:    code,
				Note:    "验证码 15 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，不会有任何变化。",
				Reason:  "你收到这封邮件，是因为有人在本站用这个邮箱登录。",
			}
			siteURL := strings.TrimRight(s.siteURL, "/")
			if siteURL == "" {
				siteURL = "https://sjtu.ow-shanghaiuniversity.com"
			}
			_, err := outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: u.Email, Name: u.Nickname}}, now)
			return err
		})
		if err != nil {
			return nil, err
		}
		return &LoginResult{
			Result:  "verify_required",
			Message: "这个邮箱还没验证过，新的验证码已发到邮箱。",
		}, nil
	}

	// PBKDF2（或旧参数 Argon2）验过：升级成现在的 Argon2（5.7 密码）
	if upgrade {
		newHash, err := auth.Hash(ctx, in.Password)
		if err != nil {
			return nil, err
		}
		err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
			return s.store.UpdatePasswordHash(ctx, tx, u.ID, newHash, now)
		})
		if err != nil {
			return nil, err
		}
	}

	token, err := s.sessions.Create(ctx, u.ID)
	if err != nil {
		return nil, err
	}
	return &LoginResult{Result: "ok", Token: token}, nil
}

// hitLoginFailure 在密码错（含邮箱不存在）之后数一次按账号的失败计数（R006）。
// 超没超在这里不看——锁在下次进入时由 Count 挡。计数器本身出问题不拦登录
// （登录是主路径，限流是防线，防线坏了不能把主路径堵死）。
func (s *Service) hitLoginFailure(ctx context.Context, emailNorm string) {
	if s.limiter == nil {
		return
	}
	_, _, _ = s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthLoginFailedKey)
}

// ResetPasswordInput 是找回密码发码请求的入参。
type ResetPasswordInput struct {
	Email string
}

// ResetPasswordResult 是找回密码发码请求的统一出参（R004 防枚举）。
type ResetPasswordResult struct {
	Email   string
	Message string
}

// ResetPasswordConfirmInput 是找回密码核验与重设密码的入参。
type ResetPasswordConfirmInput struct {
	Email           string
	Code            string
	Password        string
	ConfirmPassword string
}

// ResetPasswordConfirmResult 是找回密码核验与重设密码的出参。
type ResetPasswordConfirmResult struct {
	Result  string
	Message string
}

// RequestPasswordReset 请求发送找回密码验证码（POST /api/auth/reset-password，12 号文档 5.7）。
// 业务契约：
// - R003：3 分钟有效、最多 3 次尝试
// - R004：防止账号枚举（不存在、已停用均返回完全相同的成功响应；不存在账号发送「这个邮箱还没有注册」提醒信）
// - R006：限流 5/分/账号（AuthResetPasswordKey）；接口层 20/分/IP（AuthResetPassword）
func (s *Service) RequestPasswordReset(ctx context.Context, in ResetPasswordInput) (*ResetPasswordResult, error) {
	trimmedEmail := strings.TrimSpace(in.Email)

	fields := make(map[string][]string)
	if trimmedEmail == "" {
		fields["email"] = []string{"请输入邮箱地址。"}
	} else if !validateEmail(trimmedEmail) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	emailNorm := strings.ToLower(trimmedEmail)

	// 先按账号限流（R006：5 次/分/账号，在查库之前数，防枚举）
	if s.limiter != nil {
		retry, ok, err := s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResetPasswordKey)
		if err != nil {
			return nil, err
		}
		if !ok {
			return nil, api.TooManyRequests(retry)
		}
	}

	successRes := &ResetPasswordResult{
		Email:   trimmedEmail,
		Message: "如果该邮箱已注册，我们已向其发送了找回密码验证码。",
	}

	now := s.clock.Now().UTC()
	siteURL := strings.TrimRight(s.siteURL, "/")
	if siteURL == "" {
		siteURL = "https://sjtu.ow-shanghaiuniversity.com"
	}

	u, err := s.store.GetByEmailNorm(ctx, emailNorm)
	if err != nil {
		return nil, err
	}
	if u == nil {
		// 邮箱未注册：发「这个邮箱还没有注册」提醒信（附注册链接），返回统一响应防枚举（R004）
		err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
			letter := mail.Letter{
				Subject:    "这个邮箱还没有注册",
				Lead:       "有人用这个邮箱在 SJTU-OW 申请了账号操作（比如找回密码），但这个邮箱还没有注册过。",
				Paragraphs: []string{"如果不是你本人的操作，请忽略这封邮件。想加入的话，可以用这个邮箱注册："},
				Action:     []string{"注册", siteURL + "/accounts/signup/"},
				Note:       "如果这不是你本人的操作，请忽略这封邮件。",
				Reason:     "你收到这封邮件，是因为有人在本站填写了这个邮箱。",
			}
			_, err := outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: trimmedEmail, Name: ""}}, now)
			return err
		})
		if err != nil {
			return nil, err
		}
		return successRes, nil
	}

	if !u.IsActive {
		// 已停用账号：静默成功，不发信（R004 防枚举）
		return successRes, nil
	}

	// 正常账号：作废旧 password_reset 码、生成新码入库（3 分钟有效，R003）、发信
	code, codeHash, err := s.codeGen()
	if err != nil {
		return nil, err
	}

	err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if err := s.store.DeleteEmailCodes(ctx, tx, "password_reset", emailNorm); err != nil {
			return err
		}
		if err := s.store.InsertEmailCode(ctx, tx, "password_reset", emailNorm, codeHash, now, now.Add(3*time.Minute)); err != nil {
			return err
		}
		letter := mail.Letter{
			Subject: "找回密码验证码",
			Lead:    "你正在重置 SJTU-OW 账号的密码。请在页面上输入下面的验证码：",
			Code:    code,
			Note:    "验证码 3 分钟内有效。如果这不是你本人的操作，请忽略这封邮件，你的密码不会改变。",
			Reason:  "你收到这封邮件，是因为有人用这个邮箱申请了找回密码。",
		}
		_, err := outbox.Send(ctx, tx, nil, siteURL, letter, []mail.Person{{Address: u.Email, Name: u.Nickname}}, now)
		return err
	})
	if err != nil {
		return nil, err
	}

	return successRes, nil
}

// ResetPasswordConfirm 核验验证码并重置密码（POST /api/auth/reset-password/confirm，12 号文档 5.7）。
// 业务契约：
// - R003：核验 3 分钟内有效、最多 3 次尝试（错码加 attempts，达到 3 次物理删除作废）
// - R004：防止账号枚举（统一报错 errBadCode）
// - 密码强度与一致性校验
// - 事务外计算 Argon2id 哈希
// - 事务内更新密码，若此前未验证邮箱则置为已验证，删除该邮箱所有重置码，清空该用户所有现有会话（5.7）
// - 严格不发会话 Cookie
func (s *Service) ResetPasswordConfirm(ctx context.Context, in ResetPasswordConfirmInput) (*ResetPasswordConfirmResult, error) {
	trimmedEmail := strings.TrimSpace(in.Email)
	code := strings.TrimSpace(in.Code)

	fields := make(map[string][]string)
	if trimmedEmail == "" {
		fields["email"] = []string{"请输入邮箱地址。"}
	} else if !validateEmail(trimmedEmail) {
		fields["email"] = []string{"请输入有效的邮箱地址。"}
	}
	if code == "" {
		fields["code"] = []string{"请输入验证码。"}
	}
	if in.Password == "" {
		fields["password"] = []string{"请输入新密码。"}
	} else if in.Password != in.ConfirmPassword {
		fields["confirm_password"] = []string{"两次输入的密码不一致。"}
	} else {
		pwdErrs := auth.Validate(in.Password, trimmedEmail, "")
		if len(pwdErrs) > 0 {
			fields["password"] = pwdErrs
		}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	// 事务外计算 Argon2 哈希，避免长事务持有写锁
	pwdHash, err := auth.Hash(ctx, in.Password)
	if err != nil {
		return nil, err
	}

	emailNorm := strings.ToLower(trimmedEmail)
	now := s.clock.Now().UTC()

	var codeOK bool
	err = s.d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		u, err := s.store.GetByEmailNormTx(ctx, tx, emailNorm)
		if err != nil {
			return err
		}
		if u == nil || !u.IsActive {
			return nil
		}
		c, err := s.store.GetLatestEmailCodeTx(ctx, tx, "password_reset", emailNorm)
		if err != nil {
			return err
		}
		// 过期、用尽（最多 3 次尝试）、没有码：直接失败，不自增 attempts
		if c == nil || !now.Before(c.ExpiresAt) || c.Attempts >= 3 {
			return nil
		}
		sum := sha256.Sum256([]byte(code))
		if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(c.CodeHash)) != 1 {
			if err := s.store.BumpEmailCodeAttempts(ctx, tx, c.ID); err != nil {
				return err
			}
			// 第 3 次错：码作废（R003）
			if c.Attempts+1 >= 3 {
				if err := s.store.DeleteEmailCode(ctx, tx, c.ID); err != nil {
					return err
				}
			}
			return nil
		}

		// 验证码通过：
		// 1. 删除该邮箱的所有 password_reset 验证码
		if err := s.store.DeleteEmailCodes(ctx, tx, "password_reset", emailNorm); err != nil {
			return err
		}
		// 2. 更新密码，如果原先未验证邮箱则置为已验证
		_, err = tx.ExecContext(ctx, `UPDATE users SET
			password_hash = ?,
			password_changed_at = ?,
			email_verified_at = COALESCE(email_verified_at, ?),
			updated_at = ?
			WHERE id = ?`,
			pwdHash, db.FormatUTC(now), db.FormatUTC(now), db.FormatUTC(now), u.ID)
		if err != nil {
			return err
		}
		// 3. 删掉该用户的所有现有会话（改密码作废其他会话，12 号文档 5.7）
		_, err = tx.ExecContext(ctx, `DELETE FROM sessions WHERE user_id = ?`, u.ID)
		if err != nil {
			return err
		}

		codeOK = true
		return nil
	})
	if err != nil {
		return nil, err
	}
	if !codeOK {
		return nil, errBadCode
	}

	return &ResetPasswordConfirmResult{
		Result:  "ok",
		Message: "密码重置成功，请使用新密码登录。",
	}, nil
}

// ChangePasswordInput 是修改密码的入参。
type ChangePasswordInput struct {
	OldPassword     string
	Password        string
	ConfirmPassword string
}

// ChangePasswordResult 是修改密码的结果。
type ChangePasswordResult struct {
	Result  string
	Message string
}

// LogoutResult 是退出登录的结果。
type LogoutResult struct {
	Result  string
	Message string
}

// ChangePassword 处理已登录用户修改当前密码（规则 R006、12 号文档 5.4、5.7）。
func (s *Service) ChangePassword(ctx *app.Ctx, in ChangePasswordInput) (*ChangePasswordResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	fields := make(map[string][]string)
	if in.OldPassword == "" {
		fields["old_password"] = []string{"请输入当前密码。"}
	}
	if in.Password == "" {
		fields["password"] = []string{"请输入新密码。"}
	}
	if in.ConfirmPassword == "" {
		fields["confirm_password"] = []string{"请再次输入新密码。"}
	} else if in.Password != in.ConfirmPassword {
		fields["confirm_password"] = []string{"两次输入的密码不一致。"}
	}
	if in.OldPassword != "" && in.Password != "" && in.OldPassword == in.Password {
		fields["password"] = []string{"新密码不能与当前密码相同。"}
	}
	if len(fields) > 0 {
		return nil, api.InvalidFields(fields)
	}

	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("要先登录")
	}

	ok, _, err := auth.Verify(ctx.Context, u.PasswordHash, in.OldPassword)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, api.InvalidFields(map[string][]string{"old_password": {"当前密码不正确。"}})
	}

	pwdErrs := auth.Validate(in.Password, u.Email, u.Nickname)
	if len(pwdErrs) > 0 {
		return nil, api.InvalidFields(map[string][]string{"password": pwdErrs})
	}

	// 事务外计算 Argon2 哈希，避免长事务持有写锁
	pwdHash, err := auth.Hash(ctx.Context, in.Password)
	if err != nil {
		return nil, err
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `UPDATE users SET
			password_hash = ?,
			password_changed_at = ?,
			updated_at = ?
			WHERE id = ?`,
			pwdHash, db.FormatUTC(now), db.FormatUTC(now), u.ID)
		if err != nil {
			return err
		}
		// 作废该用户的其他会话，保留当前会话（12 号文档 5.7）
		return s.sessions.DeleteOthersTx(txCtx, tx, u.ID, ctx.SessionToken)
	})
	if err != nil {
		return nil, err
	}

	return &ChangePasswordResult{
		Result:  "ok",
		Message: "密码修改成功。",
	}, nil
}

// Logout 注销当前会话（作废会话行并清除 Cookie，12 号文档 5.7）。
func (s *Service) Logout(ctx *app.Ctx) (*LogoutResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if ctx.SessionToken != "" {
		if err := s.sessions.Delete(ctx.Context, ctx.SessionToken); err != nil {
			return nil, err
		}
	}
	ctx.ClearSessionCookie()
	return &LogoutResult{
		Result:  "ok",
		Message: "已退出登录。",
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
