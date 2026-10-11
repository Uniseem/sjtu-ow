package media

import (
	"context"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// PoolImage 是默认图库的一张图；Role 是默认头像顶层位置文件夹的标签。
type PoolImage struct {
	ID   int64
	Role string
}

// LoadPool 包含根集合及所有子目录，沿用旧站按图片 ID 排序的规则。
func LoadPool(ctx context.Context, q db.DBTX, key string) ([]PoolImage, error) {
	rows, err := q.QueryContext(ctx, `WITH RECURSIVE pool(id,role,at_root) AS (
 SELECT id,'',1 FROM image_collections WHERE key=?
 UNION
 SELECT c.id,CASE WHEN p.at_root=1 THEN
   CASE c.name WHEN '坦克' THEN 'tank' WHEN '输出' THEN 'damage' WHEN '支援' THEN 'support' ELSE '' END
   ELSE p.role END,0
 FROM image_collections c JOIN pool p ON c.parent_id=p.id
 ) SELECT i.id,p.role FROM images i JOIN pool p ON p.id=i.collection_id ORDER BY i.id`, key)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []PoolImage{}
	for rows.Next() {
		var item PoolImage
		if err := rows.Scan(&item.ID, &item.Role); err != nil {
			return nil, err
		}
		out = append(out, item)
	}
	return out, rows.Err()
}

// PickCover 的 offset 与 core/placeholders.py 的 KIND_OFFSETS 一致（文章 0、赛事 13）。
func PickCover(pool []PoolImage, id, offset int64) *int64 {
	if len(pool) == 0 {
		return nil
	}
	value := pool[(id+offset)%int64(len(pool))].ID
	return &value
}

// PickAvatar 在有主位置的文件夹挑图；文件夹为空时回退到完整图库（旧站 core/avatars.py）。
func PickAvatar(pool []PoolImage, id int64, role string) *int64 {
	if id <= 0 {
		return nil
	}
	choices := []PoolImage{}
	for _, item := range pool {
		if role != "" && item.Role == role {
			choices = append(choices, item)
		}
	}
	if len(choices) == 0 {
		choices = pool
	}
	return PickCover(choices, id, 0)
}
