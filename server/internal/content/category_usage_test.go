package content

import (
	"context"
	"net/http"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestCategoryUsageAndDeletionIncludeLatestArticleDraft(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	stored := &Category{Name: "Stored", Slug: "stored"}
	draft := &Category{Name: "Draft", Slug: "draft"}
	for _, category := range []*Category{stored, draft} {
		if err := m.svc.store.CreateCategory(editor.Context, category); err != nil {
			t.Fatal(err)
		}
	}
	article := round290Create(t, m, editor, "Article", "Body")
	err := database.WriteTx(editor.Context, func(c context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(c, "UPDATE articles SET category_id=? WHERE page_id=?", stored.ID, article.ID); err != nil {
			return err
		}
		_, err := tx.ExecContext(c, "UPDATE pages SET live=1,live_revision_id=latest_revision_id WHERE id=?", article.ID)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	saved, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: article.Version, Changes: map[string]any{"category_id": float64(draft.ID)}})
	if err != nil || len(saved.Fields) != 0 {
		t.Fatalf("draft category save: %+v %v", saved, err)
	}
	listed, err := m.svc.store.ListCategories(editor.Context)
	if err != nil {
		t.Fatal(err)
	}
	for _, category := range listed {
		want := 0
		if category.ID == draft.ID {
			want = 1
		}
		if category.ArticleCount != want {
			t.Fatalf("one article must count under its latest draft category: %+v", category)
		}
	}
	draft.Name = "Renamed draft category"
	if err := m.svc.store.UpdateCategory(editor.Context, draft); err != nil {
		t.Fatal(err)
	}
	if draft.ArticleCount != 1 {
		t.Fatalf("save receipt lost draft use count: %+v", draft)
	}
	round290ErrorStatus(t, m.svc.store.DeleteCategory(editor.Context, draft.ID), http.StatusUnprocessableEntity)
	// The old published row still has a real FK reference and remains protected.
	round290ErrorStatus(t, m.svc.store.DeleteCategory(editor.Context, stored.ID), http.StatusUnprocessableEntity)
	cleared, err := m.svc.SaveDraft(editor, article.ID, SaveDraftInput{BaseVersion: saved.Version, Changes: map[string]any{"category_id": nil}})
	if err != nil || len(cleared.Fields) != 0 {
		t.Fatalf("clear category save: %+v %v", cleared, err)
	}
	if err := m.svc.store.DeleteCategory(editor.Context, draft.ID); err != nil {
		t.Fatalf("unused old draft category remains blocked: %v", err)
	}
}
