package accounts

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
	"golang.org/x/crypto/pbkdf2"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestStoreAndBuildViewer(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()

	// 1. 未登录 (userID <= 0)
	v, err := svc.BuildViewer(ctx, 0)
	if err != nil || v != nil {
		t.Fatalf("未登录应为 nil: v=%v, err=%v", v, err)
	}

	// 2. 插入测试用户
	now := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	verified := now
	u := &User{
		Email:               "player@sjtu.edu.cn",
		EmailNorm:           "player@sjtu.edu.cn",
		PasswordHash:        "argon2$...",
		Nickname:            "交大选手",
		IsSJTU:              true,
		AgreedTermsAt:       now,
		AgreedCrossBorderAt: now,
		EmailVerifiedAt:     &verified,
		Version:             1,
		IsActive:            true,
		IsSuperuser:         false,
		CreatedAt:           now,
		UpdatedAt:           now,
	}

	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := store.InsertUser(ctx, tx, u)
		return err
	})
	if err != nil {
		t.Fatalf("InsertUser: %v", err)
	}
	if u.ID <= 0 {
		t.Fatalf("用户 ID 应 > 0: %d", u.ID)
	}

	// 3. 读取用户
	byID, err := store.GetByID(ctx, u.ID)
	if err != nil || byID == nil || byID.Nickname != "交大选手" {
		t.Fatalf("GetByID 失败: %+v, err=%v", byID, err)
	}
	byEmail, err := store.GetByEmailNorm(ctx, "player@sjtu.edu.cn")
	if err != nil || byEmail == nil || byEmail.ID != u.ID {
		t.Fatalf("GetByEmailNorm 失败: %+v, err=%v", byEmail, err)
	}

	// 4. 普通交大已验证用户生成 Viewer：自动获得 RoleSJTU + RoleContributor
	v, err = svc.BuildViewer(ctx, u.ID)
	if err != nil || v == nil {
		t.Fatalf("BuildViewer: %v", err)
	}
	if v.Disabled || !v.EmailVerified || v.Superuser {
		t.Fatalf("Viewer 标志错误: %+v", v)
	}
	// 投稿者拥有 CapAdminEnter, CapArticlesPublishOwn, CapImagesContribute
	if !v.HasCap(CapAdminEnter) || !v.HasCap(CapArticlesPublishOwn) || !v.HasCap(CapImagesContribute) {
		t.Fatalf("投稿者应拥有投稿和进后台能力: %+v", v.Caps)
	}
	if v.HasCap(CapTournamentsManage) {
		t.Fatalf("普通用户不应拥有赛事管理能力")
	}

	// 5. 授予管理角色 RoleTournamentAdmin
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		return store.AssignRole(ctx, tx, u.ID, RoleTournamentAdmin, now)
	})
	if err != nil {
		t.Fatalf("AssignRole: %v", err)
	}
	v, err = svc.BuildViewer(ctx, u.ID)
	if err != nil || v == nil {
		t.Fatalf("BuildViewer: %v", err)
	}
	if !v.HasCap(CapTournamentsManage) || !v.HasCap(CapContactsView) {
		t.Fatalf("应拥有赛事管理与查看联系方式能力")
	}

	// 6. 单用户功能规则：禁用评论
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		return store.SetFeatureUserRule(ctx, tx, u.ID, FeatureArticleComment, true, now)
	})
	if err != nil {
		t.Fatalf("SetFeatureUserRule: %v", err)
	}
	v, err = svc.BuildViewer(ctx, u.ID)
	if err != nil || v == nil {
		t.Fatalf("BuildViewer: %v", err)
	}
	if v.CanUse(FeatureArticleComment) {
		t.Fatalf("评论被单人规则禁用后 CanUse 应为 false")
	}
	if !v.CanUse(FeatureAvatarUpload) {
		t.Fatalf("未受限功能默认应可用")
	}

	// 7. 停用账号
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, "UPDATE users SET is_active = 0 WHERE id = ?", u.ID)
		return err
	})
	if err != nil {
		t.Fatalf("停用更新失败: %v", err)
	}
	v, err = svc.BuildViewer(ctx, u.ID)
	if err != nil || v == nil || !v.Disabled {
		t.Fatalf("停用账号生成的 Viewer 应处于 Disabled 状态: %+v", v)
	}
}

func TestRegisterSuccess(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()

	isSJTU := true
	res, err := svc.Register(ctx, RegisterInput{
		Email:            "alice@sjtu.edu.cn",
		Nickname:         "爱丽丝",
		Password:         "Password123!@#",
		ConfirmPassword:  "Password123!@#",
		IsSJTU:           &isSJTU,
		AgreeTerms:       true,
		AgreeCrossBorder: true,
	})
	if err != nil {
		t.Fatalf("Register error: %v", err)
	}
	if res.Email != "alice@sjtu.edu.cn" {
		t.Fatalf("res.Email=%q, want alice@sjtu.edu.cn", res.Email)
	}
	if !strings.Contains(res.Message, "验证码") {
		t.Fatalf("res.Message 不含验证码提示: %q", res.Message)
	}

	// 验证 users 表
	u, err := store.GetByEmailNorm(ctx, "alice@sjtu.edu.cn")
	if err != nil || u == nil {
		t.Fatalf("GetByEmailNorm: u=%v, err=%v", u, err)
	}
	if u.Nickname != "爱丽丝" || !u.IsSJTU || !u.IsActive || u.IsSuperuser || u.EmailVerified() {
		t.Fatalf("用户字段不符合初始状态: %+v", u)
	}
	ok, _, err := auth.Verify(ctx, u.PasswordHash, "Password123!@#")
	if err != nil || !ok {
		t.Fatalf("密码哈希校验失败: ok=%v, err=%v", ok, err)
	}

	// 验证 email_codes 表
	codeRecord, err := store.GetLatestEmailCode(ctx, "signup", "alice@sjtu.edu.cn")
	if err != nil || codeRecord == nil {
		t.Fatalf("GetLatestEmailCode: code=%v, err=%v", codeRecord, err)
	}
	if codeRecord.Attempts != 0 {
		t.Fatalf("attempts=%d, want 0", codeRecord.Attempts)
	}
	if codeRecord.ExpiresAt.Sub(codeRecord.CreatedAt) != 15*time.Minute {
		t.Fatalf("有效期应为 15 分钟: %v", codeRecord.ExpiresAt.Sub(codeRecord.CreatedAt))
	}

	// 验证 jobs 表入队邮件
	var jobKind, jobLane, jobArgs string
	err = d.ReadPool().QueryRowContext(ctx, "SELECT kind, lane, args FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&jobKind, &jobLane, &jobArgs)
	if err != nil {
		t.Fatalf("邮件任务未写入 jobs 表: %v", err)
	}
	if jobLane != "mail" {
		t.Fatalf("jobLane=%q, want mail", jobLane)
	}
	if !strings.Contains(jobArgs, "邮箱验证码") || !strings.Contains(jobArgs, "alice@sjtu.edu.cn") {
		t.Fatalf("jobArgs 邮件内容不符: %s", jobArgs)
	}
}

func TestRegisterFieldValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	isSJTU := true
	validInput := RegisterInput{
		Email:            "valid@sjtu.edu.cn",
		Nickname:         "有效昵称",
		Password:         "StrongPassword123!",
		ConfirmPassword:  "StrongPassword123!",
		IsSJTU:           &isSJTU,
		AgreeTerms:       true,
		AgreeCrossBorder: true,
	}

	tests := []struct {
		name      string
		modify    func(in *RegisterInput)
		wantField string
	}{
		{
			name:      "邮箱为空",
			modify:    func(in *RegisterInput) { in.Email = "" },
			wantField: "email",
		},
		{
			name:      "邮箱格式非法",
			modify:    func(in *RegisterInput) { in.Email = "invalid-email" },
			wantField: "email",
		},
		{
			name:      "昵称太短",
			modify:    func(in *RegisterInput) { in.Nickname = "A" },
			wantField: "nickname",
		},
		{
			name:      "昵称太长",
			modify:    func(in *RegisterInput) { in.Nickname = "一二三四五六七八九十一二三四五六七" },
			wantField: "nickname",
		},
		{
			name:      "密码为空",
			modify:    func(in *RegisterInput) { in.Password = ""; in.ConfirmPassword = "" },
			wantField: "password",
		},
		{
			name:      "密码太短",
			modify:    func(in *RegisterInput) { in.Password = "short"; in.ConfirmPassword = "short" },
			wantField: "password",
		},
		{
			name:      "密码完全是数字",
			modify:    func(in *RegisterInput) { in.Password = "12345678"; in.ConfirmPassword = "12345678" },
			wantField: "password",
		},
		{
			name:      "两次密码不一致",
			modify:    func(in *RegisterInput) { in.ConfirmPassword = "DifferentPassword123!" },
			wantField: "confirm_password",
		},
		{
			name:      "未选交大",
			modify:    func(in *RegisterInput) { in.IsSJTU = nil },
			wantField: "is_sjtu",
		},
		{
			name:      "未同意用户协议",
			modify:    func(in *RegisterInput) { in.AgreeTerms = false },
			wantField: "agree_terms",
		},
		{
			name:      "未同意跨境传输",
			modify:    func(in *RegisterInput) { in.AgreeCrossBorder = false },
			wantField: "agree_cross_border",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			input := validInput
			tc.modify(&input)
			_, err := svc.Register(ctx, input)
			if err == nil {
				t.Fatalf("应校验失败但成功了")
			}
			var apiErr *api.Error
			if !errors.As(err, &apiErr) {
				t.Fatalf("错误应为 *api.Error: %v", err)
			}
			if apiErr.Status != 422 {
				t.Fatalf("状态码应为 422，得到 %d", apiErr.Status)
			}
			if len(apiErr.Fields[tc.wantField]) == 0 {
				t.Fatalf("fields[%q] 应有错误信息，得到: %+v", tc.wantField, apiErr.Fields)
			}
		})
	}
}

