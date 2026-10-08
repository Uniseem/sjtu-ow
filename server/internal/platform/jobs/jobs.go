// Package jobs 是任务队列（12 号文档 5.10）。三条车道各取各的，慢活挡不住验证码。
// 写进调用方已经打开的事务里，这样「改了数据」和「排了任务」一起提交。
package jobs

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const (
	LaneMail    = "mail"
	LaneDefault = "default"
	LaneSlow    = "slow"

	StatusReady   = "ready"
	StatusRunning = "running"
	StatusDone    = "done"
	StatusFailed  = "failed"
)

// MailRetryDelays 是邮件失败后的三次等待：1 分钟、5 分钟、30 分钟（设计 10.1）。
var MailRetryDelays = []time.Duration{time.Minute, 5 * time.Minute, 30 * time.Minute}

// Job 是排进队列的一件事。Args 是 JSON 文本。DedupeKey 空着表示不参与去重。
type Job struct {
	ID        int64
	Kind      string
	Args      string
	Lane      string
	Priority  int
	RunAfter  time.Time
	Status    string
	Attempts  int
	LastError string
	DedupeKey string
	CreatedAt time.Time
	StartedAt time.Time
	Finished  time.Time
}

// Enqueue 插入一条 ready。RunAfter 是零就用 now。
func Enqueue(ctx context.Context, tx *db.Tx, j Job, now time.Time) (int64, error) {
	if err := checkJob(j); err != nil {
		return 0, err
	}
	if j.Args == "" {
		j.Args = "{}"
	}
	if j.RunAfter.IsZero() {
		j.RunAfter = now
	}
	var dedupe any
	if j.DedupeKey != "" {
		dedupe = j.DedupeKey
	}
	var id int64
	err := tx.QueryRowContext(ctx, `INSERT INTO jobs
		(kind, args, lane, priority, run_after, status, dedupe_key, created_at)
		VALUES (?, ?, ?, ?, ?, 'ready', ?, ?)
		RETURNING id`,
		j.Kind, j.Args, j.Lane, j.Priority, db.FormatUTC(j.RunAfter), dedupe, db.FormatUTC(now),
	).Scan(&id)
	return id, err
}

// EnqueueOnce 在已经有一条同样 dedupe_key、状态是 ready 的时候可能不排。
// 到期时间相同，不排。earlierCounts 时，已有一条不晚于这次的，也不排
// （提醒类任务自己会看数据、时间后移就顺延）。返回的 inserted 为假时 id 是已有的那条。
func EnqueueOnce(ctx context.Context, tx *db.Tx, j Job, now time.Time, earlierCounts bool) (id int64, inserted bool, err error) {
	if j.DedupeKey == "" {
		return 0, false, errors.New("enqueue_once 要有 dedupe_key")
	}
	if err := checkJob(j); err != nil {
		return 0, false, err
	}
	if j.RunAfter.IsZero() {
		j.RunAfter = now
	}
	rows, err := tx.QueryContext(ctx, `SELECT id, run_after FROM jobs
		WHERE dedupe_key = ? AND status = 'ready'`, j.DedupeKey)
	if err != nil {
		return 0, false, err
	}
	type waiting struct {
		id  int64
		due time.Time
	}
	var found []waiting
	for rows.Next() {
		var existing int64
		var dueText string
		if err := rows.Scan(&existing, &dueText); err != nil {
			_ = rows.Close()
			return 0, false, err
		}
		due, err := db.ParseUTC(dueText)
		if err != nil {
			_ = rows.Close()
			return 0, false, err
		}
		found = append(found, waiting{existing, due})
	}
	err = rows.Err()
	_ = rows.Close()
	if err != nil {
		return 0, false, err
	}
	for _, w := range found {
		if w.due.Equal(j.RunAfter) || (earlierCounts && !w.due.After(j.RunAfter)) {
			return w.id, false, nil
		}
	}
	id, err = Enqueue(ctx, tx, j, now)
	return id, err == nil, err
}

