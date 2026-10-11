package content

import (
	"context"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func categoryDuplicates(ctx context.Context, q db.DBTX, id int64, name, slug string) error {
	var sameName, sameSlug int
	err := q.QueryRowContext(ctx, `SELECT
        (SELECT COUNT(*) FROM article_categories WHERE name=? AND id<>?),
        (SELECT COUNT(*) FROM article_categories WHERE slug=? AND id<>?)`, name, id, slug, id).Scan(&sameName, &sameSlug)
	if err != nil {
		return err
	}
	fields := map[string][]string{}
	if sameName > 0 {
		fields["name"] = []string{"已经有这个名称的分类"}
	}
	if sameSlug > 0 {
		fields["slug"] = []string{"这个网址片段已被使用"}
	}
	if len(fields) > 0 {
		return api.InvalidFields(fields)
	}
	return nil
}
