package tournaments

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// HomeCandidates 公开未结束赛事和最近结束的一场，照旧 home_tournaments。
func HomeCandidates(ctx context.Context, q db.DBTX) ([]*Tournament, error) {
	rows, err := q.QueryContext(ctx, `SELECT `+tournamentCols+` FROM tournaments WHERE status IN ('published','finished')
 ORDER BY CASE status WHEN 'published' THEN 0 ELSE 1 END,
 CASE WHEN status='finished' THEN starts_at ELSE registration_opens_at END DESC,
 registration_opens_at DESC,CASE WHEN status='published' THEN id END DESC,id ASC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []*Tournament{}
	finished := false
	for rows.Next() {
		t, err := scanTournament(rows)
		if err != nil {
			return nil, err
		}
		if t.Status == StatusFinished {
			if finished {
				continue
			}
			finished = true
		}
		out = append(out, t)
	}
	return out, rows.Err()
}
