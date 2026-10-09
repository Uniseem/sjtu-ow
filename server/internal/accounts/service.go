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

// -------------------------------------------------------------
// 重新认证与改邮箱 (Reauthentication & Email Change, 规则 6、7)
// -------------------------------------------------------------

// ReauthInput 重新认证入参。
type ReauthInput struct {
	Password string `json:"password"`
}

// ReauthResult 重新认证出参。
type ReauthResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// Reauthenticate 重新认证当前会话（输密码，规则 6、7）。
func (s *Service) Reauthenticate(ctx *app.Ctx, in ReauthInput) (*ReauthResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}

	match, _, err := auth.Verify(ctx.Context, u.PasswordHash, in.Password)
	if err != nil || !match {
		return nil, api.InvalidFields(map[string][]string{"password": {"当前密码不正确。"}})
	}

	if ctx.SessionToken != "" {
		if err := s.sessions.MarkReauth(ctx.Context, ctx.SessionToken); err != nil {
			return nil, err
		}
	}

	return &ReauthResult{
		Result:  "ok",
		Message: "重新认证成功。",
	}, nil
}

// RequestEmailChangeInput 请求换绑邮箱入参。
type RequestEmailChangeInput struct {
	NewEmail string `json:"new_email"`
}

// RequestEmailChangeResult 请求换绑邮箱出参。
type RequestEmailChangeResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// RequestEmailChange 申请更换登录邮箱（发码至新邮箱，规则 7）。
func (s *Service) RequestEmailChange(ctx *app.Ctx, in RequestEmailChangeInput) (*RequestEmailChangeResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	// 5 分钟内必须重新认证过（规则 7）
	if ctx.SessionToken != "" {
		sess, err := s.sessions.Lookup(ctx.Context, ctx.SessionToken)
		if err != nil || sess == nil || !sess.RecentlyReauthed(s.clock.Now()) {
			return nil, api.Invalid("请先重新认证当前密码（5 分钟内有效）。")
		}
	}

	trimmedEmail := strings.TrimSpace(in.NewEmail)
	if !validateEmail(trimmedEmail) {
		return nil, api.InvalidFields(map[string][]string{"new_email": {"请输入有效的邮箱地址。"}})
	}

	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}

	newEmailNorm := NormalizeEmail(trimmedEmail)
	if newEmailNorm == u.EmailNorm {
		return nil, api.InvalidFields(map[string][]string{"new_email": {"新邮箱不能与当前邮箱相同。"}})
	}

	existing, err := s.store.GetByEmailNorm(ctx.Context, newEmailNorm)
	if err != nil {
		return nil, err
	}
	if existing != nil && existing.ID != u.ID {
		return nil, api.InvalidFields(map[string][]string{"new_email": {"该邮箱已被其他账号占用。"}})
	}

	code, codeHash, err := s.codeGen()
	if err != nil {
		return nil, err
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		ec := &EmailChange{
			UserID:       u.ID,
			NewEmail:     trimmedEmail,
			NewEmailNorm: newEmailNorm,
			CodeHash:     codeHash,
			CreatedAt:    now,
			ExpiresAt:    now.Add(15 * time.Minute),
		}
		if err := s.store.InsertEmailChange(txCtx, tx, ec); err != nil {
			return err
		}

		letter := mail.Letter{
			Subject: "验证你的新邮箱",
			Lead:    "你正在更换 SJTU-OW 账号的登录邮箱。请在页面上输入下面的验证码：",
			Code:    code,
			Note:    "验证码 15 分钟内有效、最多尝试 3 次。如果这不是你本人的操作，请忽略这封邮件。",
			Reason:  "你收到这封邮件，是因为有人申请将此邮箱绑定为 SJTU-OW 账号。",
		}
		_, err := outbox.Send(txCtx, tx, nil, s.siteURL, letter, []mail.Person{{Address: trimmedEmail, Name: u.Nickname}}, now)
		return err
	})
	if err != nil {
		return nil, err
	}

	return &RequestEmailChangeResult{
		Result:  "ok",
		Message: "验证码已发送至新邮箱。",
	}, nil
}

// ConfirmEmailChangeInput 确认换绑邮箱入参。
type ConfirmEmailChangeInput struct {
	Code string `json:"code"`
}

