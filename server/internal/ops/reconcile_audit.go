package ops

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// reconcileAudit isolates imported history from new runtime audit records.
func reconcileAudit(ctx context.Context, current, legacy *sql.DB, result *ReconcileResult) error {
	for _, source := range []struct {
		table string
		page  bool
	}{{"wagtailcore_pagelogentry", true}, {"wagtailcore_modellogentry", false}} {
		stat := TableStat{EntityName: "操作记录（" + source.table + "）", NewTable: "audit_log", LegacyTable: source.table, Status: "MATCH"}
		var exists int
		if err := legacy.QueryRowContext(ctx, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", source.table).Scan(&exists); err != nil {
			return err
		}
		if exists > 0 {
			if err := legacy.QueryRowContext(ctx, "SELECT count(*) FROM "+source.table).Scan(&stat.LegacyCount); err != nil {
				return err
			}
		}
		if err := current.QueryRowContext(ctx, `SELECT count(*) FROM audit_log WHERE json_extract(data,'$.legacy_table')=?`, source.table).Scan(&stat.NewCount); err != nil {
			return err
		}
		if stat.NewCount != stat.LegacyCount {
			stat.Status = "COUNT_DIFF"
			result.OverallOK = false
		}
		result.Tables = append(result.Tables, stat)
		if exists == 0 {
			continue
		}
		fallbackModel := "legacy_unknown"
		object := "l.object_id"
		if source.page {
			object = "l.page_id"
			fallbackModel = "page"
		}
		rows, err := legacy.QueryContext(ctx, fmt.Sprintf("SELECT l.id,l.user_id,l.action,l.label,l.timestamp,%s,COALESCE(c.model,'%s') FROM %s l LEFT JOIN django_content_type c ON c.id=l.content_type_id ORDER BY l.id LIMIT 5", object, fallbackModel, source.table))
		if err != nil {
			return err
		}
		checked, matched := 0, 0
		for rows.Next() {
			var id int64
			var actor sql.NullInt64
			var action, label, at, model string
			var objectID sql.NullString
			if err := rows.Scan(&id, &actor, &action, &label, &at, &objectID, &model); err != nil {
				rows.Close()
				return err
			}
			key, err := audit.LegacyID(id, source.page)
			if err != nil {
				rows.Close()
				return err
			}
			oldTime, err := db.ParseUTC(at)
			if err != nil {
				rows.Close()
				return err
			}
			var newAction, newLabel, newAt, newObjectType, newObjectText string
			var newObjectID int64
			var actualActor sql.NullInt64
			expectedActor := sql.NullInt64{}
			if actor.Valid {
				var exists int
				if err := current.QueryRowContext(ctx, "SELECT count(*) FROM users WHERE id=?", actor.Int64).Scan(&exists); err != nil {
					rows.Close()
					return err
				}
				if exists > 0 {
					expectedActor = actor
				}
			}
			var oldActor sql.NullInt64
			checked++
			err = current.QueryRowContext(ctx, `SELECT action,json_extract(data,'$.label'),created_at,json_extract(data,'$.legacy_actor_id'),actor_id,object_type,object_id,json_extract(data,'$.legacy_object_id') FROM audit_log WHERE id=?`, key).Scan(&newAction, &newLabel, &newAt, &oldActor, &actualActor, &newObjectType, &newObjectID, &newObjectText)
			if err == nil && newAction == action && newLabel == label && newAt == db.FormatUTC(oldTime) && actor == oldActor && actualActor == expectedActor && newObjectType == audit.LegacyObjectType(model) && newObjectID == audit.LegacyObjectID(objectID.String) && newObjectText == objectID.String {
				matched++
			} else {
				result.OverallOK = false
			}
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}
		result.SampleReport = append(result.SampleReport, fmt.Sprintf("%s checked=%d matched=%d", source.table, checked, matched))
	}
	return nil
}
