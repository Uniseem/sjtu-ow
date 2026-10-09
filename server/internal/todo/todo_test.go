package todo

import (
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_todo.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

// 契约 R142、R168、R205：管理员待办聚合（赛事待审/编队、内战未分队、AI 异常与 Worker 心跳）
func TestTodoDuties(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d)

	// 普通未登录用户：无待办
	guestCtx := &app.Ctx{
		Context: context.Background(),
		Viewer:  nil,
	}
	res, err := svc.GetDuties(guestCtx)
	if err != nil {
		t.Fatalf("GetDuties guest failed: %v", err)
	}
	if res.HasDuties {
		t.Errorf("guest should have no duties")
	}

	// 超级管理员：有待办检查能力
	adminCtx := &app.Ctx{
		Context: context.Background(),
		Viewer: &app.Viewer{
			ID:        1,
			Nickname:  "站长",
			Superuser: true,
		},
	}
	resAdmin, err := svc.GetDuties(adminCtx)
	if err != nil {
		t.Fatalf("GetDuties admin failed: %v", err)
	}
	if !resAdmin.HasDuties {
		t.Errorf("admin should have duties capability")
	}
	// 空库时无 worker 运行，应当提示 worker 未运行
	foundWorker := false
	for _, it := range resAdmin.Items {
		if strings.Contains(it.Text, "worker") {
			foundWorker = true
			break
		}
	}
	if !foundWorker {
		t.Errorf("expected worker warning when worker not beating")
	}

	// 模拟 worker 心跳正常
	err = d.WriteTx(context.Background(), func(txCtx context.Context, tx *db.Tx) error {
		nowUTC := db.FormatUTC(time.Now().UTC())
		_, err := tx.ExecContext(txCtx, `INSERT INTO worker_status (id, started_at, heartbeat_at)
			VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET heartbeat_at = excluded.heartbeat_at`,
			nowUTC, nowUTC)
		return err
	})
	if err != nil {
		t.Fatalf("insert worker_status failed: %v", err)
	}

	resAlive, err := svc.GetDuties(adminCtx)
	if err != nil {
		t.Fatalf("GetDuties after heartbeat failed: %v", err)
	}
	if len(resAlive.Items) != 0 {
		t.Errorf("expected no pending items after worker alive, got %v", resAlive.Items)
	}
}
