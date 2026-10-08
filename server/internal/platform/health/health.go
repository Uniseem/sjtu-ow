// Package health 是 /healthz（12 号文档 5.15）。
// 对外只有总状态和每一项真假；详情只给超管。
package health

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"syscall"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const (
	// DiskMinFree 是数据卷剩余空间的下限。等于或低于这个比例就不健康。
	DiskMinFree = 0.20
	// HeartbeatStale 和 worker 锁是同一个 120 秒。
	HeartbeatStale = 120 * time.Second
	// BacklogAfter 是 ready 且到期时间早过这么久才算积压。
	BacklogAfter = 10 * time.Minute
)

// Result 是一次检查的结果。
type Result struct {
	Status string           `json:"status"`
	Checks map[string]Check `json:"checks"`
	OK     bool             `json:"-"`
}

// Check 是一项。Detail 只在给超管看的时候填上。
type Check struct {
	OK     bool   `json:"ok"`
	Detail string `json:"detail,omitempty"`
}

type probeRollback struct{}

func (probeRollback) Error() string { return "health probe rollback" }

// Report 跑数据库、磁盘、worker 心跳、任务积压。detail 为假时去掉详情。
func Report(ctx context.Context, d *db.DB, dataDir string, now time.Time, detail bool) Result {
	checks := map[string]Check{
		"database":         checkDatabase(ctx, d),
		"disk":             checkDisk(dataDir),
		"worker_heartbeat": checkHeartbeat(ctx, d, now),
		"task_backlog":     checkBacklog(ctx, d, now),
	}
	ok := true
	for _, c := range checks {
		if !c.OK {
			ok = false
		}
	}
	if !detail {
		for name, c := range checks {
			c.Detail = ""
			checks[name] = c
		}
	}
	status := "ok"
	if !ok {
		status = "error"
	}
	return Result{Status: status, Checks: checks, OK: ok}
}

func checkDatabase(ctx context.Context, d *db.DB) Check {
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, `INSERT INTO health_probe (token) VALUES ('__healthz__')`); err != nil {
			return err
		}
		var n int
		if err := tx.QueryRowContext(ctx, `SELECT COUNT(*) FROM health_probe WHERE token = '__healthz__'`).Scan(&n); err != nil {
			return err
		}
		if n != 1 {
			return fmt.Errorf("database write did not persist")
		}
		return probeRollback{}
	})
	if errors.Is(err, probeRollback{}) {
		return Check{OK: true, Detail: "ok"}
	}
	if err == nil {
		return Check{OK: false, Detail: "probe committed"}
	}
	return Check{OK: false, Detail: err.Error()}
}

func checkDisk(path string) Check {
	free, total, err := readDisk(path)
	if err != nil {
		return Check{OK: false, Detail: err.Error()}
	}
	if total == 0 || free*5 <= total {
		ratio := 0.0
		if total > 0 {
			ratio = float64(free) / float64(total)
		}
		return Check{OK: false, Detail: fmt.Sprintf("free space %.1f%% is at or below %.0f%%", ratio*100, DiskMinFree*100)}
	}
	ratio := float64(free) / float64(total)
	return Check{OK: true, Detail: fmt.Sprintf("free space %.1f%%", ratio*100)}
}

var readDisk = statDisk

func statDisk(path string) (free, total uint64, err error) {
	var st syscall.Statfs_t
	if err = syscall.Statfs(path, &st); err != nil {
		return 0, 0, err
	}
	return uint64(st.Bavail) * uint64(st.Bsize), uint64(st.Blocks) * uint64(st.Bsize), nil
}

func checkHeartbeat(ctx context.Context, d *db.DB, now time.Time) Check {
	var raw string
	err := d.ReadPool().QueryRowContext(ctx, `SELECT heartbeat_at FROM worker_status WHERE id = 1`).Scan(&raw)
	if err != nil {
		return Check{OK: false, Detail: "心跳缺失"}
	}
	stamp, err := db.ParseUTC(raw)
	if err != nil {
		return Check{OK: false, Detail: "心跳无效"}
	}
	age := now.Sub(stamp)
	if age > HeartbeatStale {
		return Check{OK: false, Detail: fmt.Sprintf("心跳过期（%d 秒未更新）", int(age.Seconds()))}
	}
	return Check{OK: true, Detail: fmt.Sprintf("ok (%ds ago)", int(age.Seconds()))}
}

func checkBacklog(ctx context.Context, d *db.DB, now time.Time) Check {
	var n int
	cutoff := db.FormatUTC(now.Add(-BacklogAfter))
	err := d.ReadPool().QueryRowContext(ctx, `SELECT COUNT(*) FROM jobs
		WHERE status = 'ready' AND run_after < ?`, cutoff).Scan(&n)
	if err != nil {
		return Check{OK: false, Detail: err.Error()}
	}
	if n > 0 {
		return Check{OK: false, Detail: fmt.Sprintf("%d 个任务等待超过 10 分钟", n)}
	}
	return Check{OK: true, Detail: "ok"}
}

// Handler 是 GET /healthz。detail 决定这次请求能不能看详情。
func Handler(d *db.DB, dataDir string, now func() time.Time, detail func(*http.Request) bool) http.Handler {
	if now == nil {
		now = time.Now
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		see := false
		if detail != nil {
			see = detail(r)
		}
		result := Report(r.Context(), d, dataDir, now().UTC(), see)
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		if !result.OK {
			w.WriteHeader(http.StatusServiceUnavailable)
		}
		_ = json.NewEncoder(w).Encode(result)
	})
}
