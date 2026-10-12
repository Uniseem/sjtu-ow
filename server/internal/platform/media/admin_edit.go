package media

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type EditImageIn struct {
	ID          api.ID         `path:"id"`
	BaseVersion int64          `json:"base_version"`
	Changes     map[string]any `json:"changes"`
}

type EditImageValues struct {
	Title        string `json:"title"`
	CollectionID *int64 `json:"collection_id"`
}

type EditImageOut struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	Values  EditImageValues     `json:"values"`
	SavedAt string              `json:"saved_at"`
}

type CollectionCreateIn struct {
	Name     string `json:"name"`
	ParentID api.ID `json:"parent_id"`
}

type CollectionCreateOut struct {
	Collection *Collection `json:"collection"`
}

type CollectionRenameIn struct {
	ID          api.ID         `path:"id"`
	BaseVersion int64          `json:"base_version"`
	Changes     map[string]any `json:"changes"`
}

type CollectionNameValues struct {
	Name string `json:"name"`
}
type CollectionRenameOut struct {
	Version int64                `json:"version"`
	Saved   []string             `json:"saved"`
	Fields  map[string][]string  `json:"fields,omitempty"`
	Values  CollectionNameValues `json:"values"`
	SavedAt string               `json:"saved_at"`
}

type CollectionDeleteIn struct {
	ID api.ID `path:"id"`
}
type CollectionDeleteOut struct {
	Result string `json:"result"`
}

func (m *Module) registerAdminEditing(r *api.Registry) {
	api.Patch(r, "/api/admin/images/{id}", api.Cap(app.Cap("admin.enter")), m.editImage,
		api.Nav("content", "images"), api.NoLimit("图片元信息自动保存由客户端防抖"))
	api.Post(r, "/api/admin/image-collections", api.Superuser, m.createCollection,
		api.Nav("content", "images"), api.NoLimit("超级管理员创建集合"))
	api.Patch(r, "/api/admin/image-collections/{id}", api.Superuser, m.renameCollection,
		api.Nav("content", "images"), api.NoLimit("集合名称自动保存由客户端防抖"))
	api.Delete(r, "/api/admin/image-collections/{id}", api.Superuser, m.deleteCollection,
		api.Nav("content", "images"), api.NoLimit("超级管理员删除空集合"))
}

func imageStale(version int64, values EditImageValues) error {
	return &api.Error{Status: 409, Code: "stale", Message: "另一个人刚改过，已换成最新内容", Current: map[string]any{
		"version": version, "values": values,
	}}
}

func imageCollectionID(value any) (*int64, bool) {
	if value == nil {
		return nil, true
	}
	number, ok := value.(float64)
	if !ok || number <= 0 || number > 9007199254740991 || number != float64(int64(number)) {
		return nil, false
	}
	id := int64(number)
	return &id, true
}

func (m *Module) editImage(ctx *app.Ctx, in EditImageIn) (EditImageOut, error) {
	out := EditImageOut{Saved: []string{}, Fields: map[string][]string{}}
	err := m.svc.db.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		if err := requireImageManagement(c, tx, ctx.Viewer, int64(in.ID)); err != nil {
			return err
		}
		var version int64
		err := tx.QueryRowContext(c, "SELECT title, collection_id, version FROM images WHERE id=?", int64(in.ID)).Scan(
			&out.Values.Title, &out.Values.CollectionID, &version,
		)
		if errors.Is(err, sql.ErrNoRows) {
			return api.NotFound("图片不存在")
		}
		if err != nil {
			return err
		}
		if in.BaseVersion != version {
			return imageStale(version, out.Values)
		}
		keys := make([]string, 0, len(in.Changes))
		for key := range in.Changes {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			value := in.Changes[key]
			switch key {
			case "title":
				title, ok := value.(string)
				if !ok || utf8.RuneCountInString(title) > 255 {
					out.Fields[key] = []string{"标题不超过255字"}
					continue
				}
				out.Values.Title = title
				out.Saved = append(out.Saved, key)
			case "collection_id":
				id, ok := imageCollectionID(value)
				if !ok {
					out.Fields[key] = []string{"请选择有效集合"}
					continue
				}
				allowed, err := canMoveImageToCollection(c, tx, ctx.Viewer, id)
				if err != nil {
					return err
				}
				if !allowed {
					out.Fields[key] = []string{"你不能把图片放进这个集合"}
					continue
				}
				if id != nil {
					var found int
					err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM image_collections WHERE id=?", *id).Scan(&found)
					if err != nil {
						return err
					}
					if found != 1 {
						out.Fields[key] = []string{"集合不存在"}
						continue
					}
				}
				out.Values.CollectionID = id
				out.Saved = append(out.Saved, key)
			default:
				out.Fields[key] = []string{"这个字段不能修改"}
			}
		}
		out.Version = version
		out.SavedAt = ctx.Now().UTC().Format("2006-01-02T15:04:05.999999999Z07:00")
		if len(out.Saved) == 0 {
			return nil
		}
		_, err = tx.ExecContext(c, "UPDATE images SET title=?, collection_id=?,version=version+1 WHERE id=? AND version=?",
			out.Values.Title, out.Values.CollectionID, int64(in.ID), version)
		if err != nil {
			return err
		}
		out.Version++
		return mediaAudit(c, tx, ctx.Viewer.ID, "image.update", int64(in.ID), map[string]any{"saved": out.Saved}, ctx.Now())
	})
	return out, err
}

func collectionName(value string) (string, error) {
	name := strings.TrimSpace(value)
	if name == "" || utf8.RuneCountInString(name) > 255 {
		return "", api.InvalidFields(map[string][]string{"name": {"名称不能为空，且不超过255字"}})
	}
	return name, nil
}

