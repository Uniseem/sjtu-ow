package media

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Contributor access follows the fixed submission collection and its children
// (business rule 42). UNION also terminates safely on malformed legacy cycles.
const contributedCollections = `WITH RECURSIVE allowed(id) AS (
 SELECT id FROM image_collections WHERE key='contributed'
 UNION SELECT c.id FROM image_collections c JOIN allowed a ON c.parent_id=a.id
) SELECT id FROM allowed`

func CanChooseImage(ctx context.Context, q db.DBTX, viewer *app.Viewer, id int64) (bool, error) {
	if viewer == nil || viewer.Disabled {
		return false, nil
	}
	query := "SELECT COUNT(*) FROM images WHERE id=?"
	if !viewer.HasCap("images.manage") {
		if !viewer.HasCap("images.contribute") {
			return false, nil
		}
		query += " AND collection_id IN (" + contributedCollections + ")"
	}
	var count int
	err := q.QueryRowContext(ctx, query, id).Scan(&count)
	return count == 1, err
}

func canUploadCollection(ctx context.Context, q db.DBTX, viewer *app.Viewer, key string) (bool, error) {
	if viewer == nil || viewer.Disabled || !viewer.HasCap("images.contribute") {
		return false, nil
	}
	query := "SELECT COUNT(*) FROM image_collections WHERE key=?"
	if !viewer.HasCap("images.manage") {
		query += " AND id IN (" + contributedCollections + ")"
	}
	var count int
	err := q.QueryRowContext(ctx, query, key).Scan(&count)
	return count == 1, err
}