// ConfirmEmailChangeResult 确认换绑邮箱出参。
type ConfirmEmailChangeResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// ConfirmEmailChange 核验新邮箱验证码并替换主邮箱（规则 7）。
func (s *Service) ConfirmEmailChange(ctx *app.Ctx, in ConfirmEmailChangeInput) (*ConfirmEmailChangeResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	trimmedCode := strings.TrimSpace(in.Code)
	if len(trimmedCode) != 6 {
		return nil, api.InvalidFields(map[string][]string{"code": {"请输入 6 位数字验证码。"}})
	}

	now := s.clock.Now().UTC()
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		ec, err := s.store.GetEmailChangeTx(txCtx, tx, ctx.Viewer.ID)
		if err != nil {
			return err
		}
		if ec == nil || !now.Before(ec.ExpiresAt) {
			return api.InvalidFields(map[string][]string{"code": {"验证码已失效，请重新申请。"}})
		}
		if ec.Attempts >= 3 {
			_ = s.store.DeleteEmailChange(txCtx, tx, ctx.Viewer.ID)
			return api.InvalidFields(map[string][]string{"code": {"验证码尝试次数过多，请重新申请。"}})
		}

		sum := sha256.Sum256([]byte(trimmedCode))
		codeHash := hex.EncodeToString(sum[:])
		if subtle.ConstantTimeCompare([]byte(codeHash), []byte(ec.CodeHash)) != 1 {
			_ = s.store.BumpEmailChangeAttempts(txCtx, tx, ctx.Viewer.ID)
			if ec.Attempts+1 >= 3 {
				_ = s.store.DeleteEmailChange(txCtx, tx, ctx.Viewer.ID)
			}
			return api.InvalidFields(map[string][]string{"code": {"验证码不正确。"}})
		}

		// 检查新邮箱是否在核验期间被其他人占用
		existing, err := s.store.GetByEmailNormTx(txCtx, tx, ec.NewEmailNorm)
		if err != nil {
			return err
		}
		if existing != nil && existing.ID != ctx.Viewer.ID {
			return api.InvalidFields(map[string][]string{"code": {"该邮箱已被占用。"}})
		}

		if err := s.store.UpdateUserEmail(txCtx, tx, ctx.Viewer.ID, ec.NewEmail, ec.NewEmailNorm, now); err != nil {
			return err
		}
		return s.store.DeleteEmailChange(txCtx, tx, ctx.Viewer.ID)
	})
	if err != nil {
		return nil, err
	}

	return &ConfirmEmailChangeResult{
		Result:  "ok",
		Message: "邮箱修改成功。",
	}, nil
}

// -------------------------------------------------------------
// 个人资料 (Profile, 规则 18–21)
// -------------------------------------------------------------

// ProfileResult 个人资料详情出参。
type ProfileResult struct {
	ID           int64               `json:"id"`
	Nickname     string              `json:"nickname"`
	Email        string              `json:"email"`
	IsSJTU       bool                `json:"is_sjtu"`
	Motto        string              `json:"motto"`
	MainRole     string              `json:"main_role"`
	FlexRoles    string              `json:"flex_roles"`
	ShowRank     bool                `json:"show_rank"`
	IsComplete   bool                `json:"is_complete"`
	PublicRanks  PublicRanksResult   `json:"public_ranks"`
	GameAccounts []GameAccountResult `json:"game_accounts"`
	Contacts     []ContactResult     `json:"contacts"`
}

// UpdateProfileInput 更新资料入参。
type UpdateProfileInput struct {
	Nickname  string `json:"nickname"`
	Motto     string `json:"motto"`
	MainRole  string `json:"main_role"`
	FlexRoles string `json:"flex_roles"`
	ShowRank  bool   `json:"show_rank"`
	IsSJTU    *bool  `json:"is_sjtu"`
}

// UpdateProfileResult 更新资料出参。
type UpdateProfileResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// GetProfile 读当前登录用户的个人资料、游戏 ID、联系方式与段位。
func (s *Service) GetProfile(ctx *app.Ctx) (*ProfileResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}

	gas, err := s.store.GetGameAccountsByUserID(ctx.Context, u.ID)
	if err != nil {
		return nil, err
	}
	contacts, err := s.store.GetContactsByUserID(ctx.Context, u.ID)
	if err != nil {
		return nil, err
	}

	now := s.clock.Now().UTC()
	pubRanks := CalculatePublicRanks(gas, u.ShowRank, now)
	isComplete := IsProfileComplete(len(gas), len(contacts))

	var gaResults []GameAccountResult
	for _, ga := range gas {
		gaResults = append(gaResults, toGameAccountResult(ga))
	}

	var contactResults []ContactResult
	for _, c := range contacts {
		contactResults = append(contactResults, toContactResult(c))
	}

	return &ProfileResult{
		ID:           u.ID,
		Nickname:     u.Nickname,
		Email:        u.Email,
		IsSJTU:       u.IsSJTU,
		Motto:        u.Motto,
		MainRole:     u.MainRole,
		FlexRoles:    u.FlexRoles,
		ShowRank:     u.ShowRank,
		IsComplete:   isComplete,
		PublicRanks:  pubRanks,
		GameAccounts: gaResults,
		Contacts:     contactResults,
	}, nil
}

