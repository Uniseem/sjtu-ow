package scrims

import (
	"context"
	"database/sql"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/markdown"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

func (s *Service) projectPublicDetail(ctx *app.Ctx, page *Page) error {
	body, _, err := markdown.Render(page.Scrim.Description, s.siteURL, nil)
	if err != nil {
		return err
	}
	page.BodyHTML = body
	covers, err := media.LoadPool(ctx.Context, s.d.ReadPool(), "default_cover")
	if err != nil {
		return err
	}
	page.DefaultCoverImageID = media.PickCover(covers, page.Scrim.ID, 26)
	page.Scrim.DefaultCoverImageID = page.DefaultCoverImageID
	page.Card.DefaultCoverImageID = page.DefaultCoverImageID
	if page.Mine != nil {
		err := s.d.ReadPool().QueryRowContext(ctx.Context, `SELECT qq_group_url FROM site_settings WHERE id=1`).Scan(&page.GroupURL)
		if err != nil && err != sql.ErrNoRows {
			return err
		}
	}
	avatars, err := media.LoadPool(ctx.Context, s.d.ReadPool(), "default_avatar")
	if err != nil {
		return err
	}
	users := make([]int64, 0, len(page.Signups))
	for _, signup := range page.Signups {
		users = append(users, signup.UserID)
	}
	images, err := publicAvatars(ctx.Context, s.d.ReadPool(), avatars, users)
	if err != nil {
		return err
	}
	for i := range page.Signups {
		page.Signups[i].AvatarImageID = images[page.Signups[i].UserID]
	}
	return nil
}

// publicAvatars resolves this page's visible participants in one read. The
// only returned identifiers are approved/current avatars or deterministic
// defaults; stopped users are intentionally mapped to nil.
func publicAvatars(ctx context.Context, q db.DBTX, pool []media.PoolImage, users []int64) (map[int64]*int64, error) {
	out := map[int64]*int64{}
	if len(users) == 0 {
		return out, nil
	}
	args := []any{}
	marks := []string{}
	seen := map[int64]bool{}
	for _, id := range users {
		if id <= 0 || seen[id] {
			continue
		}
		seen[id] = true
		args = append(args, id)
		marks = append(marks, "?")
	}
	if len(args) == 0 {
		return out, nil
	}
	rows, err := q.QueryContext(ctx, `SELECT id,is_active,main_role,avatar_image_id FROM users WHERE id IN (`+strings.Join(marks, ",")+`)`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var active int
		var role string
		var image sql.NullInt64
		if err := rows.Scan(&id, &active, &role, &image); err != nil {
			return nil, err
		}
		if active != 1 {
			out[id] = nil
			continue
		}
		if image.Valid {
			value := image.Int64
			out[id] = &value
		} else {
			out[id] = media.PickAvatar(pool, id, role)
		}
	}
	return out, rows.Err()
}