// 契约 R004、R005、R008：防账号枚举同形响应、注册限流与注册资料补充
func TestRegisterAntiEnumeration(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()

	isSJTU := false
	// 1. 首次注册成功
	res1, err := svc.Register(ctx, RegisterInput{
		Email:            "bob@example.com",
		Nickname:         "鲍勃首发",
		Password:         "FirstPass123!@#",
		ConfirmPassword:  "FirstPass123!@#",
		IsSJTU:           &isSJTU,
		AgreeTerms:       true,
		AgreeCrossBorder: true,
	})
	if err != nil {
		t.Fatalf("首次注册失败: %v", err)
	}
	if res1.Email != "bob@example.com" {
		t.Fatalf("res1.Email=%q", res1.Email)
	}

	var userCountBefore int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM users").Scan(&userCountBefore); err != nil {
		t.Fatal(err)
	}
	if userCountBefore != 1 {
		t.Fatalf("用户数应为 1，得到 %d", userCountBefore)
	}

	// 2. 再次用相同邮箱（大小写混写 Bob@Example.COM）注册
	isSJTU2 := true
	res2, err := svc.Register(ctx, RegisterInput{
		Email:            "Bob@Example.COM",
		Nickname:         "冒牌鲍勃",
		Password:         "SecondPass456!@#",
		ConfirmPassword:  "SecondPass456!@#",
		IsSJTU:           &isSJTU2,
		AgreeTerms:       true,
		AgreeCrossBorder: true,
	})
	if err != nil {
		t.Fatalf("防枚举应返回 nil 错误，实际报错: %v", err)
	}
	// 出参与首次相同（防枚举）
	if !strings.Contains(res2.Message, "验证码") {
		t.Fatalf("防枚举出参 message 应与正常一致: %q", res2.Message)
	}

	// 用户总数未变
	var userCountAfter int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM users").Scan(&userCountAfter); err != nil {
		t.Fatal(err)
	}
	if userCountAfter != 1 {
		t.Fatalf("防枚举下不得新建用户，用户数应为 1，得到 %d", userCountAfter)
	}

	// 原始用户信息未被篡改
	origUser, err := store.GetByEmailNorm(ctx, "bob@example.com")
	if err != nil || origUser == nil {
		t.Fatal(err)
	}
	if origUser.Nickname != "鲍勃首发" {
		t.Fatalf("昵称被篡改: %s", origUser.Nickname)
	}

	// 检查 jobs 表入队了两封邮件：第一封是验证码，第二封是已注册提醒信
	rows, err := d.ReadPool().QueryContext(ctx, "SELECT args FROM jobs WHERE kind = ? ORDER BY id ASC", outbox.KindLetter)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()

	var argsList []string
	for rows.Next() {
		var a string
		if err := rows.Scan(&a); err != nil {
			t.Fatal(err)
		}
		argsList = append(argsList, a)
	}
	if len(argsList) != 2 {
		t.Fatalf("应入队 2 封邮件，得到 %d", len(argsList))
	}
	if !strings.Contains(argsList[0], "邮箱验证码") {
		t.Fatalf("第一封邮件应为邮箱验证码: %s", argsList[0])
	}
	if !strings.Contains(argsList[1], "这个邮箱已经注册过") || !strings.Contains(argsList[1], "找回密码") {
		t.Fatalf("第二封邮件应为已注册提醒: %s", argsList[1])
	}
}

// fixedCode 把验证码生成换成固定值（明文 + SHA-256 哈希），测试用。
func fixedCode(code string) func() (string, string, error) {
	return func() (string, string, error) {
		sum := sha256.Sum256([]byte(code))
		return code, hex.EncodeToString(sum[:]), nil
	}
}

func mustRegister(t *testing.T, svc *Service, email, nickname, password string) {
	t.Helper()
	isSJTU := true
	_, err := svc.Register(context.Background(), RegisterInput{
		Email:            email,
		Nickname:         nickname,
		Password:         password,
		ConfirmPassword:  password,
		IsSJTU:           &isSJTU,
		AgreeTerms:       true,
		AgreeCrossBorder: true,
	})
	if err != nil {
		t.Fatalf("注册 %s 失败: %v", email, err)
	}
}

func errString(err error) string {
	if err == nil {
		return "<nil>"
	}
	return err.Error()
}

func TestVerifyEmailSuccess(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()
	svc.codeGen = fixedCode("123456")

	mustRegister(t, svc, "verify@sjtu.edu.cn", "验证者", "Password123!@#")

	res, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "Verify@SJTU.edu.cn", Code: "123456"})
	if err != nil {
		t.Fatalf("核验失败: %v", err)
	}
	if res.Token == "" || !strings.Contains(res.Message, "游戏 ID") {
		t.Fatalf("出参不符: %+v", res)
	}

	// email_verified_at 已置、signup 码已删光
	u, err := store.GetByEmailNorm(ctx, "verify@sjtu.edu.cn")
	if err != nil || u == nil {
		t.Fatal(err)
	}
	if !u.EmailVerified() {
		t.Fatalf("邮箱应已验证: %+v", u)
	}
	c, err := store.GetLatestEmailCode(ctx, "signup", "verify@sjtu.edu.cn")
	if err != nil || c != nil {
		t.Fatalf("验证码应已删光: %+v, err=%v", c, err)
	}

	// 令牌能解出这个用户的会话
	sess := auth.NewStore(d, nil)
	s, err := sess.Lookup(ctx, res.Token)
	if err != nil || s == nil {
		t.Fatalf("会话应能查到: %+v, err=%v", s, err)
	}
	if s.UserID != u.ID {
		t.Fatalf("会话应属于用户 %d，得到 %d", u.ID, s.UserID)
	}
}