func checkJob(j Job) error {
	switch j.Lane {
	case LaneMail, LaneDefault, LaneSlow:
	default:
		return fmt.Errorf("不认识的车道 %q", j.Lane)
	}
	if j.Kind == "" {
		return errors.New("任务没有 kind")
	}
	return nil
}

// ResetRunning 把上次进程杀掉时留下的 running 放回 ready。可能重做（5.10）。
func ResetRunning(ctx context.Context, tx *db.Tx) error {
	_, err := tx.ExecContext(ctx, `UPDATE jobs SET status = 'ready', started_at = NULL WHERE status = 'running'`)
	return err
}

// Claim 取这条车道上一条已经到期的任务，标成 running，attempts 加一。没有就 ok=false。
func Claim(ctx context.Context, tx *db.Tx, lane string, now time.Time) (Job, bool, error) {
	var id int64
	err := tx.QueryRowContext(ctx, `SELECT id FROM jobs
		WHERE lane = ? AND status = 'ready' AND run_after <= ?
		ORDER BY priority DESC, run_after, id
		LIMIT 1`, lane, db.FormatUTC(now)).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return Job{}, false, nil
	}
	if err != nil {
		return Job{}, false, err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE jobs
		SET status = 'running', attempts = attempts + 1, started_at = ?
		WHERE id = ?`, db.FormatUTC(now), id); err != nil {
		return Job{}, false, err
	}
	j, err := load(ctx, tx, id)
	if err != nil {
		return Job{}, false, err
	}
	return j, true, nil
}

func load(ctx context.Context, tx *db.Tx, id int64) (Job, error) {
	var j Job
	var runAfter, created string
	var dedupe, started, finished sql.NullString
	err := tx.QueryRowContext(ctx, `SELECT id, kind, args, lane, priority, run_after, status, attempts,
			last_error, dedupe_key, created_at, started_at, finished_at
		FROM jobs WHERE id = ?`, id).Scan(
		&j.ID, &j.Kind, &j.Args, &j.Lane, &j.Priority, &runAfter, &j.Status, &j.Attempts,
		&j.LastError, &dedupe, &created, &started, &finished,
	)
	if err != nil {
		return Job{}, err
	}
	j.RunAfter, err = db.ParseUTC(runAfter)
	if err != nil {
		return Job{}, err
	}
	j.CreatedAt, err = db.ParseUTC(created)
	if err != nil {
		return Job{}, err
	}
	if dedupe.Valid {
		j.DedupeKey = dedupe.String
	}
	if started.Valid {
		j.StartedAt, err = db.ParseUTC(started.String)
		if err != nil {
			return Job{}, err
		}
	}
	if finished.Valid {
		j.Finished, err = db.ParseUTC(finished.String)
		if err != nil {
			return Job{}, err
		}
	}
	return j, nil
}

// Succeed 把任务标成做完。
func Succeed(ctx context.Context, tx *db.Tx, id int64, now time.Time) error {
	_, err := tx.ExecContext(ctx, `UPDATE jobs SET status = 'done', finished_at = ?, last_error = '' WHERE id = ?`,
		db.FormatUTC(now), id)
	return err
}

// Fail 记下错误。邮件按 1/5/30 分钟再排，三次之后放弃；别的车道一次就失败。
func Fail(ctx context.Context, tx *db.Tx, id int64, now time.Time, cause error) error {
	msg := ""
	if cause != nil {
		msg = cause.Error()
	}
	j, err := load(ctx, tx, id)
	if err != nil {
		return err
	}
	if j.Lane == LaneMail {
		n := j.Attempts - 1 // 这次失败是第几次（认领时已经加过）
		if n >= 0 && n < len(MailRetryDelays) {
			_, err = tx.ExecContext(ctx, `UPDATE jobs
				SET status = 'ready', run_after = ?, last_error = ?, started_at = NULL
				WHERE id = ?`, db.FormatUTC(now.Add(MailRetryDelays[n])), msg, id)
			return err
		}
	}
	_, err = tx.ExecContext(ctx, `UPDATE jobs SET status = 'failed', finished_at = ?, last_error = ? WHERE id = ?`,
		db.FormatUTC(now), msg, id)
	return err
}
