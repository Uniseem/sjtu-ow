package jobs

import (
	"context"
	"errors"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newDB(t *testing.T) *db.DB {
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

func TestEnqueueClaimAndMailRetry(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 1, 0, 0, 0, time.UTC)
	var id int64
	if err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var err error
		id, err = Enqueue(ctx, tx, Job{Kind: "send_mail", Lane: LaneMail, Args: `{"n":1}`}, now)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	w := New(d, nil)
	w.Handle("send_mail", func(context.Context, *db.DB, Job) error {
		return errors.New("smtp down")
	})
	if err := w.Lock(ctx, now); err != nil {
		t.Fatal(err)
	}
	if err := w.Tick(ctx, now); err != nil {
		t.Fatal(err)
	}
	j := mustLoad(t, d, id)
	if j.Status != StatusReady || j.Attempts != 1 || !j.RunAfter.Equal(now.Add(time.Minute)) {
		t.Fatalf("第一次失败应 1 分钟后重试：status=%s attempts=%d due=%s", j.Status, j.Attempts, j.RunAfter)
	}
	if err := w.Tick(ctx, now.Add(time.Minute)); err != nil {
		t.Fatal(err)
	}
	j = mustLoad(t, d, id)
	if !j.RunAfter.Equal(now.Add(time.Minute).Add(5*time.Minute)) || j.Attempts != 2 {
		t.Fatalf("第二次应再等 5 分钟：attempts=%d due=%s", j.Attempts, j.RunAfter)
	}
	if err := w.Tick(ctx, j.RunAfter); err != nil {
		t.Fatal(err)
	}
	j = mustLoad(t, d, id)
	if err := w.Tick(ctx, j.RunAfter); err != nil {
		t.Fatal(err)
	}
	j = mustLoad(t, d, id)
	if j.Status != StatusFailed || j.Attempts != 4 {
		t.Fatalf("三次重试之后应失败：status=%s attempts=%d err=%s", j.Status, j.Attempts, j.LastError)
	}
}

func TestEnqueueOnceSkipsSameOrEarlier(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 2, 0, 0, 0, time.UTC)
	later := now.Add(time.Hour)
	var first int64
	var inserted bool
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var err error
		first, inserted, err = EnqueueOnce(ctx, tx, Job{Kind: "remind", Lane: LaneDefault, DedupeKey: "remind:1", RunAfter: later}, now, true)
		return err
	})
	if err != nil || !inserted {
		t.Fatalf("第一条应排上：id=%d inserted=%v err=%v", first, inserted, err)
	}
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		id, ins, err := EnqueueOnce(ctx, tx, Job{Kind: "remind", Lane: LaneDefault, DedupeKey: "remind:1", RunAfter: later}, now, false)
		if err != nil || ins || id != first {
			t.Fatalf("同一时刻不应再排：id=%d inserted=%v err=%v", id, ins, err)
		}
		id, ins, err = EnqueueOnce(ctx, tx, Job{Kind: "remind", Lane: LaneDefault, DedupeKey: "remind:1", RunAfter: later.Add(time.Hour)}, now, true)
		if err != nil || ins || id != first {
			t.Fatalf("已有更早的一条就够了：id=%d inserted=%v err=%v", id, ins, err)
		}
		_, ins, err = EnqueueOnce(ctx, tx, Job{Kind: "remind", Lane: LaneDefault, DedupeKey: "remind:1", RunAfter: now}, now, false)
		if err != nil || !ins {
			t.Fatalf("没有 earlierCounts 时更早的一条应另排：inserted=%v err=%v", ins, err)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestSecondWorkerBusyAndResetRunning(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	var id int64
	if err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var err error
		id, err = Enqueue(ctx, tx, Job{Kind: "slow_job", Lane: LaneSlow}, now)
		if err != nil {
			return err
		}
		_, err = tx.ExecContext(ctx, `UPDATE jobs SET status = 'running' WHERE id = ?`, id)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	w := New(d, nil)
	if err := w.Lock(ctx, now); err != nil {
		t.Fatal(err)
	}
	j := mustLoad(t, d, id)
	if j.Status != StatusReady {
		t.Fatalf("启动应把 running 放回 ready，得到 %s", j.Status)
	}
	other := New(d, nil)
	err := other.Lock(ctx, now.Add(time.Minute))
	if !errors.Is(err, ErrBusy) {
		t.Fatalf("第二个应起不来：%v", err)
	}
	if err := other.Lock(ctx, now.Add(LockStale+time.Second)); err != nil {
		t.Fatalf("心跳断了应能接手：%v", err)
	}
}

func TestSchedulesCatchUpOnce(t *testing.T) {
	loc := shanghai
	thuEarly := time.Date(2026, 10, 8, 2, 0, 0, 0, loc)
	if !Due(SchedBackup, thuEarly, time.Time{}) {
		t.Fatal("第一次启动应补跑错过的备份")
	}
	if Due(SchedBackup, thuEarly.Add(time.Minute), thuEarly) {
		t.Fatal("刚补跑过不应再跑")
	}
	atThree := time.Date(2026, 10, 8, 3, 0, 0, 0, loc)
	if !Due(SchedBackup, atThree, thuEarly) {
		t.Fatal("当天 03:00 应再跑")
	}
	sunEarly := time.Date(2026, 10, 11, 4, 29, 0, 0, loc)
	if Due(SchedOptimize, sunEarly, thuEarly) {
		t.Fatal("周日 04:30 之前不应跑优化")
	}
	sun := time.Date(2026, 10, 11, 4, 30, 0, 0, loc)
	if !Due(SchedOptimize, sun, thuEarly) {
		t.Fatal("周日 04:30 应跑优化")
	}
	if !Due(SchedPublish, thuEarly, time.Time{}) || Due(SchedPublish, thuEarly.Add(10*time.Second), thuEarly) {
		t.Fatal("30 秒的项应隔 30 秒")
	}
	if !Due(SchedPublish, thuEarly.Add(30*time.Second), thuEarly) {
		t.Fatal("满 30 秒应再跑")
	}
}

func TestClaimPrefersHigherPriority(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 5, 0, 0, 0, time.UTC)
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := Enqueue(ctx, tx, Job{Kind: "low", Lane: LaneMail, Priority: 0}, now); err != nil {
			return err
		}
		_, err := Enqueue(ctx, tx, Job{Kind: "high", Lane: LaneMail, Priority: 5}, now)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	var kind string
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		j, ok, err := Claim(ctx, tx, LaneMail, now)
		if err != nil || !ok {
			return err
		}
		kind = j.Kind
		return nil
	})
	if err != nil || kind != "high" {
		t.Fatalf("应先取优先级高的，得到 %s err=%v", kind, err)
	}
}