func TestVerifyEmailAttempts(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()
	svc.codeGen = fixedCode("123456")

	mustRegister(t, svc, "attempts@sjtu.edu.cn", "尝试者", "Password123!@#")

	// 前两次错码：同一句报错、attempts 递增
	for i := 1; i <= 2; i++ {
		_, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "attempts@sjtu.edu.cn", Code: "000000"})
		if err == nil || errString(err) != errString(errBadCode) {
			t.Fatalf("第 %d 次错码应报统一错误，得到: %v", i, err)
		}
		c, _ := store.GetLatestEmailCode(ctx, "signup", "attempts@sjtu.edu.cn")
		if c == nil || c.Attempts != i {
			t.Fatalf("attempts 应为 %d: %+v", i, c)
		}
	}

	// 第 3 次错：码作废删除
	_, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "attempts@sjtu.edu.cn", Code: "000000"})
	if err == nil || errString(err) != errString(errBadCode) {
		t.Fatalf("第 3 次错码应报统一错误，得到: %v", err)
	}
	c, _ := store.GetLatestEmailCode(ctx, "signup", "attempts@sjtu.edu.cn")
	if c != nil {
		t.Fatalf("3 次用尽后码应被删: %+v", c)
	}

	// 码作废后即使输入对的码也不行
	_, err = svc.VerifyEmail(ctx, VerifyEmailInput{Email: "attempts@sjtu.edu.cn", Code: "123456"})
	if err == nil || errString(err) != errString(errBadCode) {
		t.Fatalf("码作废后对的码也应报统一错误，得到: %v", err)
	}
	// 用户仍是未验证
	u, _ := store.GetByEmailNorm(ctx, "attempts@sjtu.edu.cn")
	if u.EmailVerified() {
		t.Fatalf("不该被标记为已验证")
	}
}

func TestVerifyEmailExpired(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	mustRegister(t, svc, "expired@sjtu.edu.cn", "过期者", "Password123!@#")

	// 把码的过期时间改到过去
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `UPDATE email_codes SET expires_at = '2020-01-01T00:00:00.000000Z'`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = svc.VerifyEmail(ctx, VerifyEmailInput{Email: "expired@sjtu.edu.cn", Code: "123456"})
	if err == nil || errString(err) != errString(errBadCode) {
		t.Fatalf("过期码应报统一错误，得到: %v", err)
	}
}

func TestVerifyEmailUnknownEmailSameError(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	mustRegister(t, svc, "known@sjtu.edu.cn", "已有者", "Password123!@#")

	// 邮箱没注册过：报错必须和「码不正确」一字不差（R004 防枚举）
	_, errUnknown := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "ghost@sjtu.edu.cn", Code: "123456"})
	_, errWrong := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "known@sjtu.edu.cn", Code: "999999"})
	if errString(errUnknown) != errString(errWrong) {
		t.Fatalf("未知邮箱与错码的报错不一致（防枚举被破）: %q vs %q", errString(errUnknown), errString(errWrong))
	}
}

func TestVerifyEmailFieldValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	for _, tc := range []struct {
		name       string
		email      string
		code       string
		wantFields []string
	}{
		{"邮箱空", "", "123456", []string{"email"}},
		{"邮箱非法", "not-an-email", "123456", []string{"email"}},
		{"码空", "a@sjtu.edu.cn", "", []string{"code"}},
	} {
		_, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: tc.email, Code: tc.code})
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 422 {
			t.Fatalf("%s: 应 422，得到 %v", tc.name, err)
		}
		for _, f := range tc.wantFields {
			if len(apiErr.Fields[f]) == 0 {
				t.Fatalf("%s: fields[%s] 应有错误", tc.name, f)
			}
		}
	}
}

// newVerifiedUser 造一个已验证、密码正确的用户，返回该用户。
func newVerifiedUser(t *testing.T, d *db.DB, email, nickname, password string, active bool) *User {
	t.Helper()
	ctx := context.Background()
	store := NewStore(d)
	now := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	hash, err := auth.Hash(ctx, password)
	if err != nil {
		t.Fatal(err)
	}
	u := &User{
		Email:               email,
		EmailNorm:           strings.ToLower(email),
		PasswordHash:        hash,
		Nickname:            nickname,
		IsSJTU:              true,
		AgreedTermsAt:       now,
		AgreedCrossBorderAt: now,
		EmailVerifiedAt:     &now,
		Version:             1,
		IsActive:            active,
		CreatedAt:           now,
		UpdatedAt:           now,
	}
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := store.InsertUser(ctx, tx, u)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	return u
}

func TestLoginSuccess(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	u := newVerifiedUser(t, d, "login@sjtu.edu.cn", "登录者", "Password123!@#", true)

	res, err := svc.Login(ctx, LoginInput{Email: "LOGIN@SJTU.edu.cn", Password: "Password123!@#"})
	if err != nil {
		t.Fatalf("登录失败: %v", err)
	}
	if res.Result != "ok" || res.Token == "" {
		t.Fatalf("出参不符: %+v", res)
	}
	sess := auth.NewStore(d, nil)
	s, err := sess.Lookup(ctx, res.Token)
	if err != nil || s == nil || s.UserID != u.ID {
		t.Fatalf("会话应属于用户 %d: %+v, err=%v", u.ID, s, err)
	}
}

func TestLoginWrongPasswordUnified(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	newVerifiedUser(t, d, "real@sjtu.edu.cn", "真人", "Password123!@#", true)

	// 密码错和邮箱不存在：同一个错误（R004）
	_, errWrong := svc.Login(ctx, LoginInput{Email: "real@sjtu.edu.cn", Password: "WrongPassword!@#"})
	_, errGhost := svc.Login(ctx, LoginInput{Email: "ghost@sjtu.edu.cn", Password: "WrongPassword!@#"})
	if errWrong == nil || errGhost == nil {
		t.Fatalf("都该 401: %v / %v", errWrong, errGhost)
	}
	if errString(errWrong) != errString(errGhost) {
		t.Fatalf("错误文案不一致（防枚举被破）: %q vs %q", errString(errWrong), errString(errGhost))
	}
	var apiErr *api.Error
	if !errors.As(errWrong, &apiErr) || apiErr.Status != 401 {
		t.Fatalf("应为 401: %v", errWrong)
	}
	if apiErr.Message != "邮箱或密码不正确" {
		t.Fatalf("文案应为统一句: %q", apiErr.Message)
	}
}

