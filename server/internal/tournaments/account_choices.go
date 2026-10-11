package tournaments

import (
	"context"
	"database/sql"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// memberAccountChoices is used only after the form has established current
// captainship and loaded that team's members. Grouping in Go avoids exposing a
// search endpoint that could enumerate other members' private game IDs.
func memberAccountChoices(ctx context.Context, q db.DBTX, members []teamMember) (map[int64][]GameAccountChoice, error) {
	out := map[int64][]GameAccountChoice{}
	args := []any{}
	marks := []string{}
	for _, member := range members {
		out[member.UserID] = []GameAccountChoice{}
		args = append(args, member.UserID)
		marks = append(marks, "?")
	}
	if len(args) == 0 {
		return out, nil
	}
	rows, err := q.QueryContext(ctx, `SELECT user_id,id,battletag,rank_tank,rank_damage,rank_support FROM game_accounts
		WHERE user_id IN (`+strings.Join(marks, ",")+`) ORDER BY user_id,id`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var owner int64
		var choice GameAccountChoice
		var tank, damage, support sql.NullInt64
		if err := rows.Scan(&owner, &choice.ID, &choice.Battletag, &tank, &damage, &support); err != nil {
			return nil, err
		}
		for _, pair := range []struct {
			value  sql.NullInt64
			target **int
		}{{tank, &choice.RankTank}, {damage, &choice.RankDamage}, {support, &choice.RankSupport}} {
			if pair.value.Valid {
				value := int(pair.value.Int64)
				*pair.target = &value
			}
		}
		out[owner] = append(out[owner], choice)
	}
	return out, rows.Err()
}
