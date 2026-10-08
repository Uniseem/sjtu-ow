package jobs

import (
	"context"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// LockStale 是心跳超过这么久就当这个 worker 已经死了，别人可以接手。
// 和 /healthz 的「120 秒没心跳」是同一个数（5.15）。
const LockStale = 120 * time.Second

// ErrBusy 表示已经有一个活着的 worker。
var ErrBusy = errors.New("已经有一个 worker 在跑")

// TryLock 占住唯一的那一行。自己重复来、或者上一任心跳已经断了，都能占上。
func TryLock(ctx context.Context, tx *db.Tx, owner string, now time.Time) error {
	stale := db.FormatUTC(now.Add(-LockStale))
	res, err := tx.ExecContext(ctx, `INSERT INTO worker_lock (id, owner, heartbeat_at)
		VALUES (1, ?, ?)
		ON CONFLICT (id) DO UPDATE SET
			owner = excluded.owner,
			heartbeat_at = excluded.heartbeat_at
		WHERE worker_lock.owner = excluded.owner
			OR worker_lock.heartbeat_at < ?`,
		owner, db.FormatUTC(now), stale)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrBusy
	}
	_, err = tx.ExecContext(ctx, `INSERT INTO worker_status (id, started_at, heartbeat_at)
		VALUES (1, ?, ?)
		ON CONFLICT (id) DO UPDATE SET
			started_at = excluded.started_at,
			heartbeat_at = excluded.heartbeat_at`,
		db.FormatUTC(now), db.FormatUTC(now))
	return err
}

// Heartbeat 续上锁，并写下 worker_status。锁不在自己手里就是 ErrBusy。
func Heartbeat(ctx context.Context, tx *db.Tx, owner string, now time.Time) error {
	res, err := tx.ExecContext(ctx, `UPDATE worker_lock SET heartbeat_at = ? WHERE id = 1 AND owner = ?`,
		db.FormatUTC(now), owner)
	if err != nil {
		return err
	}
	n, err := res.RowsAffected()
	if err != nil {
		return err
	}
	if n == 0 {
		return ErrBusy
	}
	_, err = tx.ExecContext(ctx, `UPDATE worker_status SET heartbeat_at = ? WHERE id = 1`, db.FormatUTC(now))
	return err
}

// Unlock 放开锁。不是自己占的就不动。
func Unlock(ctx context.Context, tx *db.Tx, owner string) error {
	_, err := tx.ExecContext(ctx, `DELETE FROM worker_lock WHERE id = 1 AND owner = ?`, owner)
	return err
}
