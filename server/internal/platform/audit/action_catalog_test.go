package audit

import (
	"context"
	"database/sql"
	"path/filepath"
	"reflect"
	"testing"
)

func TestActionDirectoryIsStableAcrossLegacyImportAndFiltering(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	empty, err := Query(ctx, d.ReadPool(), QueryInput{})
	if err != nil {
		t.Fatal(err)
	}
	if empty.Total != 0 || len(empty.Actions) != 60 {
		t.Fatalf("frozen action directory incomplete on empty history: %+v", empty)
	}
	// Registration order comes from the site's hooks, then Wagtail's hooks.
	for index, action := range map[int]string{
		0: "tournaments.publish", 18: "scrims.notify_participants", 19: "tournaments.export_registrations",
		20: "moderation.handle", 21: "moderation.ask_author", 22: "wagtail.create", 23: "wagtail.edit",
		25: "wagtail.apitoken.create", 26: "wagtail.apitoken.revoke", 28: "wagtail.publish.scheduled",
		30: "wagtail.unpublish.scheduled", 54: "wagtail.comments.delete_reply", 59: "wagtail.workflow.cancel",
	} {
		if empty.Actions[index] != action {
			t.Fatalf("frozen action %d=%q, want %q", index, empty.Actions[index], action)
		}
	}
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "legacy-action-history.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	for _, statement := range []string{
		`CREATE TABLE django_content_type (id INTEGER,model TEXT)`,
		`INSERT INTO django_content_type VALUES(1,'articlepage')`,
		`CREATE TABLE wagtailcore_modellogentry(id INTEGER,user_id INTEGER,action TEXT,object_id TEXT,data TEXT,timestamp TEXT,label TEXT,content_type_id INTEGER)`,
		`INSERT INTO wagtailcore_modellogentry VALUES
		(52,NULL,'wagtail.apitoken.create','8','{}','2026-10-14 00:00:00','原始令牌名称',1),
		(90,NULL,'moderation.ask_author','8','{}','2026-10-14 00:00:00','原始文章名称',1),
		(91,NULL,'tournaments.export_registrations','8','{}','2026-10-14 00:00:00','原始导出对象',1),
		(98,NULL,'future.plugin.action','8','{}','2026-10-14 00:00:00','未来扩展对象',1)`,
	} {
		if _, err := legacy.ExecContext(ctx, statement); err != nil {
			t.Fatal(err)
		}
	}
	for repeat := 0; repeat < 2; repeat++ {
		if err := ImportLegacyLogs(ctx, d, legacy); err != nil {
			t.Fatal(err)
		}
	}
	imported, err := Query(ctx, d.ReadPool(), QueryInput{})
	if err != nil {
		t.Fatal(err)
	}
	if imported.Total != 4 || len(imported.Items) != 4 || len(imported.Actions) != 61 || !reflect.DeepEqual(imported.Actions[:60], empty.Actions) || imported.Actions[60] != "future.plugin.action" {
		t.Fatalf("import changed registered choices or duplicated history: %+v", imported)
	}
	for index, label := range []string{"未来扩展对象", "原始导出对象", "原始文章名称", "原始令牌名称"} {
		if imported.Items[index].Label != label {
			t.Fatalf("source label/order changed: %+v", imported.Items)
		}
	}
	filtered, err := Query(ctx, d.ReadPool(), QueryInput{Action: "tournaments.export_registrations"})
	if err != nil {
		t.Fatal(err)
	}
	if filtered.Total != 1 || len(filtered.Items) != 1 || filtered.Items[0].Action != "tournaments.export_registrations" || !reflect.DeepEqual(filtered.Actions, imported.Actions) {
		t.Fatalf("action filter changed the directory or selected wrong record: %+v", filtered)
	}
}
