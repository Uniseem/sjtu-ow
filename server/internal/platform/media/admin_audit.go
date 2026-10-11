package media

import (
	"context"
	"encoding/json"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func mediaAudit(ctx context.Context, tx *db.Tx, actor int64, action string, id int64, data any, now time.Time) error {
	if data == nil {
		data = map[string]any{}
	}
	encoded, err := json.Marshal(data)
	if err != nil {
		return err
	}
	kind := "image"
	if action == "collection.create" || action == "collection.rename" || action == "collection.delete" {
		kind = "image_collection"
	}
	_, err = tx.ExecContext(ctx, "INSERT INTO audit_log(actor_id,action,object_type,object_id,data,created_at) VALUES(?,?,?,?,?,?)",
		actor, action, kind, id, string(encoded), now.UTC().Format(time.RFC3339Nano))
	return err
}
