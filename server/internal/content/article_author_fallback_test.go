package content

import "testing"

func TestClearingArticleAuthorFallsBackToOwnerRatherThanEditingUser(t *testing.T) {
	m, _, owner, editor := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	editor.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	category := &Category{Name: "Open", Slug: "open", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(owner.Context, category); err != nil {
		t.Fatal(err)
	}
	created, err := m.svc.CreateDraft(owner, CreateDraftInput{Title: "Written by owner", CategoryID: &category.ID, BodyMD: "Body"})
	if err != nil {
		t.Fatal(err)
	}
	changed, err := m.svc.SaveDraft(editor, created.ID, SaveDraftInput{BaseVersion: created.Version, Changes: map[string]any{"author_id": float64(editor.Viewer.ID)}})
	if err != nil || len(changed.Fields) != 0 {
		t.Fatalf("change author: %+v %v", changed, err)
	}
	cleared, err := m.svc.SaveDraft(editor, created.ID, SaveDraftInput{BaseVersion: changed.Version, Changes: map[string]any{"author_id": nil}})
	if err != nil || len(cleared.Fields) != 0 || cleared.Values["author_id"] != owner.Viewer.ID {
		t.Fatalf("clear author did not return owner fallback: %+v %v", cleared, err)
	}
	article, err := m.svc.store.GetArticleByID(owner.Context, created.ID)
	if err != nil {
		t.Fatal(err)
	}
	detail, err := m.editorProjection(editor, article)
	if err != nil || detail.Revision.AuthorID == nil || *detail.Revision.AuthorID != owner.Viewer.ID {
		t.Fatalf("saved clear changed author to editor or nil: %+v %v", detail.Revision, err)
	}
	published, err := m.svc.Publish(editor, created.ID, PublishInput{BaseVersion: cleared.Version})
	if err != nil || published.AuthorID == nil || *published.AuthorID != owner.Viewer.ID {
		t.Fatalf("published cleared author: %+v %v", published, err)
	}
}
