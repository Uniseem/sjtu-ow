// Package audit 是操作记录（设计 15.5，12 号文档 7）：统一一张表，谁、做了什么、对哪个对象、带什么数据。
// 写在调用方的事务里，业务和记录一起提交或一起回滚。
package audit

import (
	"context"
	"encoding/json"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Entry 是一条操作记录。
type Entry struct {
	ID         int64           `json:"id"`
	ActorID    *int64          `json:"actor_id"`
	Action     string          `json:"action"`
	ObjectType string          `json:"object_type"`
	ObjectID   int64           `json:"object_id"`
	Data       json.RawMessage `json:"data"`
	CreatedAt  time.Time       `json:"created_at"`
}

// Record 记一条。actor 为 0 表示系统。data 可以是 nil，也可以是任何能转成 JSON 的东西。
func Record(ctx context.Context, tx *db.Tx, actor int64, action, objectType string, objectID int64, data any, at time.Time) error {
	raw := []byte("{}")
	if data != nil {
		b, err := json.Marshal(data)
		if err != nil {
			return err
		}
		raw = b
	}
	var by any
	if actor > 0 {
		by = actor
	}
	_, err := tx.ExecContext(ctx, `INSERT INTO audit_log (actor_id, action, object_type, object_id, data, created_at)
		VALUES (?, ?, ?, ?, ?, ?)`, by, action, objectType, objectID, string(raw), db.FormatUTC(at))
	return err
}

// For 读某个对象的全部记录，旧的在前。
func For(ctx context.Context, q db.DBTX, objectType string, objectID int64) ([]Entry, error) {
	rows, err := q.QueryContext(ctx, `SELECT id, actor_id, action, object_type, object_id, data, created_at
		FROM audit_log WHERE object_type = ? AND object_id = ? ORDER BY id`, objectType, objectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []Entry{}
	for rows.Next() {
		var e Entry
		var actor *int64
		var data, at string
		if err := rows.Scan(&e.ID, &actor, &e.Action, &e.ObjectType, &e.ObjectID, &data, &at); err != nil {
			return nil, err
		}
		e.ActorID, e.Data = actor, json.RawMessage(data)
		e.CreatedAt, _ = db.ParseUTC(at)
		out = append(out, e)
	}
	return out, rows.Err()
}
