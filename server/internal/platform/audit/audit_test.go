package audit

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_audit.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestAuditLogQuery(t *testing.T) {
	d := newTestDB(t)

	// 插入测试用户与操作日志
	ctx := context.Background()
	now := time.Now().UTC()
	err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `INSERT INTO users (
			id, email, email_norm, password_hash, nickname, is_sjtu,
			agreed_terms_at, agreed_cross_border_at, version, is_active, is_superuser,
			created_at, updated_at
		) VALUES (1, 'admin@example.com', 'admin@example.com', 'x', '站长', 1, '2026-01-01', '2026-01-01', 1, 1, 1, '2026-01-01', '2026-01-01')`)
		if err != nil {
			return err
		}

		return Record(txCtx, tx, 1, "update_settings", "settings", 1, map[string]any{"field": "smtp_host"}, now)
	})
	if err != nil {
		t.Fatalf("setup audit data failed: %v", err)
	}

	// 查询全部日志
	res, err := Query(ctx, d.ReadPool(), QueryInput{Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("Query audit failed: %v", err)
	}
	if res.Total != 1 {
		t.Fatalf("expected 1 audit record, got %d", res.Total)
	}
	if len(res.Items) != 1 {
		t.Fatalf("expected 1 item in slice, got %d", len(res.Items))
	}

	item := res.Items[0]
	if item.Action != "update_settings" {
		t.Errorf("expected action update_settings, got %q", item.Action)
	}
	if item.ActorNickname != "站长" {
		t.Errorf("expected actor nickname 站长, got %q", item.ActorNickname)
	}

	// 带过滤条件查询
	resFiltered, err := Query(ctx, d.ReadPool(), QueryInput{Action: "non_existent", Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("Query filtered failed: %v", err)
	}
	if resFiltered.Total != 0 {
		t.Errorf("expected 0 records for non_existent action, got %d", resFiltered.Total)
	}
}
