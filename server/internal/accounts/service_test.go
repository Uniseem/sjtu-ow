package accounts

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
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
	svc := NewService(d, nil)
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
