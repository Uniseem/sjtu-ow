package audit

import (
	"context"
	"database/sql"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestImportBothLegacyLogsIsIdempotentAndRedactsSecrets(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	if err := d.WriteTx(ctx, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, `INSERT INTO users (id,email,email_norm,password_hash,nickname,is_sjtu,agreed_terms_at,agreed_cross_border_at,version,is_active,is_superuser,created_at,updated_at) VALUES (1,'admin@example.com','admin@example.com','x','站长',1,'2026-01-01','2026-01-01',1,1,1,'2026-01-01','2026-01-01')`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	legacy, err := sql.Open("sqlite", filepath.Join(t.TempDir(), "legacy.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer legacy.Close()
	statements := []string{
		`CREATE TABLE django_content_type (id INTEGER, model TEXT)`,
		`INSERT INTO django_content_type VALUES(1,'articlepage'),(2,'team')`,
		`CREATE TABLE wagtailcore_pagelogentry(id INTEGER,user_id INTEGER,action TEXT,page_id INTEGER,data TEXT,timestamp TEXT,label TEXT,content_type_id INTEGER)`,
		`CREATE TABLE wagtailcore_modellogentry(id INTEGER,user_id INTEGER,action TEXT,object_id TEXT,data TEXT,timestamp TEXT,label TEXT,content_type_id INTEGER)`,
		`INSERT INTO wagtailcore_pagelogentry VALUES(1,1,'wagtail.publish',8,'{"precise_id":9007199254740993,"nested":[{"precise_id":9223372036854775807}],"title":"文章","smtp_password":"do-not-import"}','2026-10-12 08:00:00','文章',1)`,
		`INSERT INTO wagtailcore_modellogentry VALUES(1,999,'teams.disband','4','{"changes":{"api_key":"do-not-import","is_recruiting":false}}','2026-10-12 08:00:01','战队',2)`,
	}
	for _, statement := range statements {
		if _, err := legacy.ExecContext(ctx, statement); err != nil {
			t.Fatal(err)
		}
	}
	for i := 0; i < 2; i++ {
		if err := ImportLegacyLogs(ctx, d, legacy); err != nil {
			t.Fatal(err)
		}
	}
	result, err := Query(ctx, d.ReadPool(), QueryInput{})
	if err != nil {
		t.Fatal(err)
	}
	if result.Total != 2 {
		t.Fatalf("want two records, got %d", result.Total)
	}
	seen := map[string]bool{}
	for _, item := range result.Items {
		seen[item.Action] = true
		if item.ID >= 0 || item.Label == "" {
			t.Fatalf("wrong preserved record: %#v", item)
		}
		if strings.Contains(string(item.Data), "do-not-import") {
			t.Fatal("secret imported")
		}
		if item.Action == "wagtail.publish" && (!strings.Contains(string(item.Data), "9007199254740993") || !strings.Contains(string(item.Data), "9223372036854775807")) {
			t.Fatal("large legacy metadata number was rounded")
		}
		if item.Action == "wagtail.publish" && (item.ActorID == nil || *item.ActorID != 1 || item.ObjectID != 8 || item.CreatedAt.Format("2006-01-02 15:04:05") != "2026-10-12 08:00:00") {
			t.Fatal("lost page identity, actor or timestamp")
		}
		if item.Action == "teams.disband" && (item.ObjectType != "team" || item.ObjectID != 4) {
			t.Fatal("lost object identity")
		}
	}
	if !seen["wagtail.publish"] || !seen["teams.disband"] {
		t.Fatal("lost source action")
	}
}
