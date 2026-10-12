package media

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestContributorOwnImageManagementIsEnforcedByHTTPAndTransactions(t *testing.T) {
	module, database, manager := round290Media(t)
	err := database.WriteTx(manager.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, `INSERT INTO users(id,email,email_norm,password_hash,nickname,is_sjtu,agreed_terms_at,agreed_cross_border_at,created_at,updated_at) VALUES(2,'other@example.test','other@example.test','hash','Other',1,'2026-10-10','2026-10-10','2026-10-10','2026-10-10');
 INSERT INTO image_collections(id,name,key,parent_id,created_at) VALUES(101,'Submission child','submission_child',4,'2026-10-10');
 INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,uploader_id,created_at,version) VALUES
 (100,4,'Own root','own.webp',10,10,10,1,'2026-10-10T00:00:00Z',1),
 (101,101,'Own child','child.webp',10,10,10,1,'2026-10-10T00:00:00Z',1),
 (102,4,'Other secret','other-secret.webp',10,10,10,2,'2026-10-10T00:00:00Z',1),
 (103,3,'Private avatar','avatar-secret.webp',10,10,10,1,'2026-10-10T00:00:00Z',1);`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	writer := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}, "images.contribute": {}}}}
	var registry api.Registry
	module.Routes(&registry)
	viewer := writer.Viewer
	handler := registry.Handler(func(*http.Request) *app.Viewer { return viewer })
	request := func(method, path, body string) *httptest.ResponseRecorder {
		t.Helper()
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		if body != "" {
			req.Header.Set("Content-Type", "application/json")
		}
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		return rec
	}
	for _, id := range []string{"102", "103"} {
		for _, method := range []string{http.MethodGet, http.MethodPatch, http.MethodDelete} {
			body := ""
			if method == http.MethodPatch {
				body = `{"base_version":0,"changes":{"title":"forbidden"}}`
			}
			rec := request(method, "/api/admin/images/"+id, body)
			if rec.Code != http.StatusForbidden {
				t.Fatalf("%s denied image %s: %d %s", method, id, rec.Code, rec.Body.String())
			}
			for _, secret := range []string{"current", "Other secret", "Private avatar", "other-secret.webp", "avatar-secret.webp"} {
				if strings.Contains(rec.Body.String(), secret) {
					t.Fatalf("denial leaked %q: %s", secret, rec.Body.String())
				}
			}
		}
	}
	rec := request(http.MethodGet, "/api/admin/images/100", "")
	var image Image
	if rec.Code != 200 || json.Unmarshal(rec.Body.Bytes(), &image) != nil || !image.CanChange || !image.CanDelete {
		t.Fatalf("own detail=%d %s", rec.Code, rec.Body.String())
	}
	rec = request(http.MethodPatch, "/api/admin/images/100", `{"base_version":1,"changes":{"title":"Edited","collection_id":101}}`)
	if rec.Code != 200 {
		t.Fatalf("own edit=%d %s", rec.Code, rec.Body.String())
	}
	var receipt EditImageOut
	if err := json.Unmarshal(rec.Body.Bytes(), &receipt); err != nil || receipt.Version != 2 || receipt.Values.CollectionID == nil || *receipt.Values.CollectionID != 101 {
		t.Fatalf("own receipt=%+v err=%v", receipt, err)
	}
	rec = request(http.MethodPatch, "/api/admin/images/100", `{"base_version":2,"changes":{"collection_id":3}}`)
	if rec.Code != 200 || json.Unmarshal(rec.Body.Bytes(), &receipt) != nil || len(receipt.Saved) != 0 || len(receipt.Fields["collection_id"]) == 0 {
		t.Fatalf("private move accepted: %d %s", rec.Code, rec.Body.String())
	}
	rec = request(http.MethodPatch, "/api/admin/images/100", `{"base_version":1,"changes":{"title":"stale"}}`)
	if rec.Code != 409 || !strings.Contains(rec.Body.String(), "current") {
		t.Fatalf("own stale protection=%d %s", rec.Code, rec.Body.String())
	}
	// Service calls do not rely on the registry's capability gate.
	denied, err := module.editImage(writer, EditImageIn{ID: 102, BaseVersion: 0, Changes: map[string]any{"title": "blocked"}})
	apiErr := mediaRound290Status(t, err, 403)
	if apiErr.Current != nil || denied.Values.Title != "" {
		t.Fatalf("direct stale denial leaked: %+v %+v", denied, apiErr)
	}
	if err := module.svc.DeleteImage(writer, 103); err == nil {
		t.Fatal("private own avatar deleted through service")
	}
	// A previously fetched own detail grants no authority after a collection move.
	err = database.WriteTx(writer.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE images SET collection_id=3 WHERE id=100")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = module.editImage(writer, EditImageIn{ID: 100, BaseVersion: 0, Changes: map[string]any{"title": "blocked"}})
	mediaRound290Status(t, err, 403)
	mediaRound290Status(t, module.svc.DeleteImage(writer, 100), 403)
	// Collection ancestry is also re-evaluated within the mutation transaction.
	err = database.WriteTx(writer.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE image_collections SET parent_id=3 WHERE id=101")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = module.editImage(writer, EditImageIn{ID: 101, BaseVersion: 1, Changes: map[string]any{"title": "blocked"}})
	mediaRound290Status(t, err, 403)
	// Managers retain all-image authority.
	viewer = manager.Viewer
	rec = request(http.MethodGet, "/api/admin/images/103", "")
	if rec.Code != 200 {
		t.Fatalf("manager detail=%d %s", rec.Code, rec.Body.String())
	}
	viewer = writer.Viewer
	err = database.WriteTx(writer.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, `UPDATE images SET collection_id=4 WHERE id=100;
 INSERT INTO pages(id,kind,slug,title,live,created_at,updated_at) VALUES(1000,'article','cover','Keep article',1,'2026-10-10','2026-10-10');
 INSERT INTO articles(page_id,cover_image_id) VALUES(1000,100);`)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	rec = request(http.MethodDelete, "/api/images/100", "")
	if rec.Code != 200 {
		t.Fatalf("own deletion=%d %s", rec.Code, rec.Body.String())
	}
	var count int
	if err := database.ReadPool().QueryRowContext(writer.Context, "SELECT COUNT(*) FROM articles WHERE page_id=1000 AND cover_image_id IS NULL").Scan(&count); err != nil || count != 1 {
		t.Fatalf("reference fallback changed: %d %v", count, err)
	}
}
