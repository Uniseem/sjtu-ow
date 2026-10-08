package jobs

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Handler 做一件任务。不要在里面再开 WriteTx 的同时假定外层还占着事务：
// 调用时写锁是放开的。
type Handler func(ctx context.Context, d *db.DB, j Job) error

// ScheduleHandler 做一项定时的事。没有注册的项，到点只记下「跑过」。
type ScheduleHandler func(ctx context.Context, d *db.DB, now time.Time) error

// Worker 是一个进程里的那一个 worker。第二个 TryLock 会得到 ErrBusy。
type Worker struct {
	db       *db.DB
	clock    clock.Clock
	owner    string
	handlers map[string]Handler
	sched    map[string]ScheduleHandler
}

func New(d *db.DB, c clock.Clock) *Worker {
	if c == nil {
		c = clock.System{}
	}
	var buf [8]byte
	_, _ = rand.Read(buf[:])
	w := &Worker{
		db:       d,
		clock:    c,
		owner:    hex.EncodeToString(buf[:]),
		handlers: map[string]Handler{},
		sched: map[string]ScheduleHandler{
			SchedCleanup:  Cleanup,
			SchedOptimize: optimize,
		},
	}
	return w
}

func optimize(ctx context.Context, d *db.DB, _ time.Time) error {
	if _, err := d.WritePool().ExecContext(ctx, `PRAGMA optimize`); err != nil {
		return err
	}
	_, err := d.WritePool().ExecContext(ctx, `PRAGMA wal_checkpoint(TRUNCATE)`)
	return err
}

// Handle 注册某种 kind 的处理函数。同名后来的覆盖前面的。
func (w *Worker) Handle(kind string, h Handler) { w.handlers[kind] = h }

// OnSchedule 注册一项定时的事。
func (w *Worker) OnSchedule(name string, h ScheduleHandler) { w.sched[name] = h }

// Lock 占住 worker 锁，并把上次留下的 running 放回队列。
func (w *Worker) Lock(ctx context.Context, now time.Time) error {
	return w.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if err := TryLock(ctx, tx, w.owner, now); err != nil {
			return err
		}
		return ResetRunning(ctx, tx)
	})
}

// Run 占锁后按 every 做一轮，直到 ctx 取消。every 为零时用 1 秒。
func (w *Worker) Run(ctx context.Context, every time.Duration) error {
	if every <= 0 {
		every = time.Second
	}
	if err := w.Lock(ctx, w.clock.Now()); err != nil {
		return err
	}
	ticker := time.NewTicker(every)
	defer ticker.Stop()
	for {
		if err := w.Tick(ctx, w.clock.Now()); err != nil {
			slog.Error("worker 这一轮没做完", "err", err.Error())
		}
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

// Tick 做一轮：续心跳、每条车道取一件事、到点的定时项。
func (w *Worker) Tick(ctx context.Context, now time.Time) error {
	if err := w.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		return Heartbeat(ctx, tx, w.owner, now)
	}); err != nil {
		return err
	}
	var errs []error
	for _, lane := range []string{LaneMail, LaneDefault, LaneSlow} {
		if err := w.drainOne(ctx, lane, now); err != nil {
			errs = append(errs, err)
		}
	}
	if err := w.runSchedules(ctx, now); err != nil {
		errs = append(errs, err)
	}
	return errors.Join(errs...)
}

func (w *Worker) drainOne(ctx context.Context, lane string, now time.Time) error {
	var job Job
	var ok bool
	err := w.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var err error
		job, ok, err = Claim(ctx, tx, lane, now)
		return err
	})
	if err != nil || !ok {
		return err
	}
	h := w.handlers[job.Kind]
	var cause error
	if h == nil {
		cause = fmt.Errorf("没有处理函数 %s", job.Kind)
	} else {
		cause = h(ctx, w.db, job)
	}
	return w.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if cause != nil {
			return Fail(ctx, tx, job.ID, now, cause)
		}
		return Succeed(ctx, tx, job.ID, now)
	})
}

func (w *Worker) runSchedules(ctx context.Context, now time.Time) error {
	last, err := w.loadRuns(ctx)
	if err != nil {
		return err
	}
	var errs []error
	for _, name := range []string{SchedPublish, SchedPatrol, SchedBackup, SchedCleanup, SchedOptimize, SchedAssets} {
		if !Due(name, now, last[name]) {
			continue
		}
		if h := w.sched[name]; h != nil {
			if err := h(ctx, w.db, now); err != nil {
				errs = append(errs, fmt.Errorf("%s: %w", name, err))
				continue
			}
		}
		if err := w.mark(ctx, name, now); err != nil {
			errs = append(errs, err)
		}
	}
	return errors.Join(errs...)
}

func (w *Worker) loadRuns(ctx context.Context) (map[string]time.Time, error) {
	out := map[string]time.Time{}
	rows, err := w.db.ReadPool().QueryContext(ctx, `SELECT name, last_run_at FROM schedule_runs`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var name, at string
		if err := rows.Scan(&name, &at); err != nil {
			return nil, err
		}
		t, err := db.ParseUTC(at)
		if err != nil {
			return nil, err
		}
		out[name] = t
	}
	return out, rows.Err()
}

func (w *Worker) mark(ctx context.Context, name string, now time.Time) error {
	return w.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `INSERT INTO schedule_runs (name, last_run_at) VALUES (?, ?)
			ON CONFLICT (name) DO UPDATE SET last_run_at = excluded.last_run_at`,
			name, db.FormatUTC(now))
		return err
	})
}