// UpdateProfile 更新个人资料（昵称、宣言、主位置、副位置、段位公开，规则 18–20）。
func (s *Service) UpdateProfile(ctx *app.Ctx, in UpdateProfileInput) (*UpdateProfileResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}

	fieldErrs := make(map[string][]string)

	trimmedNickname := strings.TrimSpace(in.Nickname)
	if err := ValidateNickname(trimmedNickname); err != nil {
		fieldErrs["nickname"] = []string{err.Error()}
	}

	trimmedMotto := strings.TrimSpace(in.Motto)
	if err := ValidateMotto(trimmedMotto); err != nil {
		fieldErrs["motto"] = []string{err.Error()}
	}

	mainRole := strings.TrimSpace(in.MainRole)
	if mainRole != "" && mainRole != "tank" && mainRole != "damage" && mainRole != "support" {
		fieldErrs["main_role"] = []string{"主位置必须是 tank、damage、support 之一。"}
	}

	if len(fieldErrs) > 0 {
		return nil, api.InvalidFields(fieldErrs)
	}

	isSJTU := u.IsSJTU
	if in.IsSJTU != nil {
		isSJTU = *in.IsSJTU
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.UpdateUserProfile(txCtx, tx, u.ID, trimmedNickname, trimmedMotto, mainRole, in.FlexRoles, in.ShowRank, isSJTU, now)
	})
	if err != nil {
		return nil, err
	}

	return &UpdateProfileResult{
		Result:  "ok",
		Message: "资料已保存。",
	}, nil
}

// -------------------------------------------------------------
// 游戏 ID (GameAccount, 规则 16–17)
// -------------------------------------------------------------

// AddGameAccountInput 绑定游戏 ID 入参。
type AddGameAccountInput struct {
	Battletag   string `json:"battletag"`
	RankTank    *int   `json:"rank_tank"`
	RankDamage  *int   `json:"rank_damage"`
	RankSupport *int   `json:"rank_support"`
}

// UpdateGameAccountInput 更新游戏 ID 入参。
type UpdateGameAccountInput struct {
	ID          api.ID `path:"id"`
	RankTank    *int   `json:"rank_tank"`
	RankDamage  *int   `json:"rank_damage"`
	RankSupport *int   `json:"rank_support"`
}

// GameAccountResult 游戏 ID 出参。
type GameAccountResult struct {
	ID             int64     `json:"id"`
	Battletag      string    `json:"battletag"`
	RankTank       *int      `json:"rank_tank"`
	RankDamage     *int      `json:"rank_damage"`
	RankSupport    *int      `json:"rank_support"`
	TankLabel      string    `json:"tank_label"`
	DamageLabel    string    `json:"damage_label"`
	SupportLabel   string    `json:"support_label"`
	RanksUpdatedAt time.Time `json:"ranks_updated_at"`
}

func toGameAccountResult(ga GameAccount) GameAccountResult {
	return GameAccountResult{
		ID:             ga.ID,
		Battletag:      ga.Battletag,
		RankTank:       ga.RankTank,
		RankDamage:     ga.RankDamage,
		RankSupport:    ga.RankSupport,
		TankLabel:      FormatRank(ga.RankTank),
		DamageLabel:    FormatRank(ga.RankDamage),
		SupportLabel:   FormatRank(ga.RankSupport),
		RanksUpdatedAt: ga.RanksUpdatedAt,
	}
}