func (m *Module) createCollection(ctx *app.Ctx, in CollectionCreateIn) (CollectionCreateOut, error) {
	name, err := collectionName(in.Name)
	if err != nil {
		return CollectionCreateOut{}, err
	}
	node := &Collection{Name: name, ParentID: new(int64), Version: 1, CanAdd: true, CanChange: true, CanDelete: true}
	*node.ParentID = int64(in.ParentID)
	node.CreatedAt = ctx.Now().UTC()
	err = m.svc.db.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		var parent int64
		err := tx.QueryRowContext(c, "SELECT id FROM image_collections WHERE id=?", int64(in.ParentID)).Scan(&parent)
		if errors.Is(err, sql.ErrNoRows) {
			return api.InvalidFields(map[string][]string{"parent_id": {"上级集合不存在"}})
		}
		if err != nil {
			return err
		}
		var duplicate int
		if err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM image_collections WHERE parent_id=? AND name=?", parent, name).Scan(&duplicate); err != nil {
			return err
		}
		if duplicate > 0 {
			return api.InvalidFields(map[string][]string{"name": {"同一级已经有这个名称的集合"}})
		}
		// The internal key is stable and unrelated to editable display names.
		var next int64
		if err := tx.QueryRowContext(c, "SELECT COALESCE(MAX(id),0)+1 FROM image_collections").Scan(&next); err != nil {
			return err
		}
		node.ID = next
		node.Key = fmt.Sprintf("collection_%d", next)
		_, err = tx.ExecContext(c, "INSERT INTO image_collections(id,name,key,parent_id,version,created_at) VALUES(?,?,?,?,1,?)",
			next, name, node.Key, parent, node.CreatedAt.Format("2006-01-02T15:04:05.999999999Z07:00"))
		if err != nil {
			return err
		}
		return mediaAudit(c, tx, ctx.Viewer.ID, "collection.create", node.ID, map[string]any{"name": name, "parent_id": parent}, ctx.Now())
	})
	if err != nil {
		return CollectionCreateOut{}, err
	}
	return CollectionCreateOut{Collection: node}, nil
}

func (m *Module) renameCollection(ctx *app.Ctx, in CollectionRenameIn) (CollectionRenameOut, error) {
	out := CollectionRenameOut{Saved: []string{}, Fields: map[string][]string{}}
	err := m.svc.db.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		var parent *int64
		if err := tx.QueryRowContext(c, "SELECT name,parent_id,version FROM image_collections WHERE id=?", int64(in.ID)).Scan(&out.Values.Name, &parent, &out.Version); err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return api.NotFound("集合不存在")
			}
			return err
		}
		if parent == nil {
			return api.Forbidden()
		}
		if in.BaseVersion != out.Version {
			return &api.Error{Status: 409, Code: "stale", Message: "集合刚被修改，已换成最新内容", Current: map[string]any{"version": out.Version, "values": out.Values}}
		}
		for key, value := range in.Changes {
			if key != "name" {
				out.Fields[key] = []string{"这个字段不能修改"}
				continue
			}
			raw, ok := value.(string)
			if !ok {
				out.Fields[key] = []string{"名称格式无效"}
				continue
			}
			name, err := collectionName(raw)
			if err != nil {
				out.Fields[key] = []string{"名称不能为空，且不超过255字"}
				continue
			}
			var duplicate int
			if err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM image_collections WHERE parent_id=? AND name=? AND id<>?", *parent, name, int64(in.ID)).Scan(&duplicate); err != nil {
				return err
			}
			if duplicate > 0 {
				out.Fields[key] = []string{"同一级已经有这个名称的集合"}
				continue
			}
			out.Values.Name = name
			out.Saved = append(out.Saved, key)
		}
		out.SavedAt = ctx.Now().UTC().Format("2006-01-02T15:04:05.999999999Z07:00")
		if len(out.Saved) == 0 {
			return nil
		}
		_, err := tx.ExecContext(c, "UPDATE image_collections SET name=?,version=version+1 WHERE id=? AND version=?", out.Values.Name, int64(in.ID), out.Version)
		if err != nil {
			return err
		}
		out.Version++
		return mediaAudit(c, tx, ctx.Viewer.ID, "collection.rename", int64(in.ID), map[string]any{"name": out.Values.Name}, ctx.Now())
	})
	return out, err
}

func (m *Module) deleteCollection(ctx *app.Ctx, in CollectionDeleteIn) (CollectionDeleteOut, error) {
	err := m.svc.db.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		var parent *int64
		err := tx.QueryRowContext(c, "SELECT parent_id FROM image_collections WHERE id=?", int64(in.ID)).Scan(&parent)
		if errors.Is(err, sql.ErrNoRows) {
			return api.NotFound("集合不存在")
		}
		if err != nil {
			return err
		}
		if parent == nil {
			return api.Forbidden()
		}
		var images, children int
		if err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM images WHERE collection_id=?", int64(in.ID)).Scan(&images); err != nil {
			return err
		}
		if err := tx.QueryRowContext(c, "SELECT COUNT(*) FROM image_collections WHERE parent_id=?", int64(in.ID)).Scan(&children); err != nil {
			return err
		}
		if images > 0 || children > 0 {
			return api.InvalidFields(map[string][]string{"__all__": {"集合里还有图片或子集合，不能删除"}})
		}
		_, err = tx.ExecContext(c, "DELETE FROM image_collections WHERE id=?", int64(in.ID))
		if err != nil {
			return err
		}
		return mediaAudit(c, tx, ctx.Viewer.ID, "collection.delete", int64(in.ID), nil, ctx.Now())
	})
	return CollectionDeleteOut{Result: "ok"}, err
}
