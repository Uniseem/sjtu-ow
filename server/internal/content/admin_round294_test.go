package content

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestRound294EditorChoicesMatchLegacyNamedCategoriesAndDraftTournaments(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	for _, category := range []*Category{{Name: "Named", Slug: "named"}, {Name: "", Slug: "empty"}} {
		if err := m.svc.store.CreateCategory(editor.Context, category); err != nil {
			t.Fatal(err)
		}
	}
	err := database.WriteTx(editor.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "INSERT INTO tournaments(id,title,status,created_at,updated_at) VALUES(101,'Draft tournament','draft','x','x')")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	projection, err := m.newArticleEditor(editor, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	if len(projection.Categories) != 1 || projection.Categories[0].Name != "Named" {
		t.Fatalf("unnamed category offered: %+v", projection.Categories)
	}
	if len(projection.Tournaments) != 1 || projection.Tournaments[0].ID != 101 {
		t.Fatalf("draft tournament missing: %+v", projection.Tournaments)
	}
}

func TestRound294EmptySlugIsSavedAndUnsafeSlugCannotReplaceIt(t *testing.T) {
	m, _, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	article := round290Create(t, m, editor, "Title", "Body")
	saved, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: article.Version, Changes: map[string]any{"slug": "custom"}})
	if err != nil {
		t.Fatal(err)
	}
	cleared, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: saved.Version, Changes: map[string]any{"slug": ""}})
	if err != nil || len(cleared.Saved) != 1 || cleared.Version != saved.Version+1 {
		t.Fatalf("empty slug save: %+v %v", cleared, err)
	}
	for _, slug := range []string{"a/b", "a?b", "a#b", "a.b", "a b"} {
		rejected, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: cleared.Version, Changes: map[string]any{"slug": slug}})
		if err != nil || len(rejected.Fields["slug"]) == 0 || len(rejected.Saved) != 0 || rejected.Version != cleared.Version {
			t.Fatalf("unsafe slug accepted %q: %+v %v", slug, rejected, err)
		}
	}
	detail, err := m.adminGetArticleDetail(editor, AdminArticleDetailIn{ID: api.ID(article.ID)})
	if err != nil || detail.Revision.Slug != "" {
		t.Fatalf("clear not persisted: %+v %v", detail.Revision, err)
	}
}

func TestRound294ScheduleRejectsEqualBoundaryButAllowsUnrelatedEditAfterExpiry(t *testing.T) {
	m, _, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	now := time.Date(2026, 10, 12, 0, 0, 0, 0, time.UTC)
	editor.Clock = clock.Fixed(now)
	article := round290Create(t, m, editor, "Title", "Body")
	start := now.Add(time.Hour).Format(time.RFC3339)
	equal, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: article.Version, Changes: map[string]any{"go_live_at": start, "expire_at": start}})
	if err != nil || len(equal.Fields["expire_at"]) == 0 {
		t.Fatalf("equal schedule accepted: %+v %v", equal, err)
	}
	end := now.Add(2 * time.Hour).Format(time.RFC3339)
	saved, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: equal.Version, Changes: map[string]any{"expire_at": end}})
	if err != nil || len(saved.Fields) != 0 {
		t.Fatalf("future expiry: %+v %v", saved, err)
	}
	editor.Clock = clock.Fixed(now.Add(3 * time.Hour))
	unrelated, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: saved.Version, Changes: map[string]any{"summary": "New summary"}})
	if err != nil || len(unrelated.Fields) != 0 {
		t.Fatalf("untouched historical expiry blocked edit: %+v %v", unrelated, err)
	}
	detail, err := m.adminGetArticleDetail(editor, AdminArticleDetailIn{ID: api.ID(article.ID)})
	if err != nil || detail.Revision.ExpireAt == nil || detail.Revision.ExpireAt.Format(time.RFC3339) != end {
		t.Fatalf("historical expiry cleared: %+v %v", detail.Revision, err)
	}
}