// AddGameAccount 绑定新游戏 ID（每人最多 5 个，全站唯一，规则 16–17）。
func (s *Service) AddGameAccount(ctx *app.Ctx, in AddGameAccountInput) (*GameAccountResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	cnt, err := s.store.CountGameAccountsByUserID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if cnt >= 5 {
		return nil, api.Invalid("每人最多绑定 5 个游戏 ID。")
	}

	trimmedTag := strings.TrimSpace(in.Battletag)
	if err := ValidateBattletag(trimmedTag); err != nil {
		return nil, api.InvalidFields(map[string][]string{"battletag": {err.Error()}})
	}

	norm := NormalizeBattletag(trimmedTag)
	existing, err := s.store.GetGameAccountByBattletagNorm(ctx.Context, norm)
	if err != nil {
		return nil, err
	}
	if existing != nil {
		return nil, api.InvalidFields(map[string][]string{"battletag": {"该游戏 ID 已被其他账号绑定，如有疑问请联系管理员"}})
	}

	for field, score := range map[string]*int{"rank_tank": in.RankTank, "rank_damage": in.RankDamage, "rank_support": in.RankSupport} {
		if score != nil && (*score < 0 || *score > Top500Score) {
			return nil, api.InvalidFields(map[string][]string{field: {"非法段位分数"}})
		}
	}

	now := s.clock.Now().UTC()
	ga := &GameAccount{
		UserID:         ctx.Viewer.ID,
		Battletag:      trimmedTag,
		BattletagNorm:  norm,
		RankTank:       in.RankTank,
		RankDamage:     in.RankDamage,
		RankSupport:    in.RankSupport,
		RanksUpdatedAt: now,
		CreatedAt:      now,
		UpdatedAt:      now,
	}

	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		id, err := s.store.InsertGameAccount(txCtx, tx, ga)
		if err != nil {
			return err
		}
		ga.ID = id
		return nil
	})
	if err != nil {
		return nil, err
	}

	res := toGameAccountResult(*ga)
	return &res, nil
}

// UpdateGameAccount 更新游戏 ID 的段位信息。
func (s *Service) UpdateGameAccount(ctx *app.Ctx, in UpdateGameAccountInput) (*GameAccountResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	ga, err := s.store.GetGameAccountByID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if ga == nil || ga.UserID != ctx.Viewer.ID {
		return nil, api.NotFound("游戏 ID 不存在")
	}

	for field, score := range map[string]*int{"rank_tank": in.RankTank, "rank_damage": in.RankDamage, "rank_support": in.RankSupport} {
		if score != nil && (*score < 0 || *score > Top500Score) {
			return nil, api.InvalidFields(map[string][]string{field: {"非法段位分数"}})
		}
	}

	now := s.clock.Now().UTC()
	changed := (ga.RankTank != in.RankTank) || (ga.RankDamage != in.RankDamage) || (ga.RankSupport != in.RankSupport)
	if changed {
		ga.RanksUpdatedAt = now
	}
	ga.RankTank = in.RankTank
	ga.RankDamage = in.RankDamage
	ga.RankSupport = in.RankSupport
	ga.UpdatedAt = now

	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.UpdateGameAccount(txCtx, tx, ga)
	})
	if err != nil {
		return nil, err
	}

	res := toGameAccountResult(*ga)
	return &res, nil
}

// DeleteResult 通用删除出参。
type DeleteResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// DeleteGameAccount 删除绑定的游戏 ID。
func (s *Service) DeleteGameAccount(ctx *app.Ctx, id int64) (*DeleteResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	ga, err := s.store.GetGameAccountByID(ctx.Context, id)
	if err != nil {
		return nil, err
	}
	if ga == nil || ga.UserID != ctx.Viewer.ID {
		return nil, api.NotFound("游戏 ID 不存在")
	}

	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.DeleteGameAccount(txCtx, tx, id, ctx.Viewer.ID)
	})
	if err != nil {
		return nil, err
	}

	return &DeleteResult{
		Result:  "ok",
		Message: "游戏 ID 已删除。",
	}, nil
}

// -------------------------------------------------------------
// 联系方式 (Contact, 规则 18–19)
// -------------------------------------------------------------

// AddContactInput 添加联系方式入参。
type AddContactInput struct {
	Type  string `json:"type"`
	Value string `json:"value"`
}

// ContactResult 联系方式出参。
type ContactResult struct {
	ID        int64     `json:"id"`
	Type      string    `json:"type"`
	TypeLabel string    `json:"type_label"`
	Value     string    `json:"value"`
	CreatedAt time.Time `json:"created_at"`
}

func toContactResult(c Contact) ContactResult {
	label := AllContactTypes[c.Type]
	if label == "" {
		label = c.Type
	}
	return ContactResult{
		ID:        c.ID,
		Type:      c.Type,
		TypeLabel: label,
		Value:     c.Value,
		CreatedAt: c.CreatedAt,
	}
}

