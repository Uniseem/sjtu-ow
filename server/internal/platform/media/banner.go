package media

import (
	"context"
	"fmt"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Banner projects the configured section picture without exposing settings.
// The identifier is selected from a fixed column allowlist, never user SQL.
func Banner(ctx context.Context, q db.DBTX, section string) (*int64, error) {
	columns := map[string]string{"news": "banner_news_id", "teams": "banner_teams_id", "members": "banner_members_id", "tournaments": "banner_tournaments_id", "scrims": "banner_scrims_id"}
	column, ok := columns[section]
	if !ok {
		return nil, fmt.Errorf("未知栏目")
	}
	var id *int64
	err := q.QueryRowContext(ctx, `SELECT `+column+` FROM site_settings WHERE id=1`).Scan(&id)
	return id, err
}
