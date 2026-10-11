package content

import (
	"context"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

// NewsAuthorOut 是图片卡读取的公开头像字段。
type NewsAuthorOut struct {
	ID            int64  `json:"id"`
	Nickname      string `json:"nickname"`
	AvatarImageID *int64 `json:"avatar_image_id"`
	IsActive      bool   `json:"is_active"`
}

func (s *Store) newsItems(ctx context.Context, articles []*Article, pool []media.PoolImage) ([]*NewsItemOut, error) {
	ids := []any{}
	placeholders := []string{}
	seen := map[int64]bool{}
	for _, a := range articles {
		if a.AuthorID != nil && !seen[*a.AuthorID] {
			seen[*a.AuthorID] = true
			ids = append(ids, *a.AuthorID)
			placeholders = append(placeholders, "?")
		}
	}
	authors := map[int64]*NewsAuthorOut{}
	if len(ids) > 0 {
		rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT id,nickname,avatar_image_id,is_active,main_role,flex_roles FROM users WHERE id IN (`+strings.Join(placeholders, ",")+`)`, ids...)
		if err != nil {
			return nil, err
		}
		roles := map[int64]string{}
		for rows.Next() {
			var a NewsAuthorOut
			var active int
			var main, flex string
			if err := rows.Scan(&a.ID, &a.Nickname, &a.AvatarImageID, &active, &main, &flex); err != nil {
				_ = rows.Close()
				return nil, err
			}
			a.IsActive = active == 1
			if !a.IsActive {
				a.AvatarImageID = nil
			}
			authors[a.ID] = &a
			if a.IsActive && a.AvatarImageID == nil {
				if main == "" {
					list := accounts.ParseRoles(flex)
					if len(list) > 0 {
						main = list[0]
					}
				}
				roles[a.ID] = main
			}
		}
		err = rows.Err()
		_ = rows.Close()
		if err != nil {
			return nil, err
		}
		if len(roles) > 0 {
			avatars, err := media.LoadPool(ctx, s.d.ReadPool(), "default_avatar")
			if err != nil {
				return nil, err
			}
			for id, role := range roles {
				authors[id].AvatarImageID = media.PickAvatar(avatars, id, role)
			}
		}
	}
	out := make([]*NewsItemOut, 0, len(articles))
	for _, a := range articles {
		item := newsItem(a, media.PickCover(pool, a.ID, 0))
		if a.AuthorID != nil {
			item.Author = authors[*a.AuthorID]
		}
		out = append(out, item)
	}
	return out, nil
}