// AddContact 添加联系方式（每种类型限 1 条，规则 19）。
func (s *Service) AddContact(ctx *app.Ctx, in AddContactInput) (*ContactResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	cType := strings.TrimSpace(in.Type)
	if !IsValidContactType(cType) {
		return nil, api.InvalidFields(map[string][]string{"type": {"未知的联系方式类型。"}})
	}

	val := strings.TrimSpace(in.Value)
	if err := ValidateContact(cType, val); err != nil {
		return nil, api.InvalidFields(map[string][]string{"value": {err.Error()}})
	}

	existing, err := s.store.GetContactByUserAndType(ctx.Context, ctx.Viewer.ID, cType)
	if err != nil {
		return nil, err
	}
	if existing != nil {
		return nil, api.InvalidFields(map[string][]string{"type": {"每种联系方式只能填写一次。"}})
	}

	now := s.clock.Now().UTC()
	contact := &Contact{
		UserID:    ctx.Viewer.ID,
		Type:      cType,
		Value:     val,
		CreatedAt: now,
		UpdatedAt: now,
	}

	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		id, err := s.store.InsertContact(txCtx, tx, contact)
		if err != nil {
			return err
		}
		contact.ID = id
		return nil
	})
	if err != nil {
		return nil, err
	}

	res := toContactResult(*contact)
	return &res, nil
}

// DeleteContact 删除联系方式。
func (s *Service) DeleteContact(ctx *app.Ctx, id int64) (*DeleteResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	c, err := s.store.GetContactByID(ctx.Context, id)
	if err != nil {
		return nil, err
	}
	if c == nil || c.UserID != ctx.Viewer.ID {
		return nil, api.NotFound("联系方式不存在")
	}

	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.DeleteContact(txCtx, tx, id, ctx.Viewer.ID)
	})
	if err != nil {
		return nil, err
	}

	return &DeleteResult{
		Result:  "ok",
		Message: "联系方式已删除。",
	}, nil
}

// -------------------------------------------------------------
// 账号注销 (Account Deletion & Anonymization, 规则 28–32)
// -------------------------------------------------------------

// DeleteAccountInput 注销账号入参。
type DeleteAccountInput struct {
	Password string `json:"password"`
}

// DeleteAccountResult 注销账号出参。
type DeleteAccountResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

