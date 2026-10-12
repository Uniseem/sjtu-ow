package media

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestRound294ContributorLibraryIsLimitedToSubmissionTree(t *testing.T) {
	module, database, ctx := round290Media(t)
	err := database.WriteTx(ctx.Context, func(c context.Context, tx *db.Tx) error {
		for _, query := range []string{
			"INSERT INTO image_collections(id,name,key,parent_id,created_at) VALUES(101,'Submission child','submission_child',4,'x')",
			"INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,created_at) VALUES(101,4,'Submitted','a.png',10,20,20,'x'),(102,101,'Child','b.png',10,20,20,'x'),(103,2,'Private cover','c.png',10,20,20,'x')",
		} {
			if _, err := tx.ExecContext(c, query); err != nil {
				return err
			}
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	ctx.Viewer = &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}, "images.contribute": {}}}
	listed, err := module.listImages(ctx, ListImagesIn{Page: 1, PageSize: 48})
	if err != nil || listed.Total != 2 || len(listed.Items) != 2 {
		t.Fatalf("library leak: %+v %v", listed, err)
	}
	hiddenID := int64(2)
	hidden, err := module.listImages(ctx, ListImagesIn{CollectionID: &hiddenID})
	if err != nil || hidden.Total != 0 {
		t.Fatalf("filter bypass: %+v %v", hidden, err)
	}
	collections, err := module.listCollections(ctx, struct{}{})
	if err != nil || len(collections.Collections) != 2 {
		t.Fatalf("collection leak: %+v %v", collections, err)
	}
	for _, collection := range collections.Collections {
		if !collection.CanUpload || collection.CanAdd {
			t.Fatalf("mixed upload/collection rights: %+v", collection)
		}
	}
	for _, id := range []int64{101, 102, 103} {
		allowed, err := CanChooseImage(ctx.Context, database.ReadPool(), ctx.Viewer, id)
		if err != nil || allowed != (id != 103) {
			t.Fatalf("choose %d: %v %v", id, allowed, err)
		}
	}
	_, err = module.uploadImage(ctx, UploadImageIn{CollectionKey: "default_cover", DataURL: "invalid"})
	mediaRound290Status(t, err, http.StatusForbidden)
	_, err = module.uploadImage(ctx, UploadImageIn{CollectionKey: "missing", DataURL: "invalid"})
	mediaRound290Status(t, err, http.StatusForbidden)
	// The permitted target reaches decoding rather than a blanket denial.
	_, err = module.uploadImage(ctx, UploadImageIn{CollectionKey: "submission_child", DataURL: "invalid"})
	mediaRound290Status(t, err, http.StatusBadRequest)
	ctx.Viewer.Superuser = true
	all, err := module.listImages(ctx, ListImagesIn{})
	if err != nil || all.Total != 3 {
		t.Fatalf("manager lost full library: %+v %v", all, err)
	}
}

func TestRound294MultipartUploadRejectsMissingSessionBeforeReadingBody(t *testing.T) {
	module, _, _ := round290Media(t)
	for _, viewer := range []*app.Viewer{nil, {ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}}}} {
		module.SetUploadResolver(func(*http.Request) *app.Viewer { return viewer })
		request := httptest.NewRequest(http.MethodPost, "/api/admin/images/upload-file", nil)
		recorder := httptest.NewRecorder()
		module.ServeUploadHTTP(recorder, request)
		want := http.StatusUnauthorized
		if viewer != nil {
			want = http.StatusForbidden
		}
		if recorder.Code != want {
			t.Fatalf("multipart gate: %d want %d", recorder.Code, want)
		}
	}
}

func TestRound294ImageEditorRequiresManageAndMissingImageIs404(t *testing.T) {
	module, _, ctx := round290Media(t)
	var registry api.Registry
	module.Routes(&registry)
	viewer := &app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{"admin.enter": {}, "images.contribute": {}}}
	handler := registry.Handler(func(*http.Request) *app.Viewer { return viewer })
	request := httptest.NewRequest(http.MethodGet, "/api/admin/images/99999", nil)
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusForbidden {
		t.Fatalf("contributor editor gate: %d", recorder.Code)
	}
	viewer = ctx.Viewer
	recorder = httptest.NewRecorder()
	handler.ServeHTTP(recorder, request)
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("missing editor image: %d", recorder.Code)
	}
	recorder = httptest.NewRecorder()
	handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/api/images/99999", nil))
	if recorder.Code != http.StatusNotFound {
		t.Fatalf("public missing image: %d", recorder.Code)
	}
}
