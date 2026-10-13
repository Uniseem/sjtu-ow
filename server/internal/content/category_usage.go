package content

import (
	"context"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Counts display each article once under its latest or approved category
// (legacy rule 212/D2). References also protect the stored public article and
// every approved revision, even when a later private draft changes category.
type categoryUsage struct {
	Counts     map[int64]int
	References map[int64]int
}

func categoryUses(ctx context.Context, q db.DBTX) (categoryUsage, error) {
	out := categoryUsage{Counts: map[int64]int{}, References: map[int64]int{}}
	byPage := map[int64]*int64{}
	references := map[int64]map[int64]bool{}
	reference := func(page, category int64) {
		if references[category] == nil {
			references[category] = map[int64]bool{}
		}
		references[category][page] = true
	}
	rows, err := q.QueryContext(ctx, "SELECT page_id,category_id FROM articles")
	if err != nil {
		return out, err
	}
	for rows.Next() {
		var page int64
		var category *int64
		if err := rows.Scan(&page, &category); err != nil {
			rows.Close()
			return out, err
		}
		byPage[page] = category
		if category != nil {
			reference(page, *category)
		}
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return out, err
	}
	rows, err = q.QueryContext(ctx, `SELECT r.page_id,r.content FROM page_revisions r JOIN pages p ON p.id=r.page_id
        JOIN articles a ON a.page_id=p.id WHERE r.id=p.latest_revision_id OR r.approved_go_live_at IS NOT NULL
        ORDER BY CASE WHEN r.id=p.latest_revision_id THEN 1 ELSE 0 END,r.created_at,r.id`)
	if err != nil {
		return out, err
	}
	defer rows.Close()
	for rows.Next() {
		var page int64
		var content string
		if err := rows.Scan(&page, &content); err != nil {
			return out, err
		}
		object, err := revisionObject(content)
		if err != nil {
			return out, err
		}
		var category *int64
		if err := revisionID(object, &category, "category_id", "category"); err != nil {
			return out, err
		}
		if category != nil {
			byPage[page] = category
			reference(page, *category)
		}
	}
	if err := rows.Err(); err != nil {
		return out, err
	}
	for _, category := range byPage {
		if category != nil {
			out.Counts[*category]++
		}
	}
	for category, pages := range references {
		out.References[category] = len(pages)
	}
	return out, nil
}
