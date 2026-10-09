package accounts

import (
	"context"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// LoadGameAccounts 一次取一批人的游戏 ID（战队页、成员页给每个人算段位，不做 N+1）。
// q 可以是只读池，也可以是写事务。
func LoadGameAccounts(ctx context.Context, q db.DBTX, userIDs []int64) (map[int64][]GameAccount, error) {
	out := map[int64][]GameAccount{}
	if len(userIDs) == 0 {
		return out, nil
	}
	ph := strings.TrimSuffix(strings.Repeat("?,", len(userIDs)), ",")
	args := make([]any, len(userIDs))
	for i, id := range userIDs {
		args[i] = id
	}
	rows, err := q.QueryContext(ctx, `SELECT `+gameAccountCols+` FROM game_accounts
		WHERE user_id IN (`+ph+`) ORDER BY id`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		ga, err := scanGameAccount(rows)
		if err != nil {
			return nil, err
		}
		if ga != nil {
			out[ga.UserID] = append(out[ga.UserID], *ga)
		}
	}
	return out, rows.Err()
}
