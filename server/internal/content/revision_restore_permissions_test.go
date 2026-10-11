package content

import (
	"encoding/json"
	"net/http"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

func TestRestoreRevisionPreservesCurrentProtectedFieldsForContributor(t *testing.T) {
	m, _, owner, _ := round290Module(t)
	category := &Category{Name: "Open restore", Slug: "open-restore", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(owner.Context, category); err != nil {
		t.Fatal(err)
	}
	created, err := m.svc.CreateDraft(owner, CreateDraftInput{Title: "Current title", BodyMD: "Current body", CategoryID: &category.ID})
	if err != nil {
		t.Fatal(err)
	}
	article, err := m.authorizedArticle(owner, created.ID)
	if err != nil {
		t.Fatal(err)
	}
	current := articleDraft(article)
	history := current
	other := int64(2)
	future := time.Now().Add(24 * time.Hour).UTC()
	history.AuthorID = &other
	history.Title = "Historical title"
	history.BodyMD = "Historical body"
	history.CommentsEnabled = false
	history.Slug = "historical-slug"
	history.SeoTitle = "Historical SEO"
	history.SearchDescription = "Historical search description"
	history.GoLiveAt = &future
	history.ExpireAt = &future
	write := func(version int64, draft ArticleRevisionContent) (int64, int64) {
		t.Helper()
		raw, err := json.Marshal(draft)
		if err != nil {
			t.Fatal(err)
		}
		next, revision, err := m.svc.store.SaveArticleDraft(owner.Context, created.ID, version, string(raw), owner.Viewer.ID, 0)
		if err != nil {
			t.Fatal(err)
		}
		return next, revision
	}
	version, historicalID := write(created.Version, history)
	version, _ = write(version, current)
	restored, err := m.restoreRevision(owner, RestoreRevisionIn{ID: api.ID(created.ID), Revision: api.ID(historicalID), BaseVersion: version})
	if err != nil {
		t.Fatal(err)
	}
	detail, err := m.adminGetArticleDetail(owner, AdminArticleDetailIn{ID: api.ID(created.ID)})
	if err != nil {
		t.Fatal(err)
	}
	draft := detail.Revision
	if draft == nil || draft.Title != history.Title || draft.BodyMD != history.BodyMD {
		t.Fatalf("editable historical fields not restored: %+v", draft)
	}
	if draft.AuthorID == nil || *draft.AuthorID != owner.Viewer.ID || !draft.CommentsEnabled || draft.Slug != current.Slug || draft.SeoTitle != current.SeoTitle || draft.SearchDescription != current.SearchDescription || draft.GoLiveAt != nil || draft.ExpireAt != nil {
		t.Fatalf("historical protected fields leaked into contributor draft: %+v", draft)
	}
	// The same historical author and schedule remain available to a caller who
	// actually holds those permissions. Do not strip admin edits globally.
	owner.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	owner.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	_, err = m.restoreRevision(owner, RestoreRevisionIn{ID: api.ID(created.ID), Revision: api.ID(historicalID), BaseVersion: restored.Version})
	if err != nil {
		t.Fatal(err)
	}
	detail, err = m.adminGetArticleDetail(owner, AdminArticleDetailIn{ID: api.ID(created.ID)})
	if err != nil {
		t.Fatal(err)
	}
	if detail.Revision.AuthorID == nil || *detail.Revision.AuthorID != other || detail.Revision.CommentsEnabled || detail.Revision.Slug != history.Slug || detail.Revision.GoLiveAt == nil || !detail.Revision.GoLiveAt.Equal(future) {
		t.Fatalf("authorized restoration lost historical fields: %+v", detail.Revision)
	}
}

func TestRestoreAndPublishRecheckClosedCategoryWithoutChangingDraft(t *testing.T) {
	m, _, owner, _ := round290Module(t)
	category := &Category{Name: "Later closes", Slug: "later-closes", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(owner.Context, category); err != nil {
		t.Fatal(err)
	}
	created, err := m.svc.CreateDraft(owner, CreateDraftInput{Title: "Waiting article", BodyMD: "Actual body", CategoryID: &category.ID})
	if err != nil {
		t.Fatal(err)
	}
	latest, err := m.svc.store.GetLatestRevision(owner.Context, created.ID)
	if err != nil || latest == nil {
		t.Fatalf("latest revision: %+v %v", latest, err)
	}
	category.AllowSubmission = false
	if err := m.svc.store.UpdateCategory(owner.Context, category); err != nil {
		t.Fatal(err)
	}
	_, err = m.restoreRevision(owner, RestoreRevisionIn{ID: api.ID(created.ID), Revision: api.ID(latest.ID), BaseVersion: created.Version})
	failure := round290ErrorStatus(t, err, http.StatusUnprocessableEntity)
	if len(failure.Fields["category_id"]) == 0 {
		t.Fatalf("restore missing category gate: %+v", failure)
	}
	_, err = m.svc.Publish(owner, created.ID, PublishInput{BaseVersion: created.Version})
	failure = round290ErrorStatus(t, err, http.StatusUnprocessableEntity)
	if len(failure.Fields["category_id"]) == 0 {
		t.Fatalf("publish missing category gate: %+v", failure)
	}
	article, err := m.svc.store.GetArticleByID(owner.Context, created.ID)
	if err != nil || article.Live || article.Version != created.Version || article.LatestRevisionID == nil || *article.LatestRevisionID != latest.ID {
		t.Fatalf("rejected restore/publish changed article: %+v %v", article, err)
	}
	owner.Viewer.Roles = map[string]struct{}{"certified_author": {}}
	published, err := m.svc.Publish(owner, created.ID, PublishInput{BaseVersion: created.Version})
	if err != nil || !published.Live {
		t.Fatalf("certified author cannot publish closed category: %+v %v", published, err)
	}
}
