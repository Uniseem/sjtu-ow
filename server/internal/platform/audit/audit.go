// Package audit 是操作记录（设计 15.5，12 号文档 7）：统一一张表，谁、做了什么、对哪个对象、带什么数据。
// 写在调用方的事务里，业务和记录一起提交或一起回滚。
package audit

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
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

// EntryWithActor 附带操作人基础信息。
type EntryWithActor struct {
	Entry
	ActorNickname string `json:"actor_nickname"`
	ActorEmail    string `json:"actor_email"`
}

// QueryInput 是查询审计日志的条件。
type QueryInput struct {
	Action     string
	ActorID    *int64
	ObjectType string
	Since      *time.Time
	Until      *time.Time
	Page       int
	PageSize   int
}

// QueryResult 是分页查询结果。
type QueryResult struct {
	Items    []EntryWithActor `json:"items"`
	Total    int              `json:"total"`
	Page     int              `json:"page"`
	PageSize int              `json:"page_size"`
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

// Query 分页查询审计日志，新的在前。
func Query(ctx context.Context, q db.DBTX, in QueryInput) (*QueryResult, error) {
	page := in.Page
	if page < 1 {
		page = 1
	}
	pageSize := in.PageSize
	if pageSize < 1 {
		pageSize = 50
	}
	if pageSize > 100 {
		pageSize = 100
	}

	var where []string
	var args []any

	if in.Action != "" {
		where = append(where, "a.action = ?")
		args = append(args, in.Action)
	}
	if in.ActorID != nil && *in.ActorID > 0 {
		where = append(where, "a.actor_id = ?")
		args = append(args, *in.ActorID)
	}
	if in.ObjectType != "" {
		where = append(where, "a.object_type = ?")
		args = append(args, in.ObjectType)
	}
	if in.Since != nil && !in.Since.IsZero() {
		where = append(where, "a.created_at >= ?")
		args = append(args, db.FormatUTC(*in.Since))
	}
	if in.Until != nil && !in.Until.IsZero() {
		where = append(where, "a.created_at < ?")
		args = append(args, db.FormatUTC(*in.Until))
	}

	whereClause := ""
	if len(where) > 0 {
		whereClause = "WHERE " + strings.Join(where, " AND ")
	}

	var total int
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM audit_log a %s", whereClause)
	if err := q.QueryRowContext(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, fmt.Errorf("统计审计日志总数失败: %w", err)
	}

	query := fmt.Sprintf(`
		SELECT a.id, a.actor_id, a.action, a.object_type, a.object_id, a.data, a.created_at,
		       COALESCE(u.nickname, ''), COALESCE(u.email, '')
		FROM audit_log a
		LEFT JOIN users u ON u.id = a.actor_id
		%s
		ORDER BY a.id DESC
		LIMIT ? OFFSET ?
	`, whereClause)

	limitArgs := append(args, pageSize, (page-1)*pageSize)
	rows, err := q.QueryContext(ctx, query, limitArgs...)
	if err != nil {
		return nil, fmt.Errorf("查询审计日志列表失败: %w", err)
	}
	defer rows.Close()

	items := make([]EntryWithActor, 0, pageSize)
	for rows.Next() {
		var item EntryWithActor
		var actorID sql.NullInt64
		var dataStr, atStr string

		if err := rows.Scan(
			&item.ID, &actorID, &item.Action, &item.ObjectType, &item.ObjectID,
			&dataStr, &atStr, &item.ActorNickname, &item.ActorEmail,
		); err != nil {
			return nil, err
		}

		if actorID.Valid {
			v := actorID.Int64
			item.ActorID = &v
		}
		item.Data = json.RawMessage(dataStr)
		item.CreatedAt, _ = db.ParseUTC(atStr)
		items = append(items, item)
	}

	return &QueryResult{
		Items:    items,
		Total:    total,
		Page:     page,
		PageSize: pageSize,
	}, rows.Err()
}
