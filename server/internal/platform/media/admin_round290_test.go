package media

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func round290Media(t *testing.T) (*Module, *db.DB, *app.Ctx) {
	t.Helper()
	database, directory := setupTestDB(t)
	service := NewService(database, filepath.Join(directory, "originals"), filepath.Join(directory, "media"))
	ctx := &app.Ctx{Context: context.Background(), Viewer: &app.Viewer{ID: 1, Superuser: true, Caps: map[app.Cap]struct{}{"admin.enter": {}, "images.manage": {}, "images.contribute": {}}}}
	return NewModule(service), database, ctx
}

func mediaRound290Status(t *testing.T, err error, want int) *api.Error {
	t.Helper()
	var result *api.Error
	if !errors.As(err, &result) || result.Status != want {
		t.Fatalf("error=%v want=%d", err, want)
	}
	return result
}

func TestRound290CollectionCRUDCannotDeleteRootParentOrNonemptyCollection(t *testing.T) {
	module, database, ctx := round290Media(t)
	parent, err := module.createCollection(ctx, CollectionCreateIn{Name: "Parent", ParentID: 1})
	if err != nil {
		t.Fatal(err)
	}
	child, err := module.createCollection(ctx, CollectionCreateIn{Name: "Child", ParentID: api.ID(parent.Collection.ID)})
	if err != nil {
		t.Fatal(err)
	}
	_, err = module.deleteCollection(ctx, CollectionDeleteIn{ID: 1})
	mediaRound290Status(t, err, http.StatusForbidden)
	_, err = module.deleteCollection(ctx, CollectionDeleteIn{ID: api.ID(parent.Collection.ID)})
	mediaRound290Status(t, err, http.StatusUnprocessableEntity)
	// No parent field is writable, so a caller cannot create a cycle by rename.
	changed, err := module.renameCollection(ctx, CollectionRenameIn{ID: api.ID(parent.Collection.ID), BaseVersion: parent.Collection.Version, Changes: map[string]any{"parent_id": child.Collection.ID}})
	if err != nil {
		t.Fatal(err)
	}
	if len(changed.Saved) != 0 || len(changed.Fields["parent_id"]) == 0 {
		t.Fatalf("parent mutation accepted: %+v", changed)
	}
	var actualParent int64
	if err := database.ReadPool().QueryRowContext(ctx.Context, "SELECT parent_id FROM image_collections WHERE id=?", parent.Collection.ID).Scan(&actualParent); err != nil || actualParent != 1 {
		t.Fatalf("parent changed: %d %v", actualParent, err)
	}
	_, err = module.deleteCollection(ctx, CollectionDeleteIn{ID: api.ID(child.Collection.ID)})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := module.deleteCollection(ctx, CollectionDeleteIn{ID: api.ID(parent.Collection.ID)}); err != nil {
		t.Fatal(err)
	}
}

func TestRound290ImageEditAndCollectionReferenceDeletionAreVersioned(t *testing.T) {
	module, database, ctx := round290Media(t)
	child, err := module.createCollection(ctx, CollectionCreateIn{Name: "Images", ParentID: 1})
	if err != nil {
		t.Fatal(err)
	}
	err = database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,uploader_id,created_at,version) VALUES(100,?,'Original','fake.webp',10,10,10,1,'2026-10-11T00:00:00Z',1)", child.Collection.ID)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = module.deleteCollection(ctx, CollectionDeleteIn{ID: api.ID(child.Collection.ID)})
	mediaRound290Status(t, err, http.StatusUnprocessableEntity)
	receipt, err := module.editImage(ctx, EditImageIn{ID: 100, BaseVersion: 1, Changes: map[string]any{"title": "Edited", "collection_id": float64(1)}})
	if err != nil || receipt.Version != 2 || len(receipt.Saved) != 2 {
		t.Fatalf("image save: %+v %v", receipt, err)
	}
	_, err = module.editImage(ctx, EditImageIn{ID: 100, BaseVersion: 1, Changes: map[string]any{"title": "STALE"}})
	stale := mediaRound290Status(t, err, http.StatusConflict)
	if stale.Current == nil {
		t.Fatal("stale image edit omitted safe current values")
	}
	var title string
	if err := database.ReadPool().QueryRowContext(ctx.Context, "SELECT title FROM images WHERE id=100").Scan(&title); err != nil || title != "Edited" {
		t.Fatalf("stale overwrite: %s %v", title, err)
	}
	if _, err := module.deleteCollection(ctx, CollectionDeleteIn{ID: api.ID(child.Collection.ID)}); err != nil {
		t.Fatal(err)
	}
}

func TestRound290ReferencedImageDeleteFallsBackInsteadOfDeletingArticle(t *testing.T) {
	module, database, ctx := round290Media(t)
	err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(c, "INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,uploader_id,created_at,version) VALUES(100,1,'Cover','fake.webp',10,10,10,1,'2026-10-11T00:00:00Z',1)"); err != nil {
			return err
		}
		if _, err := tx.ExecContext(c, "INSERT INTO pages(id,kind,slug,title,live,created_at,updated_at) VALUES(1000,'article','image-delete','Keep article',1,'2026-10-11T00:00:00Z','2026-10-11T00:00:00Z')"); err != nil {
			return err
		}
		_, err := tx.ExecContext(c, "INSERT INTO articles(page_id,cover_image_id) VALUES(1000,100)")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := module.svc.DeleteImage(ctx, 100); err != nil {
		t.Fatal(err)
	}
	var count int
	if err := database.ReadPool().QueryRowContext(ctx.Context, "SELECT COUNT(*) FROM articles WHERE page_id=1000 AND cover_image_id IS NULL").Scan(&count); err != nil || count != 1 {
		t.Fatalf("article lost or cover not reset: %d %v", count, err)
	}
}

func TestRound290ContributorCanChooseImagesButCannotEditOrCreateCollections(t *testing.T) {
	module, _, ctx := round290Media(t)
	ctx.Viewer.Superuser = false
	ctx.Viewer.Caps = map[app.Cap]struct{}{"admin.enter": {}, "images.contribute": {}}
	resolver := func(*http.Request) *app.Viewer { return ctx.Viewer }
	registry := &api.Registry{}
	module.Routes(registry)
	handler := registry.Handler(resolver)
	for _, path := range []string{"/api/admin/images", "/api/admin/image-collections"} {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, path, nil))
		if recorder.Code != http.StatusOK {
			t.Fatalf("contributor chooser %s: %d %s", path, recorder.Code, recorder.Body.String())
		}
	}
	cases := []struct{ method, path, body string }{
		{http.MethodPatch, "/api/admin/images/100", `{"base_version":1,"changes":{"title":"Blocked"}}`},
		{http.MethodPost, "/api/admin/image-collections", `{"name":"Blocked","parent_id":1}`},
	}
	for _, item := range cases {
		request := httptest.NewRequest(item.method, item.path, strings.NewReader(item.body))
		request.Header.Set("Content-Type", "application/json")
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, request)
		if recorder.Code != http.StatusForbidden {
			t.Fatalf("contributor write %s: %d %s", item.path, recorder.Code, recorder.Body.String())
		}
	}
}
