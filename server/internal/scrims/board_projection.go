package scrims

import (
	"context"
	"database/sql"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// readBoardSnapshot avoids mixing a roster from one version with assignments
// from another during concurrent signup/administrator activity.
func (s *Service) readBoardSnapshot(ctx *app.Ctx, id int64, order string) (*Board, error) {
	viewer, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	snapshot, err := s.d.ReadPool().BeginTx(ctx.Context, &sql.TxOptions{ReadOnly: true})
	if err != nil {
		return nil, err
	}
	defer snapshot.Rollback()
	return s.buildBoard(ctx.Context, snapshot, id, order, viewer.HasCap(accounts.CapContactsView))
}

// Missing-state/deletion facts are always server projections, so action menus
// and confirmation controls need no inferred capabilities or placeholder rows.
type BoardMemberState struct {
	Active bool
	SJTU   bool
}

func (s *Service) memberStates(ctx context.Context, q interface {
	QueryContext(context.Context, string, ...any) (*sql.Rows, error)
}, id int64) (map[int64]BoardMemberState, error) {
	rows, err := q.QueryContext(ctx, `SELECT u.id, u.is_active, u.is_sjtu FROM users u
		JOIN scrim_signups signup ON signup.user_id = u.id WHERE signup.scrim_id = ?`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	states := map[int64]BoardMemberState{}
	for rows.Next() {
		var id int64
		var active, sjtu int
		if err := rows.Scan(&id, &active, &sjtu); err != nil {
			return nil, err
		}
		states[id] = BoardMemberState{Active: active == 1, SJTU: sjtu == 1}
	}
	return states, rows.Err()
}