func TestLoginFailedRateLimitPerAccount(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	enforcer := ratelimit.NewEnforcer(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, enforcer)

	newVerifiedUser(t, d, "brute@sjtu.edu.cn", "被爆破", "Password123!@#", true)

	// 5 次失败都返回 401（R006：5 次/300 秒/账号）
	for i := 1; i <= 5; i++ {
		_, err := svc.Login(ctx, LoginInput{Email: "brute@sjtu.edu.cn", Password: "Nope12345!@#"})
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 401 {
			t.Fatalf("第 %d 次失败应 401，得到 %v", i, err)
		}
	}
	// 第 6 次：429 + Retry-After
	_, err := svc.Login(ctx, LoginInput{Email: "brute@sjtu.edu.cn", Password: "Nope12345!@#"})
	var apiErr *api.Error
	if !errors.As(err, &apiErr) {
		t.Fatalf("应返回 *api.Error: %v", err)
	}
	if apiErr.Status != 429 {
		t.Fatalf("第 6 次失败应 429，得到 %d", apiErr.Status)
	}
	if apiErr.Header.Get("Retry-After") == "" {
		t.Fatalf("429 应带 Retry-After")
	}
	// 即使密码正确也先被 429 挡住（防线在前）
	_, err = svc.Login(ctx, LoginInput{Email: "brute@sjtu.edu.cn", Password: "Password123!@#"})
	if !errors.As(err, &apiErr) || apiErr.Status != 429 {
		t.Fatalf("锁定期内正确密码也应 429，得到 %v", err)
	}
}

func TestLoginDisabled(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	newVerifiedUser(t, d, "gone@sjtu.edu.cn", "停用者", "Password123!@#", false)

	_, err := svc.Login(ctx, LoginInput{Email: "gone@sjtu.edu.cn", Password: "Password123!@#"})
	var apiErr *api.Error
	if !errors.As(err, &apiErr) || apiErr.Status != 403 {
		t.Fatalf("停用账号应 403，得到 %v", err)
	}
	if apiErr.Code != "account_disabled" {
		t.Fatalf("code 应为 account_disabled: %q", apiErr.Code)
	}
	// 停用账号不发会话
	var n int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM sessions").Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 0 {
		t.Fatalf("停用账号不应有会话，得到 %d 条", n)
	}
}

func TestLoginUnverifiedResendsCode(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()
	svc.codeGen = fixedCode("654321")

	mustRegister(t, svc, "fresh@sjtu.edu.cn", "新人", "Password123!@#")

	res, err := svc.Login(ctx, LoginInput{Email: "fresh@sjtu.edu.cn", Password: "Password123!@#"})
	if err != nil {
		t.Fatalf("登录未验证账号不应报错: %v", err)
	}
	if res.Result != "verify_required" || res.Token != "" {
		t.Fatalf("出参不符: %+v", res)
	}

	// 新验证码已落库（15 分钟有效、尝试次数清零）
	c, err := store.GetLatestEmailCode(ctx, "signup", "fresh@sjtu.edu.cn")
	if err != nil || c == nil {
		t.Fatalf("应重发验证码: %+v, err=%v", c, err)
	}
	if c.Attempts != 0 || c.ExpiresAt.Sub(c.CreatedAt) != 15*time.Minute {
		t.Fatalf("新码应为全新一条: %+v", c)
	}

	// 没有会话
	var n int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM sessions").Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 0 {
		t.Fatalf("未验证登录不应建会话，得到 %d 条", n)
	}

	// 两封信入队：注册的验证码 + 登录时重发的验证码
	var letters int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&letters); err != nil {
		t.Fatal(err)
	}
	if letters != 2 {
		t.Fatalf("应入队 2 封信，得到 %d", letters)
	}

	// 用重发的码能完成验证并拿到会话
	vres, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "fresh@sjtu.edu.cn", Code: "654321"})
	if err != nil || vres.Token == "" {
		t.Fatalf("重发的码应能验证: %+v, err=%v", vres, err)
	}
}

func TestLoginPBKDF2Upgrade(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := NewStore(d)

	// 造一个 Django PBKDF2 哈希的存量用户
	salt := "oldsalt"
	key := pbkdf2.Key([]byte("LegacyPass123!@#"), []byte(salt), 600000, 32, sha256.New)
	legacy := fmt.Sprintf("pbkdf2_sha256$600000$%s$%s", salt, base64.StdEncoding.EncodeToString(key))

	now := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	u := &User{
		Email:               "legacy@sjtu.edu.cn",
		EmailNorm:           "legacy@sjtu.edu.cn",
		PasswordHash:        legacy,
		Nickname:            "老用户",
		IsSJTU:              true,
		AgreedTermsAt:       now,
		AgreedCrossBorderAt: now,
		EmailVerifiedAt:     &now,
		Version:             1,
		IsActive:            true,
		CreatedAt:           now,
		UpdatedAt:           now,
	}
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := store.InsertUser(ctx, tx, u)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}

	res, err := svc.Login(ctx, LoginInput{Email: "legacy@sjtu.edu.cn", Password: "LegacyPass123!@#"})
	if err != nil || res.Result != "ok" {
		t.Fatalf("PBKDF2 登录应成功: %+v, err=%v", res, err)
	}

	got, _ := store.GetByEmailNorm(ctx, "legacy@sjtu.edu.cn")
	if !strings.HasPrefix(got.PasswordHash, "argon2$") {
		t.Fatalf("哈希应升级为 Argon2: %s", got.PasswordHash)
	}
	// 升级后的哈希验得过
	ok, upgrade, err := auth.Verify(ctx, got.PasswordHash, "LegacyPass123!@#")
	if err != nil || !ok || upgrade {
		t.Fatalf("新哈希应验过且无需再升级: ok=%v upgrade=%v err=%v", ok, upgrade, err)
	}
}

func TestLoginFieldValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	for _, tc := range []struct {
		name       string
		email      string
		password   string
		wantFields []string
	}{
		{"邮箱空", "", "x", []string{"email"}},
		{"邮箱非法", "bad", "x", []string{"email"}},
		{"密码空", "a@sjtu.edu.cn", "", []string{"password"}},
	} {
		_, err := svc.Login(ctx, LoginInput{Email: tc.email, Password: tc.password})
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 422 {
			t.Fatalf("%s: 应 422，得到 %v", tc.name, err)
		}
		for _, f := range tc.wantFields {
			if len(apiErr.Fields[f]) == 0 {
				t.Fatalf("%s: fields[%s] 应有错误", tc.name, f)
			}
		}
	}
}

func TestResendCodeFieldValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	for _, tc := range []struct {
		name       string
		email      string
		wantFields []string
	}{
		{"邮箱空", "", []string{"email"}},
		{"邮箱纯空格", "   ", []string{"email"}},
		{"邮箱非法无域名", "bad-email", []string{"email"}},
		{"邮箱非法无点", "bad@domain", []string{"email"}},
	} {
		_, err := svc.ResendCode(ctx, ResendCodeInput{Email: tc.email})
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 422 {
			t.Fatalf("%s: 应 422，得到 %v", tc.name, err)
		}
		for _, f := range tc.wantFields {
			if len(apiErr.Fields[f]) == 0 {
				t.Fatalf("%s: fields[%s] 应有错误", tc.name, f)
			}
		}
	}
}

func TestResendCodeUnregisteredEmail(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	res, err := svc.ResendCode(ctx, ResendCodeInput{Email: "ghost@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("未注册邮箱不应报错（防枚举 R004）: %v", err)
	}
	if res.Email != "ghost@sjtu.edu.cn" || res.Message == "" {
		t.Fatalf("出参不符: %+v", res)
	}

	// 不得向未注册邮箱发信
	var letters int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&letters); err != nil {
		t.Fatal(err)
	}
	if letters != 0 {
		t.Fatalf("未注册邮箱不应发信，得到 %d 封", letters)
	}
}

