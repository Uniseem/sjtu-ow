package health

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
)

func newDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestProbeRollsBackAndHidesDetail(t *testing.T) {
	d := newDB(t)
	dir := t.TempDir()
	prev := readDisk
	readDisk = func(string) (uint64, uint64, error) { return 50, 100, nil }
	t.Cleanup(func() { readDisk = prev })
	now := time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	w := jobs.New(d, nil)
	if err := w.Lock(context.Background(), now); err != nil {
		t.Fatal(err)
	}

	public := Report(context.Background(), d, dir, now, false)
	if !public.OK || public.Checks["database"].Detail != "" || strings.Contains(mustJSON(t, public), "detail") {
		t.Fatalf("对外不该有详情：%+v", public)
	}
	full := Report(context.Background(), d, dir, now, true)
	if full.Checks["database"].Detail != "ok" || full.Checks["worker_heartbeat"].Detail == "" {
		t.Fatalf("超管该看到详情：%+v", full.Checks)
	}
	var n int
	if err := d.ReadPool().QueryRow(`SELECT COUNT(*) FROM health_probe`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 0 {
		t.Fatal("探测行应该回滚掉")
	}
}

func TestDiskAtTwentyPercentIsDown(t *testing.T) {
	prev := readDisk
	t.Cleanup(func() { readDisk = prev })
	readDisk = func(string) (uint64, uint64, error) { return 20, 100, nil }
	c := checkDisk(t.TempDir())
	if c.OK {
		t.Fatal("剩余刚好 20% 应该不健康")
	}
	readDisk = func(string) (uint64, uint64, error) { return 21, 100, nil }
	if !checkDisk(t.TempDir()).OK {
		t.Fatal("剩余 21% 应该健康")
	}
}

func TestBacklogUsesRunAfter(t *testing.T) {
	d := newDB(t)
	now := time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	insertJob(t, d, now.Add(-2*time.Minute))
	if !checkBacklog(context.Background(), d, now).OK {
		t.Fatal("两分钟前到期的还不算积压")
	}
	insertJob(t, d, now.Add(-11*time.Minute))
	c := checkBacklog(context.Background(), d, now)
	if c.OK || !strings.Contains(c.Detail, "1 个任务") {
		t.Fatalf("十一分钟前到期的算积压：%+v", c)
	}
}

func TestHeartbeatMissingAndStale(t *testing.T) {
	d := newDB(t)
	now := time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	if checkHeartbeat(context.Background(), d, now).OK {
		t.Fatal("没有 worker 应该不健康")
	}
	w := jobs.New(d, nil)
	if err := w.Lock(context.Background(), now.Add(-3*time.Minute)); err != nil {
		t.Fatal(err)
	}
	if checkHeartbeat(context.Background(), d, now).OK {
		t.Fatal("三分钟没心跳应该不健康")
	}
}

func TestHandlerStatus(t *testing.T) {
	d := newDB(t)
	prev := readDisk
	readDisk = func(string) (uint64, uint64, error) { return 50, 100, nil }
	t.Cleanup(func() { readDisk = prev })
	h := Handler(d, t.TempDir(), func() time.Time {
		return time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	}, func(*http.Request) bool { return false })
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if rec.Code != http.StatusServiceUnavailable || strings.Contains(rec.Body.String(), "detail") {
		t.Fatalf("没心跳应 503 且不带详情：%d %s", rec.Code, rec.Body.String())
	}
}

func insertJob(t *testing.T, d *db.DB, due time.Time) {
	t.Helper()
	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO jobs
			(kind, args, lane, run_after, status, created_at)
			VALUES ('x', '{}', 'default', ?, 'ready', ?)`,
			db.FormatUTC(due), db.FormatUTC(due))
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
}

func mustJSON(t *testing.T, result Result) string {
	t.Helper()
	b, err := json.Marshal(result)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}
