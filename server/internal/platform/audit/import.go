package audit

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"strconv"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// LegacyID uses a negative namespace so page/model IDs cannot collide with
// each other or with live records. Repeated imports update the same record.
func LegacyID(id int64, page bool) (int64, error) {
	if id <= 0 || id > (math.MaxInt64-1)/2 {
		return 0, fmt.Errorf("旧审计编号超出范围")
	}
	offset := int64(0)
	if page {
		offset = 1
	}
	return -(id*2 + offset), nil
}

// RedactLegacyData keeps historical metadata without importing stored secrets.
// Apply recursively because Wagtail field changes can be nested.
func RedactLegacyData(value any) any {
	switch v := value.(type) {
	case map[string]any:
		sensitiveField := false
		for _, descriptor := range []string{"field", "name", "field_name"} {
			if value, ok := v[descriptor].(string); ok && sensitiveLegacyKey(value) {
				sensitiveField = true
			}
		}
		for key, item := range v {
			name := strings.ToLower(key)
			if sensitiveLegacyKey(name) || sensitiveField && (name == "old" || name == "new" || name == "value" || name == "old_value" || name == "new_value") {
				v[key] = "[redacted]"
			} else {
				v[key] = RedactLegacyData(item)
			}
		}
	case []any:
		for i, item := range v {
			v[i] = RedactLegacyData(item)
		}
	}
	return value
}

func sensitiveLegacyKey(key string) bool {
	name := strings.ToLower(key)
	return strings.Contains(name, "password") || strings.Contains(name, "secret") || (strings.Contains(name, "token") && !strings.Contains(name, "tokens")) || strings.Contains(name, "api_key") || strings.Contains(name, "access_key") || strings.Contains(name, "credential")
}

// LegacyObjectID preserves numeric primary keys; UUID/text keys remain in
// legacy_object_id metadata and use zero in the numeric audit column.
func LegacyObjectID(value string) int64 {
	number, err := strconv.ParseInt(value, 10, 64)
	if err != nil {
		return 0
	}
	return number
}

// LegacyObjectType maps a frozen content-type model to its new domain.
func LegacyObjectType(model string) string {
	switch model {
	case "articlepage":
		return "article"
	case "standardpage", "page":
		return "page"
	case "membergroup":
		return "member_group"
	case "fontfamily":
		return "font"
	case "sitesettings":
		return "settings"
	case "user", "team", "tournament", "scrim", "registration", "comment", "image":
		return model
	default:
		return model
	}
}

// ImportLegacyLogs reads both frozen Wagtail log tables. The caller opens
// legacy read-only. Invalid metadata aborts the transaction rather than
// silently dropping history. Missing actors retain their old ID in metadata.
func ImportLegacyLogs(ctx context.Context, d *db.DB, legacy *sql.DB) error {
	return d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		for _, source := range []struct {
			table string
			page  bool
		}{{"wagtailcore_pagelogentry", true}, {"wagtailcore_modellogentry", false}} {
			var exists int
			if err := legacy.QueryRowContext(ctx, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", source.table).Scan(&exists); err != nil {
				return err
			}
			if exists == 0 {
				continue
			}
			fallbackModel := "legacy_unknown"
			object := "l.object_id"
			if source.page {
				object = "l.page_id"
				fallbackModel = "page"
			}
			rows, err := legacy.QueryContext(ctx, fmt.Sprintf(`SELECT l.id,l.user_id,l.action,%s,l.data,l.timestamp,l.label,COALESCE(c.model,'%s') FROM %s l LEFT JOIN django_content_type c ON c.id=l.content_type_id ORDER BY l.id`, object, fallbackModel, source.table))
			if err != nil {
				return fmt.Errorf("读取旧审计表 %s: %w", source.table, err)
			}
			for rows.Next() {
				var oldID int64
				var actor sql.NullInt64
				var objectID sql.NullString
				var action, at, label, model string
				var raw sql.NullString
				if err := rows.Scan(&oldID, &actor, &action, &objectID, &raw, &at, &label, &model); err != nil {
					rows.Close()
					return err
				}
				id, err := LegacyID(oldID, source.page)
				if err != nil {
					rows.Close()
					return err
				}
				timestamp, err := db.ParseUTC(at)
				if err != nil {
					rows.Close()
					return fmt.Errorf("旧审计时间 %s/%d: %w", source.table, oldID, err)
				}
				metadata := map[string]any{}
				if raw.Valid && raw.String != "" {
					decoder := json.NewDecoder(strings.NewReader(raw.String))
					decoder.UseNumber()
					if err := decoder.Decode(&metadata); err != nil {
						rows.Close()
						return fmt.Errorf("旧审计JSON %s/%d: %w", source.table, oldID, err)
					}
					var extra any
					if err := decoder.Decode(&extra); err != io.EOF {
						rows.Close()
						return fmt.Errorf("旧审计JSON %s/%d 存在尾随数据", source.table, oldID)
					}
				}
				if metadata == nil {
					metadata = map[string]any{}
				}
				RedactLegacyData(metadata)
				metadata["label"] = label
				metadata["legacy_table"] = source.table
				metadata["legacy_id"] = oldID
				metadata["legacy_object_id"] = objectID.String
				numericID := LegacyObjectID(objectID.String)
				if actor.Valid {
					metadata["legacy_actor_id"] = actor.Int64
				}
				var by any
				if actor.Valid {
					var found int
					if err := tx.QueryRowContext(txCtx, "SELECT count(*) FROM users WHERE id=?", actor.Int64).Scan(&found); err != nil {
						rows.Close()
						return err
					}
					if found > 0 {
						by = actor.Int64
					}
				}
				encoded, err := json.Marshal(metadata)
				if err != nil {
					rows.Close()
					return err
				}
				if _, err := tx.ExecContext(txCtx, `INSERT INTO audit_log (id,actor_id,action,object_type,object_id,data,created_at) VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET actor_id=excluded.actor_id,action=excluded.action,object_type=excluded.object_type,object_id=excluded.object_id,data=excluded.data,created_at=excluded.created_at`, id, by, action, LegacyObjectType(model), numericID, string(encoded), db.FormatUTC(timestamp)); err != nil {
					rows.Close()
					return err
				}
			}
			rows.Close()
			if err := rows.Err(); err != nil {
				return err
			}
		}
		return nil
	})
}