func TestResendCodeDeactivatedUser(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	newVerifiedUser(t, d, "disabled@sjtu.edu.cn", "停用用户", "Password123!@#", false)

	res, err := svc.ResendCode(ctx, ResendCodeInput{Email: "disabled@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("停用账号不应报错（防枚举 R004）: %v", err)
	}
	if res.Message == "" {
		t.Fatalf("出参消息不应为空: %+v", res)
	}

	// 停用账号不发信
	var letters int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&letters); err != nil {
		t.Fatal(err)
	}
	if letters != 0 {
		t.Fatalf("停用账号不应发信，得到 %d 封", letters)
	}
}

func TestResendCodeAlreadyVerifiedUser(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	newVerifiedUser(t, d, "verified@sjtu.edu.cn", "已验证", "Password123!@#", true)

	res, err := svc.ResendCode(ctx, ResendCodeInput{Email: "verified@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("已验证账号不应报错（防枚举 R004）: %v", err)
	}
	if res.Message == "" {
		t.Fatalf("出参消息不应为空: %+v", res)
	}

	// 应入队 1 封提示信（告知已验证过，可直接登录）
	var letters int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&letters); err != nil {
		t.Fatal(err)
	}
	if letters != 1 {
		t.Fatalf("已验证账号应发 1 封提示信，得到 %d 封", letters)
	}

	// 不得生成 signup 验证码
	var codes int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM email_codes WHERE email_norm = ?", "verified@sjtu.edu.cn").Scan(&codes); err != nil {
		t.Fatal(err)
	}
	if codes != 0 {
		t.Fatalf("已验证账号不应生成验证码，得到 %d 条", codes)
	}
}

func TestResendCodeUnverifiedUser(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()
	svc.codeGen = fixedCode("111111")

	// 注册时生成第一个码
	mustRegister(t, svc, "resend@sjtu.edu.cn", "重发者", "Password123!@#")

	// 模拟旧码被尝试过 1 次
	oldCode, err := store.GetLatestEmailCode(ctx, "signup", "resend@sjtu.edu.cn")
	if err != nil || oldCode == nil {
		t.Fatalf("注册应生成码: %v", err)
	}
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		return store.BumpEmailCodeAttempts(ctx, tx, oldCode.ID)
	})
	if err != nil {
		t.Fatal(err)
	}

	// 换固定新码
	svc.codeGen = fixedCode("222222")

	// 请求重发验证码（R002、R006）
	res, err := svc.ResendCode(ctx, ResendCodeInput{Email: "resend@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("重发验证码应成功: %v", err)
	}
	if res.Email != "resend@sjtu.edu.cn" || res.Message == "" {
		t.Fatalf("出参不符: %+v", res)
	}

	// 验证旧码被作废、新码已写入且 attempts 为 0
	newCode, err := store.GetLatestEmailCode(ctx, "signup", "resend@sjtu.edu.cn")
	if err != nil || newCode == nil {
		t.Fatalf("应有新码: %v", err)
	}
	if newCode.ID == oldCode.ID {
		t.Fatalf("新码 ID 不该等于旧码 ID")
	}
	if newCode.Attempts != 0 {
		t.Fatalf("新码 attempts 应为 0，得到 %d", newCode.Attempts)
	}
	if newCode.ExpiresAt.Sub(newCode.CreatedAt) != 15*time.Minute {
		t.Fatalf("新码应为 15 分钟有效: %+v", newCode)
	}

	// 验证旧码被作废：库里该邮箱的 signup 码恰好只有 1 条（旧码已被彻底删除，作废 R002）
	var codeCount int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM email_codes WHERE purpose = 'signup' AND email_norm = ?", "resend@sjtu.edu.cn").Scan(&codeCount); err != nil {
		t.Fatal(err)
	}
	if codeCount != 1 {
		t.Fatalf("重发后该邮箱应只有 1 条有效验证码，得到 %d 条", codeCount)
	}

	// 信件入队：注册 1 封 + 重发 1 封 = 2 封
	var letters int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&letters); err != nil {
		t.Fatal(err)
	}
	if letters != 2 {
		t.Fatalf("应入队 2 封信，得到 %d", letters)
	}

	// 用新码核验应成功并建会话
	vres, err := svc.VerifyEmail(ctx, VerifyEmailInput{Email: "resend@sjtu.edu.cn", Code: "222222"})
	if err != nil || vres.Token == "" {
		t.Fatalf("新码核验应成功: %+v, err=%v", vres, err)
	}
}

type testClock struct {
	t time.Time
}

func (c *testClock) Now() time.Time { return c.t }

func TestResendCodeRateLimitKey(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	t0 := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: t0}
	enforcer := ratelimit.NewEnforcer(d, clk)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, enforcer)

	newVerifiedUser(t, d, "user1@sjtu.edu.cn", "用户一", "Password123!@#", true)
	newVerifiedUser(t, d, "user2@sjtu.edu.cn", "用户二", "Password123!@#", true)

	// 第一次：成功
	_, err := svc.ResendCode(ctx, ResendCodeInput{Email: "user1@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("第 1 次应成功: %v", err)
	}

	// 同一时间片内（10 秒内）第 2 次：429（R006: confirm_email 1/10s/key）
	_, err = svc.ResendCode(ctx, ResendCodeInput{Email: "user1@sjtu.edu.cn"})
	var apiErr *api.Error
	if !errors.As(err, &apiErr) || apiErr.Status != 429 {
		t.Fatalf("第 2 次应 429，得到 %v", err)
	}
	if apiErr.Header.Get("Retry-After") == "" {
		t.Fatalf("429 应带 Retry-After")
	}

	// 此时不同账号不受影响（per-key 隔离）
	_, err = svc.ResendCode(ctx, ResendCodeInput{Email: "user2@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("不同账号第 1 次应成功: %v", err)
	}

	// 时钟推进 11 秒后，user1 翻页恢复放行
	clk.t = t0.Add(11 * time.Second)
	_, err = svc.ResendCode(ctx, ResendCodeInput{Email: "user1@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("11 秒后重发应成功: %v", err)
	}
}

func TestRequestPasswordResetFieldValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	for _, tc := range []struct {
		name  string
		email string
	}{
		{"邮箱为空", ""},
		{"邮箱仅空格", "   "},
		{"邮箱格式非法", "not-an-email"},
		{"缺少顶级域", "user@domain"},
	} {
		_, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: tc.email})
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 422 {
			t.Fatalf("%s: 应返回 422，得到 %v", tc.name, err)
		}
		if len(apiErr.Fields["email"]) == 0 {
			t.Fatalf("%s: fields['email'] 应包含错误信息", tc.name)
		}
	}
}

func TestRequestPasswordResetUnknownEmailAntiEnumeration(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	// 未注册邮箱请求找回密码：返回统一成功响应（R004 防枚举）
	res, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "unknown@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("未注册邮箱找回密码应返回成功: %v", err)
	}
	if res.Email != "unknown@sjtu.edu.cn" || !strings.Contains(res.Message, "验证码") {
		t.Fatalf("出参不符: %+v", res)
	}

	// 库里不生成 password_reset 验证码
	var codeCount int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM email_codes WHERE purpose = 'password_reset'").Scan(&codeCount); err != nil {
		t.Fatal(err)
	}
	if codeCount != 0 {
		t.Fatalf("未注册邮箱不该生成验证码，得到 %d 条", codeCount)
	}

	// 但入队了一封「这个邮箱还没有注册」提醒信（附带注册链接）
	var jobArgs string
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT args FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&jobArgs); err != nil {
		t.Fatalf("未注册邮箱应入队提醒信: %v", err)
	}
	if !strings.Contains(jobArgs, "这个邮箱还没有注册") || !strings.Contains(jobArgs, "/accounts/signup/") {
		t.Fatalf("信件内容不符: %s", jobArgs)
	}
}