func (s *Service) isTeamCaptain(ctx context.Context, userID int64) (bool, error) {
	var n int
	err := s.d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM team_memberships m
		JOIN teams t ON t.id = m.team_id
		WHERE m.user_id = ? AND m.role = 'captain' AND t.disbanded_at IS NULL`, userID).Scan(&n)
	if err != nil {
		return false, err
	}
	return n > 0, nil
}

// DeleteAccount 原地匿名化注销账号（规则 28–32）。
func (s *Service) DeleteAccount(ctx *app.Ctx, in DeleteAccountInput) (*DeleteAccountResult, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}

	match, _, err := auth.Verify(ctx.Context, u.PasswordHash, in.Password)
	if err != nil || !match {
		return nil, api.InvalidFields(map[string][]string{"password": {"当前密码不正确。"}})
	}

	// 在任队长的用户不能注销（规则 29）
	isCaptain, err := s.isTeamCaptain(ctx.Context, u.ID)
	if err != nil {
		return nil, err
	}
	if isCaptain {
		return nil, api.Invalid("你仍担任未解散战队的队长，必须先转让队长或解散战队才能注销账号。")
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := s.store.AnonymizeUserTx(txCtx, tx, u.ID, now); err != nil {
			return err
		}
		if err := s.store.DeleteUserDataTx(txCtx, tx, u.ID); err != nil {
			return err
		}
		if err := s.store.LeaveTournamentsTx(txCtx, tx, u.ID, now); err != nil {
			return err
		}
		if err := s.store.LeaveTeamsAndGroupsTx(txCtx, tx, u.ID, now); err != nil {
			return err
		}
		if s.sessions != nil {
			return s.sessions.DeleteAllTx(txCtx, tx, u.ID)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}

	ctx.ClearSessionCookie()

	return &DeleteAccountResult{
		Result:  "ok",
		Message: "账号已注销。",
	}, nil
}

// -------------------------------------------------------------
// 导出个人信息 (Account Export, 规则 37–38)
// -------------------------------------------------------------

// AccountExportData 导出个人数据的 JSON 结构（规则 38）。
type AccountExportData struct {
	User         *User               `json:"user"`
	GameAccounts []GameAccountResult `json:"game_accounts"`
	Contacts     []ContactResult     `json:"contacts"`
	Roles        []string            `json:"roles"`
	// 战队和成员展示的自有数据（规则 38：战队、退役记录、入队申请、成员分组）。
	Teams            []ExportTeam        `json:"teams"`
	TeamApplications []ExportApplication `json:"team_applications"`
	TeamAlumni       []ExportAlumnus     `json:"team_alumni"`
	MemberGroups     []ExportGroup       `json:"member_groups"`
	ExportedAt       time.Time           `json:"exported_at"`
}

// ExportAccount 导出当前用户的完整自有数据。
func (s *Service) ExportAccount(ctx *app.Ctx) (*AccountExportData, error) {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}

	u, err := s.store.GetByID(ctx.Context, ctx.Viewer.ID)
	if err != nil {
		return nil, err
	}
	if u == nil || !u.IsActive {
		return nil, api.Unauthorized("账号不存在或已停用")
	}

	gas, err := s.store.GetGameAccountsByUserID(ctx.Context, u.ID)
	if err != nil {
		return nil, err
	}
	var gaResults []GameAccountResult
	for _, ga := range gas {
		gaResults = append(gaResults, toGameAccountResult(ga))
	}

	contacts, err := s.store.GetContactsByUserID(ctx.Context, u.ID)
	if err != nil {
		return nil, err
	}
	var contactResults []ContactResult
	for _, c := range contacts {
		contactResults = append(contactResults, toContactResult(c))
	}

	roles, err := s.store.GetUserRoles(ctx.Context, u.ID)
	if err != nil {
		return nil, err
	}

	out := &AccountExportData{
		User:         u,
		GameAccounts: gaResults,
		Contacts:     contactResults,
		Roles:        roles,
		ExportedAt:   s.clock.Now().UTC(),
	}
	if err := s.store.fillTeamExport(ctx.Context, u.ID, out); err != nil {
		return nil, err
	}
	return out, nil
}

// -------------------------------------------------------------
// 停用与启用 (Deactivation & Activation, 规则 33–36)
// -------------------------------------------------------------

// DeactivateUserInput 停用入参。
type DeactivateUserInput struct {
	ID     api.ID `path:"id"`
	Reason string `json:"reason"`
}

// DeactivateResult 停用出参。
type DeactivateResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// DeactivateUser 管理员停用用户（必填原因，规则 33–34）。
func (s *Service) DeactivateUser(ctx *app.Ctx, in DeactivateUserInput) (*DeactivateResult, error) {
	reason := strings.TrimSpace(in.Reason)
	if reason == "" {
		return nil, api.InvalidFields(map[string][]string{"reason": {"停用原因必填。"}})
	}
	if len(reason) > 200 {
		return nil, api.InvalidFields(map[string][]string{"reason": {"停用原因最多 200 字。"}})
	}

	u, err := s.store.GetByID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, api.NotFound("用户不存在")
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if err := s.store.DeactivateUserTx(txCtx, tx, int64(in.ID), reason, now); err != nil {
			return err
		}
		if err := s.store.SuspendTeamActivityTx(txCtx, tx, int64(in.ID), now); err != nil {
			return err
		}
		if s.sessions != nil {
			return s.sessions.DeleteAllTx(txCtx, tx, int64(in.ID))
		}
		return nil
	})
	if err != nil {
		return nil, err
	}

	return &DeactivateResult{
		Result:  "ok",
		Message: "账号已停用。",
	}, nil
}

// ReactivateUserInput 启用入参。
type ReactivateUserInput struct {
	ID api.ID `path:"id"`
}

// ReactivateResult 启用出参。
type ReactivateResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// ReactivateUser 管理员重新启用用户（注销账号不能启用，清空停用原因，规则 35–36）。
func (s *Service) ReactivateUser(ctx *app.Ctx, in ReactivateUserInput) (*ReactivateResult, error) {
	u, err := s.store.GetByID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, api.NotFound("用户不存在")
	}

	if strings.HasSuffix(u.Email, "@deleted.invalid") {
		return nil, api.Invalid("注销账号不能重新启用。")
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.ReactivateUserTx(txCtx, tx, int64(in.ID), now)
	})
	if err != nil {
		return nil, err
	}

	return &ReactivateResult{
		Result:  "ok",
		Message: "账号已重新启用。",
	}, nil
}

// -------------------------------------------------------------
// 后台用户管理 (Admin User Management, 规则 39–42)
// -------------------------------------------------------------

// ListUsersInput 后台查询用户列表入参。
type ListUsersInput struct {
	Page     int    `query:"page"`
	PageSize int    `query:"page_size"`
	Search   string `query:"search"`
}

// AdminUserSummary 用户概要出参。
type AdminUserSummary struct {
	ID               int64     `json:"id"`
	Email            string    `json:"email"`
	Nickname         string    `json:"nickname"`
	IsSJTU           bool      `json:"is_sjtu"`
	IsActive         bool      `json:"is_active"`
	IsSuperuser      bool      `json:"is_superuser"`
	EmailVerified    bool      `json:"email_verified"`
	DeactivationNote string    `json:"deactivation_note"`
	CreatedAt        time.Time `json:"created_at"`
}

// ListUsersResult 用户列表出参。
type ListUsersResult struct {
	Total int                `json:"total"`
	Users []AdminUserSummary `json:"users"`
}

// ListUsers 后台分页列出用户（只有超管能搜邮箱和看邮箱，规则 39）。
func (s *Service) ListUsers(ctx *app.Ctx, in ListUsersInput) (*ListUsersResult, error) {
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}
	offset := (page - 1) * pageSize

	isSuperuser := ctx.Viewer != nil && ctx.Viewer.Superuser
	total, err := s.store.CountUsers(ctx.Context, in.Search, isSuperuser)
	if err != nil {
		return nil, err
	}

	users, err := s.store.ListUsers(ctx.Context, pageSize, offset, in.Search, isSuperuser)
	if err != nil {
		return nil, err
	}

	var summaries []AdminUserSummary
	for _, u := range users {
		email := u.Email
		if !isSuperuser {
			email = "" // 非超管隐藏邮箱（规则 39）
		}
		summaries = append(summaries, AdminUserSummary{
			ID:               u.ID,
			Email:            email,
			Nickname:         u.Nickname,
			IsSJTU:           u.IsSJTU,
			IsActive:         u.IsActive,
			IsSuperuser:      u.IsSuperuser,
			EmailVerified:    u.EmailVerified(),
			DeactivationNote: u.DeactivationNote,
			CreatedAt:        u.CreatedAt,
		})
	}

	return &ListUsersResult{
		Total: total,
		Users: summaries,
	}, nil
}

// UserDetailInput 用户详情入参。
type UserDetailInput struct {
	ID api.ID `path:"id"`
}

// UserDetailResult 用户详情出参。
type UserDetailResult struct {
	User         *User               `json:"user"`
	Roles        []string            `json:"roles"`
	Rules        map[string]bool     `json:"rules"`
	GameAccounts []GameAccountResult `json:"game_accounts"`
	Contacts     []ContactResult     `json:"contacts"`
}

// GetUserDetail 后台查看单个用户完整详情。
func (s *Service) GetUserDetail(ctx *app.Ctx, in UserDetailInput) (*UserDetailResult, error) {
	u, err := s.store.GetByID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, api.NotFound("用户不存在")
	}

	roles, err := s.store.GetUserRoles(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}

	rulesMap, err := s.store.GetFeatureUserRules(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	rulesStr := make(map[string]bool)
	for f, allowed := range rulesMap {
		rulesStr[string(f)] = allowed
	}

	gas, err := s.store.GetGameAccountsByUserID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	var gaResults []GameAccountResult
	for _, ga := range gas {
		gaResults = append(gaResults, toGameAccountResult(ga))
	}

	var contactResults []ContactResult
	// 联系方式只对超管或有 contacts.view 权限者显示（规则 40）
	canViewContacts := ctx.Viewer != nil && (ctx.Viewer.Superuser || ctx.Viewer.HasCap(CapContactsView))
	if canViewContacts {
		contacts, err := s.store.GetContactsByUserID(ctx.Context, int64(in.ID))
		if err != nil {
			return nil, err
		}
		for _, c := range contacts {
			contactResults = append(contactResults, toContactResult(c))
		}
	}

	if ctx.Viewer != nil && !ctx.Viewer.Superuser {
		u.Email = ""
		u.EmailNorm = ""
	}

	return &UserDetailResult{
		User:         u,
		Roles:        roles,
		Rules:        rulesStr,
		GameAccounts: gaResults,
		Contacts:     contactResults,
	}, nil
}

// UpdateUserRolesInput 更新用户角色入参。
type UpdateUserRolesInput struct {
	ID    api.ID   `path:"id"`
	Roles []string `json:"roles"`
}

// UpdateUserRolesResult 更新用户角色出参。
type UpdateUserRolesResult struct {
	Result  string   `json:"result"`
	Roles   []string `json:"roles"`
	Message string   `json:"message"`
}

// UpdateUserRoles 更新用户的管理角色（仅限 4 个存库角色）。
func (s *Service) UpdateUserRoles(ctx *app.Ctx, in UpdateUserRolesInput) (*UpdateUserRolesResult, error) {
	for _, r := range in.Roles {
		valid := false
		for _, sr := range AllStoredRoles {
			if r == sr {
				valid = true
				break
			}
		}
		if !valid {
			return nil, api.Invalid("未知或非存库角色: " + r)
		}
	}

	u, err := s.store.GetByID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, api.NotFound("用户不存在")
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.SetUserRolesTx(txCtx, tx, int64(in.ID), in.Roles, now)
	})
	if err != nil {
		return nil, err
	}

	return &UpdateUserRolesResult{
		Result:  "ok",
		Roles:   in.Roles,
		Message: "角色已更新。",
	}, nil
}

// UpdateUserRulesInput 更新用户规则入参。
type UpdateUserRulesInput struct {
	ID    api.ID          `path:"id"`
	Rules map[string]bool `json:"rules"`
}

// UpdateUserRulesResult 更新用户规则出参。
type UpdateUserRulesResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// UpdateUserRules 更新用户的单人功能规则。
func (s *Service) UpdateUserRules(ctx *app.Ctx, in UpdateUserRulesInput) (*UpdateUserRulesResult, error) {
	rules := make(map[app.Feature]bool)
	for fStr, allowed := range in.Rules {
		feat := app.Feature(fStr)
		if !IsValidFeature(feat) {
			return nil, api.Invalid("未知的功能标识: " + fStr)
		}
		rules[feat] = allowed
	}

	u, err := s.store.GetByID(ctx.Context, int64(in.ID))
	if err != nil {
		return nil, err
	}
	if u == nil {
		return nil, api.NotFound("用户不存在")
	}

	now := s.clock.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.SetUserRulesTx(txCtx, tx, int64(in.ID), rules, now)
	})
	if err != nil {
		return nil, err
	}

	return &UpdateUserRulesResult{
		Result:  "ok",
		Message: "规则已更新。",
	}, nil
}

// RoleRestrictionItem 单条角色功能限制。
type RoleRestrictionItem struct {
	Role    string `json:"role"`
	Feature string `json:"feature"`
}

// FeatureRoleRestrictionsResult 角色限制出参。
type FeatureRoleRestrictionsResult struct {
	Restrictions []RoleRestrictionItem `json:"restrictions"`
}

// GetFeatureRoleRestrictions 读全站所有角色功能限制。
func (s *Service) GetFeatureRoleRestrictions(ctx *app.Ctx) (*FeatureRoleRestrictionsResult, error) {
	restrs, err := s.store.GetFeatureRoleRestrictions(ctx.Context)
	if err != nil {
		return nil, err
	}

	var list []RoleRestrictionItem
	for role, feats := range restrs {
		for feat, restricted := range feats {
			if restricted {
				list = append(list, RoleRestrictionItem{Role: role, Feature: string(feat)})
			}
		}
	}

	return &FeatureRoleRestrictionsResult{
		Restrictions: list,
	}, nil
}

// SetFeatureRoleRestrictionsInput 更新角色限制入参。
type SetFeatureRoleRestrictionsInput struct {
	Restrictions []RoleRestrictionItem `json:"restrictions"`
}

// SetFeatureRoleRestrictionsResult 更新角色限制出参。
type SetFeatureRoleRestrictionsResult struct {
	Result  string `json:"result"`
	Message string `json:"message"`
}

// SetFeatureRoleRestrictions 全量替换全站角色限制。
func (s *Service) SetFeatureRoleRestrictions(ctx *app.Ctx, in SetFeatureRoleRestrictionsInput) (*SetFeatureRoleRestrictionsResult, error) {
	restrs := make(map[string]map[app.Feature]bool)
	for _, item := range in.Restrictions {
		feat := app.Feature(item.Feature)
		if !IsValidFeature(feat) {
			return nil, api.Invalid("未知的功能标识: " + item.Feature)
		}
		if restrs[item.Role] == nil {
			restrs[item.Role] = make(map[app.Feature]bool)
		}
		restrs[item.Role][feat] = true
	}

	now := s.clock.Now().UTC()
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.ReplaceRoleRestrictionsTx(txCtx, tx, restrs, now)
	})
	if err != nil {
		return nil, err
	}

	return &SetFeatureRoleRestrictionsResult{
		Result:  "ok",
		Message: "角色限制已更新。",
	}, nil
}

// VerifyUserEmailDirectly 服务端直接将用户邮箱标记为已验证（命令用，规则 15）。
func (s *Service) VerifyUserEmailDirectly(ctx context.Context, email string) error {
	norm := NormalizeEmail(email)
	u, err := s.store.GetByEmailNorm(ctx, norm)
	if err != nil {
		return err
	}
	if u == nil {
		return fmt.Errorf("用户 %s 不存在", email)
	}
	now := s.clock.Now().UTC()
	return s.d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		return s.store.MarkEmailVerified(txCtx, tx, u.ID, now)
	})
}
