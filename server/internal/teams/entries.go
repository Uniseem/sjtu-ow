package teams

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// PublicEntry only exposes an approved registration's event and lifecycle.
// Drafts, submission notes and roster snapshots stay out of the team page.
type PublicEntry struct {
	ID           int64  `json:"id"`
	TournamentID int64  `json:"tournament_id"`
	Title        string `json:"title"`
	Status       string `json:"status"`
}

func (s *Service) publicEntries(ctx context.Context, q db.DBTX, teamID int64) ([]PublicEntry, error) {
	rows, err := q.QueryContext(ctx, `SELECT r.id,t.id,t.title,t.status FROM registrations r JOIN tournaments t ON t.id=r.tournament_id
 WHERE r.team_id=? AND r.status='approved' AND t.status<>'draft' ORDER BY t.registration_closes_at DESC,r.id DESC`, teamID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []PublicEntry{}
	for rows.Next() {
		var entry PublicEntry
		if err := rows.Scan(&entry.ID, &entry.TournamentID, &entry.Title, &entry.Status); err != nil {
			return nil, err
		}
		out = append(out, entry)
	}
	return out, rows.Err()
}