func TestRequestPasswordResetInactiveAccountAntiEnumeration(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	newVerifiedUser(t, d, "inactive@sjtu.edu.cn", "停用用户", "Password123!@#", false)

	// 停用账号请求重置密码：静默成功，不发信（防枚举）
	res, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "inactive@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("停用账号找回密码应成功: %v", err)
	}
	if res.Email != "inactive@sjtu.edu.cn" || !strings.Contains(res.Message, "验证码") {
		t.Fatalf("出参不符: %+v", res)
	}

	// 既不存码也不发信
	var codeCount, jobCount int
	_ = d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM email_codes WHERE purpose = 'password_reset'").Scan(&codeCount)
	_ = d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM jobs WHERE kind = ?", outbox.KindLetter).Scan(&jobCount)
	if codeCount != 0 || jobCount != 0 {
		t.Fatalf("停用账号不应生成码或信件: codes=%d, jobs=%d", codeCount, jobCount)
	}
}

func TestRequestPasswordResetActiveUserCodeAndLetter(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	store := NewStore(d)
	t0 := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: t0}
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("112233")

	newVerifiedUser(t, d, "active@sjtu.edu.cn", "活跃用户", "Password123!@#", true)

	// 首次请求找回密码
	res, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "active@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("找回密码发码应成功: %v", err)
	}
	if res.Email != "active@sjtu.edu.cn" {
		t.Fatalf("出参邮箱不符: %+v", res)
	}

	// 验证生成了 3 分钟有效期的验证码（R003）
	code1, err := store.GetLatestEmailCode(ctx, "password_reset", "active@sjtu.edu.cn")
	if err != nil || code1 == nil {
		t.Fatalf("应生成重置码: %v", err)
	}
	if code1.Attempts != 0 {
		t.Fatalf("尝试次数应为 0，得到 %d", code1.Attempts)
	}
	if code1.ExpiresAt.Sub(code1.CreatedAt) != 3*time.Minute {
		t.Fatalf("重置验证码有效期应为 3 分钟（R003），得到 %v", code1.ExpiresAt.Sub(code1.CreatedAt))
	}

	// 再次请求：作废旧码并生成新码，库中仍只有 1 条记录
	svc.codeGen = fixedCode("445566")
	clk.t = t0.Add(time.Minute)
	_, err = svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "active@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("第二次找回密码发码应成功: %v", err)
	}

	code2, err := store.GetLatestEmailCode(ctx, "password_reset", "active@sjtu.edu.cn")
	if err != nil || code2 == nil {
		t.Fatalf("应有新码: %v", err)
	}
	if code2.ID == code1.ID {
		t.Fatalf("新码 ID 不该等于旧码 ID")
	}

	var codeCount int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT count(*) FROM email_codes WHERE purpose = 'password_reset' AND email_norm = 'active@sjtu.edu.cn'").Scan(&codeCount); err != nil {
		t.Fatal(err)
	}
	if codeCount != 1 {
		t.Fatalf("旧码应被彻底作废，库里该邮箱应恰好有 1 条 password_reset 码，得到 %d", codeCount)
	}

	// 检查入队信件
	var letters []string
	rows, err := d.ReadPool().QueryContext(ctx, "SELECT args FROM jobs WHERE kind = ? ORDER BY id", outbox.KindLetter)
	if err != nil {
		t.Fatal(err)
	}
	defer rows.Close()
	for rows.Next() {
		var a string
		if err := rows.Scan(&a); err != nil {
			t.Fatal(err)
		}
		letters = append(letters, a)
	}
	if len(letters) != 2 {
		t.Fatalf("应入队 2 封找回密码信件，得到 %d 封", len(letters))
	}
	if !strings.Contains(letters[0], "找回密码验证码") || !strings.Contains(letters[0], "112233") || !strings.Contains(letters[0], "3 分钟内有效") {
		t.Fatalf("第一封信内容不符: %s", letters[0])
	}
}

func TestRequestPasswordResetRateLimitKey(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	t0 := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: t0}
	enforcer := ratelimit.NewEnforcer(d, clk)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, enforcer)

	newVerifiedUser(t, d, "limit1@sjtu.edu.cn", "限流用户一", "Password123!@#", true)
	newVerifiedUser(t, d, "limit2@sjtu.edu.cn", "限流用户二", "Password123!@#", true)

	// AuthResetPasswordKey: 同一账号每分钟最多 5 次（R006）
	for i := 1; i <= 5; i++ {
		_, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "limit1@sjtu.edu.cn"})
		if err != nil {
			t.Fatalf("第 %d 次请求应成功: %v", i, err)
		}
	}

	// 第 6 次触发 429
	_, err := svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "limit1@sjtu.edu.cn"})
	var apiErr *api.Error
	if !errors.As(err, &apiErr) || apiErr.Status != 429 {
		t.Fatalf("第 6 次应 429，得到 %v", err)
	}
	if apiErr.Header.Get("Retry-After") == "" {
		t.Fatalf("429 应包含 Retry-After")
	}

	// limit2 不受影响（按 key 隔离）
	_, err = svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "limit2@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("不同账号应成功: %v", err)
	}

	// 时间片翻页（61 秒后）恢复
	clk.t = t0.Add(61 * time.Second)
	_, err = svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "limit1@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("翻页后应放行: %v", err)
	}
}

func TestResetPasswordConfirmFieldValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	for _, tc := range []struct {
		name       string
		in         ResetPasswordConfirmInput
		wantFields []string
	}{
		{
			"全部为空",
			ResetPasswordConfirmInput{},
			[]string{"email", "code", "password"},
		},
		{
			"邮箱非法且码空",
			ResetPasswordConfirmInput{Email: "bad", Code: "", Password: "Password123!@#", ConfirmPassword: "Password123!@#"},
			[]string{"email", "code"},
		},
		{
			"两次密码不一致",
			ResetPasswordConfirmInput{Email: "test@sjtu.edu.cn", Code: "123456", Password: "Password123!@#", ConfirmPassword: "Mismatch123!@#"},
			[]string{"confirm_password"},
		},
		{
			"密码太短或纯数字弱密码",
			ResetPasswordConfirmInput{Email: "test@sjtu.edu.cn", Code: "123456", Password: "123", ConfirmPassword: "123"},
			[]string{"password"},
		},
		{
			"密码与邮箱过于相似",
			ResetPasswordConfirmInput{Email: "myuser@sjtu.edu.cn", Code: "123456", Password: "myuser123", ConfirmPassword: "myuser123"},
			[]string{"password"},
		},
	} {
		_, err := svc.ResetPasswordConfirm(ctx, tc.in)
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 422 {
			t.Fatalf("%s: 应 422，得到 %v", tc.name, err)
		}
		for _, f := range tc.wantFields {
			if len(apiErr.Fields[f]) == 0 {
				t.Fatalf("%s: fields[%s] 应该有错误信息", tc.name, f)
			}
		}
	}
}

