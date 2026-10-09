package accounts

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

type dummyMedia struct {
	d        *db.DB
	lastID   int64
	deleted  []int64
	uploaded []media.UploadInput
}

func (m *dummyMedia) Upload(ctx *app.Ctx, in media.UploadInput) (*media.Image, error) {
	m.lastID++
	if m.d != nil {
		_ = m.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
			_, err := tx.ExecContext(txCtx, `INSERT INTO images (id, title, file_name, file_size, width, height, created_at, version)
				VALUES (?, ?, ?, 100, 10, 10, '2026-01-01', 1)`, m.lastID, in.Title, in.FileName)
			return err
		})
	}
	m.uploaded = append(m.uploaded, in)
	return &media.Image{
		ID:       m.lastID,
		FileName: in.FileName,
		Title:    in.Title,
	}, nil
}

func (m *dummyMedia) DeleteImage(ctx *app.Ctx, id int64) error {
	m.deleted = append(m.deleted, id)
	return nil
}

func newAvatarTestEnv(t *testing.T) (*Service, *dummyMedia, *db.DB) {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_avatar.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })

	svc := NewService(d, nil, "https://sjtu.example", nil, nil)
	dm := &dummyMedia{d: d}
	svc.SetMedia(dm)

	// 插入测试用户
	err = d.WriteTx(context.Background(), func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `INSERT INTO users (
			id, email, email_norm, password_hash, nickname, is_sjtu,
			agreed_terms_at, agreed_cross_border_at, version, is_active, is_superuser,
			created_at, updated_at
		) VALUES (1, 'user@example.com', 'user@example.com', 'x', '测试成员', 1, '2026-01-01', '2026-01-01', 1, 1, 0, '2026-01-01', '2026-01-01')`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}

	return svc, dm, d
}

// 契约 R022–R027：头像上传、自动清旧图、管理员下架与本人移除
func TestSubmitAndRemoveAvatar(t *testing.T) {
	svc, dm, d := newAvatarTestEnv(t)

	ctx := &app.Ctx{
		Context: context.Background(),
		Viewer: &app.Viewer{
			ID:        1,
			Nickname:  "测试成员",
			Superuser: false,
		},
	}

	// 1. 上传新头像 (1x1 PNG dataURL)
	pngDataURL := "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
	img, err := svc.SubmitAvatar(ctx, "avatar.png", pngDataURL)
	if err != nil {
		t.Fatalf("SubmitAvatar failed: %v", err)
	}
	if img.ID != 1 {
		t.Errorf("expected image ID 1, got %d", img.ID)
	}

	// 检查 users 表 avatar_image_id
	var avID *int64
	_ = d.ReadPool().QueryRowContext(ctx.Context, `SELECT avatar_image_id FROM users WHERE id = 1`).Scan(&avID)
	if avID == nil || *avID != 1 {
		t.Errorf("expected user avatar_image_id 1, got %v", avID)
	}

	// 2. 再次上传新头像，旧头像应被清理
	img2, err := svc.SubmitAvatar(ctx, "avatar2.png", pngDataURL)
	if err != nil {
		t.Fatalf("SubmitAvatar second failed: %v", err)
	}
	if img2.ID != 2 {
		t.Errorf("expected image ID 2, got %d", img2.ID)
	}
	if len(dm.deleted) != 1 || dm.deleted[0] != 1 {
		t.Errorf("expected old image 1 deleted, got: %v", dm.deleted)
	}

	// 3. 管理员列出头像
	adminCtx := &app.Ctx{
		Context: context.Background(),
		Viewer: &app.Viewer{
			ID:        99,
			Superuser: true,
		},
	}
	subs, total, err := svc.ListAvatars(adminCtx, "", 1, 10)
	if err != nil {
		t.Fatalf("ListAvatars failed: %v", err)
	}
	if total != 2 || len(subs) != 2 {
		t.Errorf("expected 2 avatar submissions, got %d", total)
	}

	// 4. 管理员下架违规头像
	err = svc.TakeDownAvatar(adminCtx, subs[0].ID, "涉嫌违规")
	if err != nil {
		t.Fatalf("TakeDownAvatar failed: %v", err)
	}

	// 下架后该用户的 avatar_image_id 应变为 NULL
	_ = d.ReadPool().QueryRowContext(ctx.Context, `SELECT avatar_image_id FROM users WHERE id = 1`).Scan(&avID)
	if avID != nil {
		t.Errorf("expected avatar_image_id nil after takedown, got %v", *avID)
	}

	// 5. 移除头像
	err = svc.RemoveAvatar(ctx)
	if err != nil {
		t.Fatalf("RemoveAvatar failed: %v", err)
	}
}
