package media

import (
	"context"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
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

// Metadata management is broader for managers, and limited to the contributor's
// own uploads within the submission collection tree for ordinary writers.
func canManageImage(ctx context.Context, q db.DBTX, viewer *app.Viewer, id int64) (bool, error) {
	if viewer == nil || viewer.Disabled {
		return false, nil
	}
	query := "SELECT COUNT(*) FROM images WHERE id=?"
	args := []any{id}
	if !viewer.HasCap("images.manage") {
		if !viewer.HasCap("images.contribute") {
			return false, nil
		}
		query += " AND uploader_id=? AND collection_id IN (" + contributedCollections + ")"
		args = append(args, viewer.ID)
	}
	var count int
	err := q.QueryRowContext(ctx, query, args...).Scan(&count)
	return count == 1, err
}

func requireImageManagement(ctx context.Context, q db.DBTX, viewer *app.Viewer, id int64) error {
	allowed, err := canManageImage(ctx, q, viewer, id)
	if err != nil {
		return err
	}
	if allowed {
		return nil
	}
	if viewer != nil && !viewer.Disabled && viewer.HasCap("images.manage") {
		return api.NotFound("图片不存在")
	}
	return api.Forbidden()
}

func canMoveImageToCollection(ctx context.Context, q db.DBTX, viewer *app.Viewer, id *int64) (bool, error) {
	if viewer == nil || viewer.Disabled {
		return false, nil
	}
	if viewer.HasCap("images.manage") {
		return true, nil
	}
	if !viewer.HasCap("images.contribute") || id == nil {
		return false, nil
	}
	var count int
	err := q.QueryRowContext(ctx, "SELECT COUNT(*) FROM image_collections WHERE id=? AND id IN ("+contributedCollections+")", *id).Scan(&count)
	return count == 1, err
}