func TestResetPasswordConfirmCodeAttemptsAndExpiry(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	store := NewStore(d)
	t0 := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: t0}
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("654321")

	newVerifiedUser(t, d, "confirm-test@sjtu.edu.cn", "核验用户", "OldPassword123!@#", true)
	_, _ = svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "confirm-test@sjtu.edu.cn"})

	// 1. 未注册邮箱核验报错与错码一致（防枚举 R004）
	_, errUnknown := svc.ResetPasswordConfirm(ctx, ResetPasswordConfirmInput{
		Email: "ghost@sjtu.edu.cn", Code: "654321", Password: "NewPassword123!@#", ConfirmPassword: "NewPassword123!@#",
	})
	if errString(errUnknown) != errString(errBadCode) {
		t.Fatalf("未注册邮箱报错不符: %v", errUnknown)
	}

	// 2. 第一次输错码：attempts 变成 1，返回 errBadCode
	_, err := svc.ResetPasswordConfirm(ctx, ResetPasswordConfirmInput{
		Email: "confirm-test@sjtu.edu.cn", Code: "000000", Password: "NewPassword123!@#", ConfirmPassword: "NewPassword123!@#",
	})
	if errString(err) != errString(errBadCode) {
		t.Fatalf("第一次错码应返回统一错误: %v", err)
	}
	c, _ := store.GetLatestEmailCode(ctx, "password_reset", "confirm-test@sjtu.edu.cn")
	if c == nil || c.Attempts != 1 {
		t.Fatalf("第一次错码后 attempts 应为 1: %+v", c)
	}

	// 3. 第二次输错码：attempts 变成 2
	_, _ = svc.ResetPasswordConfirm(ctx, ResetPasswordConfirmInput{
		Email: "confirm-test@sjtu.edu.cn", Code: "111111", Password: "NewPassword123!@#", ConfirmPassword: "NewPassword123!@#",
	})
	c, _ = store.GetLatestEmailCode(ctx, "password_reset", "confirm-test@sjtu.edu.cn")
	if c == nil || c.Attempts != 2 {
		t.Fatalf("第二次错码后 attempts 应为 2: %+v", c)
	}

	// 4. 第三次输错码：达到 3 次尝试上限，直接物理删除作废（R003）
	_, _ = svc.ResetPasswordConfirm(ctx, ResetPasswordConfirmInput{
		Email: "confirm-test@sjtu.edu.cn", Code: "222222", Password: "NewPassword123!@#", ConfirmPassword: "NewPassword123!@#",
	})
	c, _ = store.GetLatestEmailCode(ctx, "password_reset", "confirm-test@sjtu.edu.cn")
	if c != nil {
		t.Fatalf("3 次尝试用尽后码应被删除作废，仍然存在: %+v", c)
	}

	// 5. 过期测试（> 3 分钟失效，R003）
	svc.codeGen = fixedCode("778899")
	_, _ = svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "confirm-test@sjtu.edu.cn"})
	clk.t = t0.Add(3*time.Minute + time.Second) // 超过 3 分钟

	_, errExpired := svc.ResetPasswordConfirm(ctx, ResetPasswordConfirmInput{
		Email: "confirm-test@sjtu.edu.cn", Code: "778899", Password: "NewPassword123!@#", ConfirmPassword: "NewPassword123!@#",
	})
	if errString(errExpired) != errString(errBadCode) {
		t.Fatalf("过期验证码应返回统一错误: %v", errExpired)
	}
}

func TestResetPasswordConfirmSuccess(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	store := NewStore(d)
	t0 := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: t0}
	sessions := auth.NewStore(d, clk)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", sessions, nil)
	svc.codeGen = fixedCode("998877")

	u := newVerifiedUser(t, d, "success-reset@sjtu.edu.cn", "成功用户", "OldPassword123!@#", true)

	// 先建立一个活跃会话
	oldToken, err := sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	sess, err := sessions.Lookup(ctx, oldToken)
	if err != nil || sess == nil {
		t.Fatalf("旧会话应存在")
	}

	// 请求重置密码
	_, err = svc.RequestPasswordReset(ctx, ResetPasswordInput{Email: "success-reset@sjtu.edu.cn"})
	if err != nil {
		t.Fatalf("请求发码应成功: %v", err)
	}

	// 提交重置密码
	clk.t = t0.Add(time.Minute)
	res, err := svc.ResetPasswordConfirm(ctx, ResetPasswordConfirmInput{
		Email:           "success-reset@sjtu.edu.cn",
		Code:            "998877",
		Password:        "NewPassword123!@#",
		ConfirmPassword: "NewPassword123!@#",
	})
	if err != nil {
		t.Fatalf("重置密码应成功: %v", err)
	}
	if res.Result != "ok" || !strings.Contains(res.Message, "成功") {
		t.Fatalf("出参不符: %+v", res)
	}

	// 1. 旧会话已被彻底作废（5.7 改密码删所有会话）
	sess, err = sessions.Lookup(ctx, oldToken)
	if err != nil || sess != nil {
		t.Fatalf("重置密码后原有会话应被全部作废")
	}

	// 2. 验证码已被删除
	c, _ := store.GetLatestEmailCode(ctx, "password_reset", "success-reset@sjtu.edu.cn")
	if c != nil {
		t.Fatalf("重置成功后验证码应被删除")
	}

	// 3. 用户密码已更新为新密码哈希且 password_changed_at 已更新
	updatedUser, err := store.GetByID(ctx, u.ID)
	if err != nil || updatedUser == nil {
		t.Fatal(err)
	}
	okOld, _, _ := auth.Verify(ctx, updatedUser.PasswordHash, "OldPassword123!@#")
	if okOld {
		t.Fatalf("旧密码不应再能通过验证")
	}
	okNew, _, _ := auth.Verify(ctx, updatedUser.PasswordHash, "NewPassword123!@#")
	if !okNew {
		t.Fatalf("新密码应该验证通过")
	}
	if updatedUser.PasswordChangedAt == nil || !updatedUser.PasswordChangedAt.Equal(clk.t) {
		t.Fatalf("password_changed_at 应更新为当前时间: %+v", updatedUser.PasswordChangedAt)
	}

	// 4. 可以用新密码登录
	loginRes, err := svc.Login(ctx, LoginInput{
		Email:    "success-reset@sjtu.edu.cn",
		Password: "NewPassword123!@#",
	})
	if err != nil || loginRes.Result != "ok" || loginRes.Token == "" {
		t.Fatalf("新密码应能正常登录: %+v, err=%v", loginRes, err)
	}
}

func TestChangePasswordValidation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	u := newVerifiedUser(t, d, "cp-val@sjtu.edu.cn", "改密码校验", "OldPassword123!@#", true)
	appCtx := &app.Ctx{
		Context: ctx,
		Viewer:  &app.Viewer{ID: u.ID},
	}

	for _, tc := range []struct {
		name       string
		old        string
		new        string
		confirm    string
		wantFields []string
	}{
		{"当前密码空", "", "NewPass123!@#", "NewPass123!@#", []string{"old_password"}},
		{"新密码空", "OldPassword123!@#", "", "", []string{"password", "confirm_password"}},
		{"确认密码空", "OldPassword123!@#", "NewPass123!@#", "", []string{"confirm_password"}},
		{"两次密码不一致", "OldPassword123!@#", "NewPass123!@#", "Mismatch123!@#", []string{"confirm_password"}},
		{"新旧密码相同", "OldPassword123!@#", "OldPassword123!@#", "OldPassword123!@#", []string{"password"}},
		{"新密码太弱纯数字", "OldPassword123!@#", "12345678", "12345678", []string{"password"}},
		{"新密码太弱包含邮箱", "OldPassword123!@#", "cp-val@sjtu.edu.cn", "cp-val@sjtu.edu.cn", []string{"password"}},
	} {
		_, err := svc.ChangePassword(appCtx, ChangePasswordInput{
			OldPassword:     tc.old,
			Password:        tc.new,
			ConfirmPassword: tc.confirm,
		})
		var apiErr *api.Error
		if !errors.As(err, &apiErr) || apiErr.Status != 422 {
			t.Fatalf("%s: 应 422，得到 %v", tc.name, err)
		}
		for _, f := range tc.wantFields {
			if len(apiErr.Fields[f]) == 0 {
				t.Fatalf("%s: fields[%s] 应有错误", tc.name, f)
			}
		}
	}
}