func TestCleanupDropsExpired(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 4, 0, 0, 0, time.UTC)
	old := db.FormatUTC(now.Add(-40 * 24 * time.Hour))
	fresh := db.FormatUTC(now.Add(-time.Hour))
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, `INSERT INTO jobs
			(kind, args, lane, run_after, status, created_at, finished_at)
			VALUES ('x', '{}', 'slow', ?, 'done', ?, ?)`, old, old, old); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO jobs
			(kind, args, lane, run_after, status, created_at, finished_at)
			VALUES ('y', '{}', 'slow', ?, 'done', ?, ?)`, fresh, fresh, fresh); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO sessions
			(token_hash, user_id, created_at, expires_at, last_seen_at)
			VALUES ('old', 1, ?, ?, ?)`, old, old, old); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO sessions
			(token_hash, user_id, created_at, expires_at, last_seen_at)
			VALUES ('new', 1, ?, ?, ?)`, fresh, db.FormatUTC(now.Add(time.Hour)), fresh); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO idempotency_keys
			(user_id, key, method, path, status, created_at)
			VALUES (1, 'k', 'POST', '/x', 200, ?)`, db.FormatUTC(now.Add(-25*time.Hour))); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO rate_counters (key, bucket, count)
			VALUES ('ip:1', 'search|20261001T0000', 1)`); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, `INSERT INTO rate_counters (key, bucket, count)
			VALUES ('ip:1', 'search|20261008T0300', 1)`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := Cleanup(ctx, d, now); err != nil {
		t.Fatal(err)
	}
	if n := count(t, d, `SELECT count(*) FROM jobs`); n != 1 {
		t.Fatalf("应只留下 30 天内做完的任务，得到 %d", n)
	}
	if n := count(t, d, `SELECT count(*) FROM sessions`); n != 1 {
		t.Fatalf("过期会话应删掉，得到 %d", n)
	}
	if n := count(t, d, `SELECT count(*) FROM idempotency_keys`); n != 0 {
		t.Fatalf("过期回执应删掉，得到 %d", n)
	}
	if n := count(t, d, `SELECT count(*) FROM rate_counters`); n != 1 {
		t.Fatalf("只应删旧桶，得到 %d", n)
	}
}

func mustLoad(t *testing.T, d *db.DB, id int64) Job {
	t.Helper()
	var j Job
	err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		var err error
		j, err = load(ctx, tx, id)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	return j
}

func count(t *testing.T, d *db.DB, q string) int {
	t.Helper()
	var n int
	if err := d.ReadPool().QueryRow(q).Scan(&n); err != nil {
		t.Fatal(err)
	}
	return n
}
