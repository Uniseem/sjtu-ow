// Package idempotency 实现幂等键（12 号文档 5.5）：同一个人同一个键 24 小时内
// 重放直接返回当时的回执；认领先行防双击。「存好了但回答丢了」的请求重试时
// 拿到的还是当时的回执，不会把动作做两遍。
package idempotency

import (
	"context"
	"database/sql"
	"errors"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// TTL 是幂等回执的保留时长（5.5：24 小时）。
const TTL = 24 * time.Hour

// Claim 的四种结果。
type Outcome int

const (
	// Created：认领成功，请求去处理，完了 Complete（出错就 Release）。
	Created Outcome = iota
	// Replay：这个键已经处理完，回执在 receipt 里，原样回给客户端。
	Replay
	// Busy：同一个键的上一个请求还在处理（双击、并发重发）。
	Busy
	// Mismatch：这个键用过别的地址，多半是客户端生成键的方式有毛病。
	Mismatch
)

// Receipt 是存下来的回执。
type Receipt struct {
	Status int
	Body   []byte
}

// Store 是幂等键的存储。
type Store struct {
	db    *db.DB
	clock clock.Clock
}

// NewStore 造一个存储；clock 注入让测试冻结时间。
func NewStore(d *db.DB, c clock.Clock) *Store {
	if c == nil {
		c = clock.System{}
	}
	return &Store{db: d, clock: c}
}

// Claim 认领一个键。receipt 只在 Outcome==Replay 时非空。
func (s *Store) Claim(ctx context.Context, userID int64, key, method, path string) (Outcome, *Receipt, error) {
	now := s.clock.Now()
	outcome := Created
	var receipt *Receipt
	err := s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var status int
		var body, m, p, createdAt string
		err := tx.QueryRowContext(ctx,
			`SELECT status, response, method, path, created_at FROM idempotency_keys
			 WHERE user_id = ? AND key = ?`, userID, key).
			Scan(&status, &body, &m, &p, &createdAt)
		if errors.Is(err, sql.ErrNoRows) {
			_, err = tx.ExecContext(ctx, `INSERT INTO idempotency_keys
				(user_id, key, method, path, status, response, created_at)
				VALUES (?, ?, ?, ?, 0, '', ?)`, userID, key, method, path, db.FormatUTC(now))
			return err
		}
		if err != nil {
			return err
		}

		created, perr := db.ParseUTC(createdAt)
		if perr == nil && now.Sub(created) > TTL {
			// 过期的键重新用：整行换成本次请求的
			_, err = tx.ExecContext(ctx, `UPDATE idempotency_keys
				SET method = ?, path = ?, status = 0, response = '', created_at = ?
				WHERE user_id = ? AND key = ?`, method, path, db.FormatUTC(now), userID, key)
			return err
		}
		if m != method || p != path {
			outcome = Mismatch
			return nil
		}
		if status == 0 {
			outcome = Busy
			return nil
		}
		outcome = Replay
		receipt = &Receipt{Status: status, Body: []byte(body)}
		return nil
	})
	if err != nil {
		return Created, nil, err
	}
	return outcome, receipt, nil
}

// Complete 把回执写进认领的行（只写 status=0 的那行）。
func (s *Store) Complete(ctx context.Context, userID int64, key string, status int, body []byte) error {
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `UPDATE idempotency_keys
			SET status = ?, response = ?, created_at = ?
			WHERE user_id = ? AND key = ? AND status = 0`,
			status, string(body), db.FormatUTC(s.clock.Now()), userID, key)
		return err
	})
}

// Release 释放处理出错的那行认领，让同一个键的重试还能进行。
func (s *Store) Release(ctx context.Context, userID int64, key string) error {
	return s.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, `DELETE FROM idempotency_keys
			WHERE user_id = ? AND key = ? AND status = 0`, userID, key)
		return err
	})
}
