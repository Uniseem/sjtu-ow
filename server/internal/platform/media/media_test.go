package media

import (
	"bytes"
	"context"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func createTestImage(w, h int) []byte {
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			img.Set(x, y, color.RGBA{R: uint8(x % 256), G: uint8(y % 256), B: 100, A: 255})
		}
	}
	var buf bytes.Buffer
	_ = png.Encode(&buf, img)
	return buf.Bytes()
}

func setupTestDB(t *testing.T) (*db.DB, string) {
	t.Helper()
	tmpDir, err := os.MkdirTemp("", "media_test_*")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}

	dbPath := filepath.Join(tmpDir, "test.db")
	database, err := db.Open(dbPath)
	if err != nil {
		t.Fatalf("failed to open db: %v", err)
	}

	// 执行当前所有迁移
	ctx := context.Background()
	if err := db.Migrate(ctx, database); err != nil {
		t.Fatalf("failed to run migrations: %v", err)
	}

	// 插入一个测试用户
	err = database.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `
			INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at, version, is_active, is_superuser, created_at, updated_at)
			VALUES (1, 'test@sjtu.edu.cn', 'test@sjtu.edu.cn', 'hash', 'TestUser', 1, '2026-10-09T00:00:00Z', '2026-10-09T00:00:00Z', 1, 1, 1, '2026-10-09T00:00:00Z', '2026-10-09T00:00:00Z')
		`)
		return err
	})
	if err != nil {
		t.Fatalf("failed to insert test user: %v", err)
	}

	t.Cleanup(func() {
		_ = database.Close()
		_ = os.RemoveAll(tmpDir)
	})

	return database, tmpDir
}

func TestMediaUploadAndThumbnail(t *testing.T) {
	database, tmpDir := setupTestDB(t)
	dataDir := filepath.Join(tmpDir, "data")
	mediaDir := filepath.Join(tmpDir, "media")
	svc := NewService(database, dataDir, mediaDir)

	ctx := &app.Ctx{
		Context: context.Background(),
		Viewer:  &app.Viewer{ID: 1, Superuser: true},
		Clock:   clock.Fixed(time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)),
	}

	pngData := createTestImage(200, 100)
	img, err := svc.Upload(ctx, UploadInput{
		Title:         "测试图片",
		FileName:      "test.png",
		CollectionKey: "contributed",
		Reader:        bytes.NewReader(pngData),
		FileSize:      int64(len(pngData)),
	})
	if err != nil {
		t.Fatalf("Upload failed: %v", err)
	}
	if img.ID <= 0 {
		t.Fatalf("expected positive image ID, got %d", img.ID)
	}
	if img.Width != 200 || img.Height != 100 {
		t.Fatalf("expected 200x100, got %dx%d", img.Width, img.Height)
	}

	// 测试生成合法规格缩略图
	thumbPath, err := svc.RenderThumbnail(ctx.Context, img.ID, "fill-88x88")
	if err != nil {
		t.Fatalf("RenderThumbnail fill-88x88 failed: %v", err)
	}
	if _, err := os.Stat(thumbPath); err != nil {
		t.Fatalf("thumbnail file does not exist: %v", err)
	}

	// 重复调用应直接命中缓存
	thumbPath2, err := svc.RenderThumbnail(ctx.Context, img.ID, "fill-88x88")
	if err != nil || thumbPath2 != thumbPath {
		t.Fatalf("second call to RenderThumbnail failed: %v", err)
	}

	// 测试非法规格被拒
	_, err = svc.RenderThumbnail(ctx.Context, img.ID, "fill-999x999")
	if err == nil {
		t.Fatalf("expected error for unwhitelisted spec, got nil")
	}

	// 测试删除
	if err := svc.DeleteImage(ctx, img.ID); err != nil {
		t.Fatalf("DeleteImage failed: %v", err)
	}

	// 确认母版已删除
	if _, err := os.Stat(svc.MasterPath(img.ID)); !os.IsNotExist(err) {
		t.Fatalf("expected master file to be deleted, err=%v", err)
	}
}

func TestMediaUploadValidation(t *testing.T) {
	database, tmpDir := setupTestDB(t)
	svc := NewService(database, filepath.Join(tmpDir, "data"), filepath.Join(tmpDir, "media"))

	ctx := &app.Ctx{
		Context: context.Background(),
		Viewer:  &app.Viewer{ID: 1},
		Clock:   clock.Fixed(time.Now()),
	}

	// 1. 无效格式
	_, err := svc.Upload(ctx, UploadInput{
		FileName: "not-an-image.txt",
		Reader:   bytes.NewReader([]byte("plain text")),
		FileSize: 10,
	})
	if err == nil {
		t.Fatalf("expected error for non-image, got nil")
	}

	// 2. 尺寸过小 (< 10x10)
	tiny := image.NewRGBA(image.Rect(0, 0, 5, 5))
	var buf bytes.Buffer
	_ = jpeg.Encode(&buf, tiny, nil)
	_, err = svc.Upload(ctx, UploadInput{
		FileName: "tiny.jpg",
		Reader:   bytes.NewReader(buf.Bytes()),
		FileSize: int64(buf.Len()),
	})
	if err == nil {
		t.Fatalf("expected error for tiny image, got nil")
	}
}
