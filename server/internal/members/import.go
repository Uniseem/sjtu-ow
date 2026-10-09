package members

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// ImportLegacyGroups 从现行站的 Django 库读成员分组两张表，编号原样沿用（导入顺序「战队 → 分组」）。
// legacy 要以只读方式打开；反复导入同一份库得到同样的结果，出错一律报出来。
func ImportLegacyGroups(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	now := db.FormatUTC(time.Now().UTC())
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		rows, err := legacy.QueryContext(ctx, `SELECT id, name, description, is_visible, sort_order
			FROM members_membergroup ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 members_membergroup：%w", err)
		}
		for rows.Next() {
			var id int64
			var name, desc string
			var visible, order int
			if err := rows.Scan(&id, &name, &desc, &visible, &order); err != nil {
				rows.Close()
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO member_groups
				(id, name, description, is_visible, sort_order, version, created_at, updated_at)
				VALUES (?, ?, ?, ?, ?, 1, ?, ?)
				ON CONFLICT (id) DO UPDATE SET name = excluded.name, description = excluded.description,
					is_visible = excluded.is_visible, sort_order = excluded.sort_order`,
				id, name, desc, visible, order, now, now); err != nil {
				rows.Close()
				return fmt.Errorf("写分组 %d：%w", id, err)
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		rows, err = legacy.QueryContext(ctx, `SELECT id, group_id, user_id, title, sort_order
			FROM members_membergroupmembership ORDER BY id`)
		if err != nil {
			return fmt.Errorf("读旧库 members_membergroupmembership：%w", err)
		}
		defer rows.Close()
		for rows.Next() {
			var id, groupID, userID int64
			var title string
			var order sql.NullInt64 // Wagtail 的 Orderable 允许空
			if err := rows.Scan(&id, &groupID, &userID, &title, &order); err != nil {
				return err
			}
			if _, err := tx.ExecContext(txCtx, `INSERT INTO member_group_memberships (id, group_id, user_id, title, sort_order)
				VALUES (?, ?, ?, ?, ?)
				ON CONFLICT (id) DO UPDATE SET title = excluded.title, sort_order = excluded.sort_order`,
				id, groupID, userID, title, order.Int64); err != nil {
				return fmt.Errorf("写分组成员 %d：%w", id, err)
			}
		}
		return rows.Err()
	})
}
