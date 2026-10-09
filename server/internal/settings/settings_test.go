package settings

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_settings.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	_ = d.WriteTx(context.Background(), func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `INSERT INTO users (
			id, email, email_norm, password_hash, nickname, is_sjtu,
			agreed_terms_at, agreed_cross_border_at, version, is_active, is_superuser,
			created_at, updated_at
		) VALUES (1, 'admin@example.com', 'admin@example.com', 'x', '站长', 1, '2026-01-01', '2026-01-01', 1, 1, 1, '2026-01-01', '2026-01-01')`)
		return err
	})
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestSettingsGetAndPatch(t *testing.T) {
	d := newTestDB(t)
	fieldKey := "01234567890123456789012345678901"
	svc := NewService(d, "https://sjtu.example", fieldKey)

	ctx := &app.Ctx{
		Context: context.Background(),
		Viewer: &app.Viewer{
			ID:        1,
			Nickname:  "站长",
			Superuser: true,
		},
	}

	// 1. 默认读取
	dto, err := svc.Get(ctx.Context)
	if err != nil {
		t.Fatalf("svc.Get failed: %v", err)
	}
	if dto.FromName != "SJTU-OW" {
		t.Errorf("expected from_name SJTU-OW, got %q", dto.FromName)
	}
	if dto.HasSmtpPassword {
		t.Errorf("expected no smtp password initially")
	}

	// 2. 修改设置（含密码与敏感字段）
	newDesc := "上海交通大学守望先锋社区"
	newHost := "smtp.example.com"
	newPort := 587
	newPass := "secret-smtp-pass"
	modKey := "sk-deepseek-api-key"
	enableMod := true

	patchIn := UpdateSettingsInput{
		SiteDescription:   &newDesc,
		SmtpHost:          &newHost,
		SmtpPort:          &newPort,
		SmtpPassword:      &newPass,
		ModerationEnabled: &enableMod,
		ModerationAPIKey:  &modKey,
	}

	updated, err := svc.Update(ctx, patchIn)
	if err != nil {
		t.Fatalf("svc.Update failed: %v", err)
	}
	if updated.SiteDescription != newDesc {
		t.Errorf("expected site_description %q, got %q", newDesc, updated.SiteDescription)
	}
	if updated.SmtpHost != newHost {
		t.Errorf("expected smtp_host %q, got %q", newHost, updated.SmtpHost)
	}
	if !updated.HasSmtpPassword {
		t.Errorf("expected HasSmtpPassword true")
	}
	if !updated.HasModerationAPIKey {
		t.Errorf("expected HasModerationAPIKey true")
	}

	// 3. 再次读取验证持久化
	dto2, err := svc.Get(ctx.Context)
	if err != nil {
		t.Fatalf("svc.Get failed: %v", err)
	}
	if dto2.SiteDescription != newDesc {
		t.Errorf("persisted description mismatch: got %q", dto2.SiteDescription)
	}
	if !dto2.HasSmtpPassword {
		t.Errorf("persisted HasSmtpPassword should be true")
	}

	// 4. 留空密码不覆盖原密码
	emptyPass := ""
	patchIn2 := UpdateSettingsInput{
		SmtpPassword: &emptyPass,
	}
	updated2, err := svc.Update(ctx, patchIn2)
	if err != nil {
		t.Fatalf("svc.Update second failed: %v", err)
	}
	if !updated2.HasSmtpPassword {
		t.Errorf("empty password string should preserve existing encrypted password")
	}
}
