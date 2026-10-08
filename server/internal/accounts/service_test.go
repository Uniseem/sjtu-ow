package accounts

import (
	"context"
	"errors"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
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
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")
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
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")
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
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")

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

func TestRegisterAntiEnumeration(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")
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