func TestChangePasswordUnauthenticatedOrDisabled(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	u := newVerifiedUser(t, d, "cp-unauth@sjtu.edu.cn", "未登用户", "OldPassword123!@#", true)

	// 1. nil app.Ctx
	if _, err := svc.ChangePassword(nil, ChangePasswordInput{OldPassword: "x", Password: "y", ConfirmPassword: "y"}); err == nil {
		t.Fatal("nil Ctx 应报错")
	}

	// 2. nil Viewer
	nilViewerCtx := &app.Ctx{Context: ctx}
	if _, err := svc.ChangePassword(nilViewerCtx, ChangePasswordInput{OldPassword: "x", Password: "y", ConfirmPassword: "y"}); err == nil {
		t.Fatal("nil Viewer 应报错")
	}

	// 3. Disabled Viewer
	disabledCtx := &app.Ctx{Context: ctx, Viewer: &app.Viewer{ID: u.ID, Disabled: true}}
	if _, err := svc.ChangePassword(disabledCtx, ChangePasswordInput{OldPassword: "x", Password: "y", ConfirmPassword: "y"}); err == nil {
		t.Fatal("Disabled Viewer 应报错")
	}
}

func TestChangePasswordWrongOldPassword(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	u := newVerifiedUser(t, d, "cp-wrong@sjtu.edu.cn", "错密用户", "RealOldPassword123!@#", true)
	appCtx := &app.Ctx{
		Context: ctx,
		Viewer:  &app.Viewer{ID: u.ID},
	}

	_, err := svc.ChangePassword(appCtx, ChangePasswordInput{
		OldPassword:     "WrongPassword123!@#",
		Password:        "BrandNewPassword123!@#",
		ConfirmPassword: "BrandNewPassword123!@#",
	})
	var apiErr *api.Error
	if !errors.As(err, &apiErr) || apiErr.Status != 422 {
		t.Fatalf("旧密码错误应 422，得到 %v", err)
	}
	if len(apiErr.Fields["old_password"]) == 0 || !strings.Contains(apiErr.Fields["old_password"][0], "不正确") {
		t.Fatalf("应提示当前密码不正确: %+v", apiErr.Fields)
	}
}

func TestChangePasswordSuccess(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	t0 := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := &testClock{t: t0}
	sessions := auth.NewStore(d, clk)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", sessions, nil)

	u := newVerifiedUser(t, d, "cp-succ@sjtu.edu.cn", "成功改密", "OldPassword123!@#", true)
	otherUser := newVerifiedUser(t, d, "other-user@sjtu.edu.cn", "他人", "OldPassword123!@#", true)

	// 为 u 创建会话 A（当前会话）和会话 B（另一个设备）
	sessA, err := sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	sessB, err := sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	// 为他人创建会话 C
	sessC, err := sessions.Create(ctx, otherUser.ID)
	if err != nil {
		t.Fatal(err)
	}

	clk.t = t0.Add(10 * time.Minute)
	appCtx := &app.Ctx{
		Context:      ctx,
		Viewer:       &app.Viewer{ID: u.ID},
		Clock:        clk,
		SessionToken: sessA,
	}

	res, err := svc.ChangePassword(appCtx, ChangePasswordInput{
		OldPassword:     "OldPassword123!@#",
		Password:        "NewAwesomePassword123!@#",
		ConfirmPassword: "NewAwesomePassword123!@#",
	})
	if err != nil {
		t.Fatalf("修改密码应成功: %v", err)
	}
	if res.Result != "ok" || !strings.Contains(res.Message, "成功") {
		t.Fatalf("出参不符: %+v", res)
	}

	// 1. 验证会话处置（12 号文档 5.7：改密码时删掉这个人的其他会话）
	// 会话 A（当前会话）依然有效
	if gotA, err := sessions.Lookup(ctx, sessA); err != nil || gotA == nil {
		t.Fatalf("当前会话 A 应该保留，得到 %+v, err=%v", gotA, err)
	}
	// 会话 B（同一人的其他会话）已被作废
	if gotB, err := sessions.Lookup(ctx, sessB); err != nil || gotB != nil {
		t.Fatalf("其他会话 B 应该被删除，得到 %+v", gotB)
	}
	// 会话 C（其他人的会话）不受影响
	if gotC, err := sessions.Lookup(ctx, sessC); err != nil || gotC == nil {
		t.Fatalf("他人会话 C 不应受影响，得到 %+v", gotC)
	}

	// 2. 验证用户数据更新
	updated, err := svc.Store().GetByID(ctx, u.ID)
	if err != nil || updated == nil {
		t.Fatal(err)
	}
	okOld, _, _ := auth.Verify(ctx, updated.PasswordHash, "OldPassword123!@#")
	if okOld {
		t.Fatal("旧密码不应再能通过验证")
	}
	okNew, _, _ := auth.Verify(ctx, updated.PasswordHash, "NewAwesomePassword123!@#")
	if !okNew {
		t.Fatal("新密码应该能通过验证")
	}
	if updated.PasswordChangedAt == nil || !updated.PasswordChangedAt.Equal(clk.t) {
		t.Fatalf("password_changed_at 应记录当前时间: %v", updated.PasswordChangedAt)
	}

	// 3. 可以用新密码登录
	loginRes, err := svc.Login(ctx, LoginInput{
		Email:    "cp-succ@sjtu.edu.cn",
		Password: "NewAwesomePassword123!@#",
	})
	if err != nil || loginRes.Result != "ok" || loginRes.Token == "" {
		t.Fatalf("新密码应能正常登录: %+v, err=%v", loginRes, err)
	}
}

func TestLogout(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sessions := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sessions, nil)

	u := newVerifiedUser(t, d, "logout@sjtu.edu.cn", "退出用户", "Password123!@#", true)
	sessTok, err := sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}

	// 1. 未登录调用
	if _, err := svc.Logout(nil); err == nil {
		t.Fatal("nil ctx 应 401")
	}
	if _, err := svc.Logout(&app.Ctx{Context: ctx}); err == nil {
		t.Fatal("nil viewer 应 401")
	}
	if _, err := svc.Logout(&app.Ctx{Context: ctx, Viewer: &app.Viewer{ID: u.ID, Disabled: true}}); err == nil {
		t.Fatal("disabled viewer 应 401")
	}

	// 2. 正常退出
	appCtx := &app.Ctx{
		Context:      ctx,
		Viewer:       &app.Viewer{ID: u.ID},
		SessionToken: sessTok,
	}
	res, err := svc.Logout(appCtx)
	if err != nil {
		t.Fatalf("退出登录应成功: %v", err)
	}
	if res.Result != "ok" || !strings.Contains(res.Message, "退出") {
		t.Fatalf("出参不符: %+v", res)
	}

	// 验证会话在库中已删除
	if sess, err := sessions.Lookup(ctx, sessTok); err != nil || sess != nil {
		t.Fatalf("退出后会话应已被删除: %+v", sess)
	}

	// 验证已标记清除 Cookie
	if !appCtx.ShouldClearSessionCookie() {
		t.Fatal("退出登录后应标记清除会话 Cookie")
	}
}
