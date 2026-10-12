package ops

import (
	"context"
	"database/sql"
	"path/filepath"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/audit"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestReconcileAuditRejectsObjectAndActualActorCorruption(t *testing.T) {
	ctx := context.Background()
	d, _ := setupTestDB(t)
	if err := d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, `INSERT INTO users(id,email,email_norm,password_hash,nickname,is_sjtu,agreed_terms_at,agreed_cross_border_at,version,is_active,is_superuser,created_at,updated_at) VALUES(1,'one@example.test','one@example.test','!','一个用户',0,'2026-01-01','2026-01-01',1,1,0,'2026-01-01','2026-01-01'),(2,'two@example.test','two@example.test','!','另个用户',0,'2026-01-01','2026-01-01',1,1,0,'2026-01-01','2026-01-01')`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "legacy_audit.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, statement := range []string{
		`CREATE TABLE django_content_type(id INTEGER,model TEXT)`,
		`INSERT INTO django_content_type VALUES(1,'articlepage')`,
		`CREATE TABLE wagtailcore_pagelogentry(id INTEGER,user_id INTEGER,action TEXT,page_id INTEGER,data TEXT,timestamp TEXT,label TEXT,content_type_id INTEGER)`,
		`CREATE TABLE wagtailcore_modellogentry(id INTEGER,user_id INTEGER,action TEXT,object_id TEXT,data TEXT,timestamp TEXT,label TEXT,content_type_id INTEGER)`,
		`INSERT INTO wagtailcore_pagelogentry VALUES(1,1,'wagtail.publish',8,'{}','2026-10-12 08:00:00','文章',1)`,
		`INSERT INTO wagtailcore_modellogentry VALUES(1,999,'wagtail.delete','9223372036854775808','{}','2026-10-12 08:00:01','已删对象',NULL)`,
	} {
		if _, err := legacy.ExecContext(ctx, statement); err != nil {
			t.Fatal(err)
		}
	}
	check := func(want bool) {
		t.Helper()
		result := &ReconcileResult{OverallOK: true}
		if err := reconcileAudit(ctx, d.ReadPool(), legacy, result); err != nil {
			t.Fatal(err)
		}
		if result.OverallOK != want {
			t.Fatalf("wrong audit gate: want=%v result=%#v", want, result)
		}
	}
	if err := audit.ImportLegacyLogs(ctx, d, legacy); err != nil {
		t.Fatal(err)
	}
	var model string
	var object int64
	if err := d.ReadPool().QueryRowContext(ctx, `SELECT object_type,object_id FROM audit_log WHERE id=-2`).Scan(&model, &object); err != nil {
		t.Fatal(err)
	}
	if model != "legacy_unknown" || object != 0 {
		t.Fatal("lost nullable content-type or overflow handling")
	}
	check(true)
	for _, corrupt := range []string{
		`UPDATE audit_log SET object_id=9 WHERE id=-3`,
		`UPDATE audit_log SET object_type='team' WHERE id=-3`,
		`UPDATE audit_log SET actor_id=2 WHERE id=-3`,
		`UPDATE audit_log SET data=json_set(data,'$.legacy_object_id','wrong') WHERE id=-3`,
		`UPDATE audit_log SET actor_id=1 WHERE id=-2`,
	} {
		if err := d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error { _, err := tx.ExecContext(c, corrupt); return err }); err != nil {
			t.Fatal(err)
		}
		check(false)
		if err := audit.ImportLegacyLogs(ctx, d, legacy); err != nil {
			t.Fatal(err)
		}
		check(true)
	}
}