func TestRound294SitePartsExposesDraftTitleWithoutChangingPublishedTitle(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	err := database.WriteTx(editor.Context, func(c context.Context, tx *db.Tx) error {
		for _, query := range []string{
			"INSERT INTO pages(id,kind,slug,title,live,version,created_at,updated_at) VALUES(1000,'site_page','about','Live title',1,1,'x','x'),(1001,'news_index','news','News',1,1,'x','x')",
			"INSERT INTO site_pages(page_id,body_md,body_html,body_plain) VALUES(1000,'Live','Live','Live')",
			"INSERT INTO news_index(page_id,intro) VALUES(1001,'Intro')",
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
	_, err = m.patchPlainPage(editor, PlainPagePatchIn{ID: 1000, BaseVersion: 1, Changes: map[string]any{"title": "Draft title"}})
	if err != nil {
		t.Fatal(err)
	}
	parts, err := m.listSiteParts(editor, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	if len(parts.Items) != 1 || parts.Items[0].Title != "Live title" || parts.Items[0].DraftTitle == nil || *parts.Items[0].DraftTitle != "Draft title" {
		t.Fatalf("draft list title lost or live changed: %+v", parts.Items)
	}
	public, err := m.svc.store.GetSitePageBySlug(editor.Context, "about")
	if err != nil || public.Title != "Live title" || strings.Contains(public.BodyMD, "Draft") {
		t.Fatalf("list projection published draft: %+v %v", public, err)
	}
}

func TestRound294ContributorCannotChooseOtherLibraryButCanRetainExistingCover(t *testing.T) {
	m, database, writer, _ := round290Module(t)
	writer.Viewer.Caps["images.contribute"] = struct{}{}
	err := database.WriteTx(writer.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,created_at) VALUES(701,1,'Restricted','a.png',10,20,20,'x'),(702,4,'Submitted','b.png',10,20,20,'x'),(703,1,'Another restricted','c.png',10,20,20,'x')")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	created := round290Create(t, m, writer, "Article", "Body")
	rejected, err := m.svc.SaveDraft(writer, created.ID, SaveDraftInput{BaseVersion: created.Version, Changes: map[string]any{"cover_image_id": float64(701)}})
	if err != nil || len(rejected.Fields["cover_image_id"]) == 0 || len(rejected.Saved) != 0 {
		t.Fatalf("restricted cover accepted: %+v %v", rejected, err)
	}
	allowed, err := m.svc.SaveDraft(writer, created.ID, SaveDraftInput{BaseVersion: created.Version, Changes: map[string]any{"cover_image_id": float64(702)}})
	if err != nil || len(allowed.Fields) != 0 {
		t.Fatalf("contribution rejected: %+v %v", allowed, err)
	}
	// An editor can have selected a restricted cover for the author's draft.
	writer.Viewer.Caps["images.manage"] = struct{}{}
	editorial, err := m.svc.SaveDraft(writer, created.ID, SaveDraftInput{BaseVersion: allowed.Version, Changes: map[string]any{"cover_image_id": float64(701)}})
	if err != nil {
		t.Fatal(err)
	}
	delete(writer.Viewer.Caps, "images.manage")
	retained, err := m.svc.SaveDraft(writer, created.ID, SaveDraftInput{BaseVersion: editorial.Version, Changes: map[string]any{"cover_image_id": float64(701), "summary": "Edit unrelated text"}})
	if err != nil || len(retained.Fields) != 0 {
		t.Fatalf("existing cover exception lost: %+v %v", retained, err)
	}
	another, err := m.svc.SaveDraft(writer, created.ID, SaveDraftInput{BaseVersion: retained.Version, Changes: map[string]any{"cover_image_id": float64(703)}})
	if err != nil || len(another.Fields["cover_image_id"]) == 0 {
		t.Fatalf("existing cover exception broadened: %+v %v", another, err)
	}
}

func TestRound294CoverWriteRechecksCollectionAfterConcurrentMove(t *testing.T) {
	m, database, writer, _ := round290Module(t)
	writer.Viewer.Caps["images.contribute"] = struct{}{}
	err := database.WriteTx(writer.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "INSERT INTO images(id,collection_id,title,file_name,file_size,width,height,created_at) VALUES(801,4,'Submitted','a.png',10,20,20,'x')")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	created := round290Create(t, m, writer, "Article", "Body")
	fields, err := m.svc.validateArticleChanges(writer, map[string]any{"cover_image_id": float64(801)})
	if err != nil || len(fields) != 0 {
		t.Fatalf("initial choose denied: %+v %v", fields, err)
	}
	// A manager moves the image between the read check and the draft write.
	err = database.WriteTx(writer.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE images SET collection_id=1 WHERE id=801")
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	id := int64(801)
	_, _, err = m.svc.store.SaveArticleDraft(writer.Context, created.ID, created.Version, `{"title":"Should not persist","cover_image_id":801}`, writer.Viewer.ID, 0, coverWriteCheck(writer.Viewer, &id, nil))
	round290ErrorStatus(t, err, 403)
	detail, err := m.adminGetArticleDetail(writer, AdminArticleDetailIn{ID: api.ID(created.ID)})
	if err != nil || detail.Version != created.Version || detail.Revision.CoverImageID != nil {
		t.Fatalf("collection race bypass: %+v %v", detail, err)
	}
}
