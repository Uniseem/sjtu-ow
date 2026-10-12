package media

import (
	"context"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// RetireUnusedTeamLogo is called only after the teams domain has authorized a
// logo replacement/removal. Unlike a library action it may retire a former
// captain's upload, but only an unused image from the dedicated logo collection.
// No HTTP handler exposes this lifecycle operation.
func (s *Service) RetireUnusedTeamLogo(ctx *app.Ctx, id int64) error {
	return s.retireUnusedImage(ctx, id, "team_logo", false)
}

// RetireUnusedUserAvatar follows an authorized personal avatar replacement or
// removal. The submission must belong to the caller and no current user/team
// may still reference it. It does not grant library access to private avatars.
func (s *Service) RetireUnusedUserAvatar(ctx *app.Ctx, id int64) error {
	return s.retireUnusedImage(ctx, id, "user_avatar", true)
}

func (s *Service) retireUnusedImage(ctx *app.Ctx, id int64, key string, ownSubmission bool) error {
	if ctx == nil || ctx.Viewer == nil || ctx.Viewer.Disabled || ctx.Viewer.ID <= 0 {
		return api.Forbidden()
	}
	if id <= 0 {
		return nil
	}
	removed := false
	err := s.db.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		query := `DELETE FROM images WHERE id=? AND collection_id=(SELECT id FROM image_collections WHERE key=?)
    AND NOT EXISTS(SELECT 1 FROM teams WHERE logo_image_id=images.id)
    AND NOT EXISTS(SELECT 1 FROM users WHERE avatar_image_id=images.id)`
		args := []any{id, key}
		if ownSubmission {
			query += " AND EXISTS(SELECT 1 FROM avatar_submissions WHERE image_id=images.id AND user_id=?)"
			args = append(args, ctx.Viewer.ID)
		}
		result, err := tx.ExecContext(c, query, args...)
		if err != nil {
			return err
		}
		count, err := result.RowsAffected()
		if err != nil {
			return err
		}
		removed = count == 1
		if removed {
			return mediaAudit(c, tx, ctx.Viewer.ID, "image.delete", id, map[string]any{"lifecycle": key}, ctx.Now())
		}
		return nil
	})
	if err != nil {
		return err
	}
	if removed {
		s.DeleteImageFiles(id)
	}
	return nil
}
