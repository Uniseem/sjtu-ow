package jobs

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Cleanup 是每天 04:00 里、这张库现在就有的那一部分（5.10）：
// 做完超过 30 天的任务、过期会话、超过 24 小时的幂等回执、48 小时前的限流桶。
// 入队申请、空草稿那些表还没有，不在这里。
func Cleanup(ctx context.Context, d *db.DB, now time.Time) error {
	return d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, `DELETE FROM jobs
			WHERE status IN ('done', 'failed') AND finished_at < ?`,
			db.FormatUTC(now.Add(-30*24*time.Hour))); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `DELETE FROM sessions WHERE expires_at < ?`,
			db.FormatUTC(now)); err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, `DELETE FROM idempotency_keys WHERE created_at < ?`,
			db.FormatUTC(now.Add(-24*time.Hour))); err != nil {
			return err
		}
		cutoff := now.Add(-48 * time.Hour).UTC().Format("20060102T1504")
		_, err := tx.ExecContext(ctx, `DELETE FROM rate_counters
			WHERE substr(bucket, instr(bucket, '|') + 1) < ?`, cutoff)
		return err
	})
}
