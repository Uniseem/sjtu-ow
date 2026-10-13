package content

import (
	"net/http"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
)

func TestRealArticlePublishApprovesScheduledRevisionAndImmediatePublishClearsIt(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	editor.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	now := time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC)
	editor.Clock = clock.Fixed(now)
	category := &Category{Name: "Category", Slug: "category", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(editor.Context, category); err != nil {
		t.Fatal(err)
	}
	draft, err := m.svc.CreateDraft(editor, CreateDraftInput{Title: "Scheduled article", CategoryID: &category.ID, BodyMD: "Body"})
	if err != nil {
		t.Fatal(err)
	}
	future := now.Add(time.Hour)
	saved, err := m.svc.SaveDraft(editor, draft.ID, SaveDraftInput{BaseVersion: draft.Version, Changes: map[string]any{"go_live_at": future.Format(time.RFC3339)}})
	if err != nil || len(saved.Fields) != 0 {
		t.Fatalf("save schedule: %+v %v", saved, err)
	}
	before, err := m.listEditableArticles(editor, AdminListArticlesIn{Status: "scheduled"})
	if err != nil || before.Total != 0 {
		t.Fatalf("typed time prematurely approved: %+v %v", before, err)
	}
	published, err := m.svc.Publish(editor, draft.ID, PublishInput{BaseVersion: saved.Version})
	if err != nil || published.Live {
		t.Fatalf("publish schedule: %+v %v", published, err)
	}
	if published.FirstPublishedAt != nil || published.LastPublishedAt != nil || published.LiveRevisionID != nil || !published.ApprovedSchedule {
		t.Fatalf("first scheduled revision falsely reported a past publication: %+v", published)
	}
	scheduled, err := m.listEditableArticles(editor, AdminListArticlesIn{Status: "scheduled"})
	if err != nil || len(scheduled.Items) != 1 || scheduled.Items[0].ID != draft.ID || !scheduled.Items[0].ApprovedSchedule || !scheduled.Items[0].CanAnnounce {
		t.Fatalf("real published schedule/announcement state: %+v %v", scheduled, err)
	}
	latest, err := m.svc.store.GetLatestRevision(editor.Context, draft.ID)
	if err != nil || latest.ApprovedGoLiveAt == nil || !latest.ApprovedGoLiveAt.Equal(future) {
		t.Fatalf("latest revision approval: %+v %v", latest, err)
	}
	subject, err := m.svc.AnnounceKind().Load(editor.Context, database.ReadPool(), draft.ID)
	if err != nil || subject == nil || subject.GoLiveAt == nil || !subject.GoLiveAt.Equal(future) {
		t.Fatalf("scheduled notification subject: %+v %v", subject, err)
	}
	cleared, err := m.svc.SaveDraft(editor, draft.ID, SaveDraftInput{BaseVersion: published.Version, Changes: map[string]any{"go_live_at": nil}})
	if err != nil || len(cleared.Fields) != 0 {
		t.Fatalf("clear future time: %+v %v", cleared, err)
	}
	before, err = m.listEditableArticles(editor, AdminListArticlesIn{Status: "scheduled"})
	if err != nil || before.Total != 1 {
		t.Fatalf("unsaved publication change removed prior approval: %+v %v", before, err)
	}
	immediate, err := m.svc.Publish(editor, draft.ID, PublishInput{BaseVersion: cleared.Version})
	if err != nil || !immediate.Live {
		t.Fatalf("immediate publish: %+v %v", immediate, err)
	}
	var remaining int
	if err := database.ReadPool().QueryRowContext(editor.Context, "SELECT COUNT(*) FROM page_revisions WHERE page_id=? AND approved_go_live_at IS NOT NULL", draft.ID).Scan(&remaining); err != nil || remaining != 0 {
		t.Fatalf("obsolete approved schedule remains: %d %v", remaining, err)
	}
	listed, err := m.listEditableArticles(editor, AdminListArticlesIn{Status: "live"})
	if err != nil || len(listed.Items) != 1 || listed.Items[0].ApprovedSchedule || !listed.Items[0].CanAnnounce {
		t.Fatalf("immediate published state: %+v %v", listed, err)
	}
}

func TestSchedulingRevisionKeepsPublishedArticleAndLaterDraftSeparate(t *testing.T) {
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	editor.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	now := time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC)
	editor.Clock = clock.Fixed(now)
	category := &Category{Name: "Category", Slug: "category", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(editor.Context, category); err != nil {
		t.Fatal(err)
	}
	plannedCategory := &Category{Name: "Planned", Slug: "planned", AllowSubmission: true}
	privateCategory := &Category{Name: "Private", Slug: "private", AllowSubmission: true}
	for _, item := range []*Category{plannedCategory, privateCategory} {
		if err := m.svc.store.CreateCategory(editor.Context, item); err != nil {
			t.Fatal(err)
		}
	}
	draft, err := m.svc.CreateDraft(editor, CreateDraftInput{Title: "Published A", CategoryID: &category.ID, BodyMD: "Public body A"})
	if err != nil {
		t.Fatal(err)
	}
	a, err := m.svc.Publish(editor, draft.ID, PublishInput{BaseVersion: draft.Version})
	if err != nil || !a.Live || a.FirstPublishedAt == nil || a.LastPublishedAt == nil || a.LiveRevisionID == nil {
		t.Fatalf("publish A: %+v %v", a, err)
	}
	future := now.Add(time.Hour)
	b, err := m.svc.SaveDraft(editor, draft.ID, SaveDraftInput{BaseVersion: a.Version, Changes: map[string]any{"title": "Scheduled B", "body_md": "Scheduled body B", "category_id": float64(plannedCategory.ID), "go_live_at": future.Format(time.RFC3339)}})
	if err != nil || len(b.Fields) != 0 {
		t.Fatalf("save B: %+v %v", b, err)
	}
	approved, err := m.svc.Publish(editor, draft.ID, PublishInput{BaseVersion: b.Version})
	if err != nil {
		t.Fatal(err)
	}
	if !approved.Live || approved.Title != a.Title || approved.BodyMD != a.BodyMD || approved.BodyHTML != a.BodyHTML || approved.LiveRevisionID == nil || *approved.LiveRevisionID != *a.LiveRevisionID || approved.FirstPublishedAt == nil || approved.LastPublishedAt == nil || !approved.FirstPublishedAt.Equal(*a.FirstPublishedAt) || !approved.LastPublishedAt.Equal(*a.LastPublishedAt) || !approved.ApprovedSchedule {
		t.Fatalf("approving B replaced public A or publication metadata: %+v", approved)
	}
	approvedRevision := *approved.LatestRevisionID
	c, err := m.svc.SaveDraft(editor, draft.ID, SaveDraftInput{BaseVersion: approved.Version, Changes: map[string]any{"title": "Unapproved C", "body_md": "Private draft body C", "category_id": float64(privateCategory.ID)}})
	if err != nil || len(c.Fields) != 0 {
		t.Fatalf("save C: %+v %v", c, err)
	}
	latest, err := m.svc.store.GetLatestRevision(editor.Context, draft.ID)
	if err != nil || latest.ID == approvedRevision || latest.ApprovedGoLiveAt != nil {
		t.Fatalf("C overwrote approved B: %+v %v", latest, err)
	}
	var planRevision int64
	if err := database.ReadPool().QueryRowContext(editor.Context, "SELECT id FROM page_revisions WHERE page_id=? AND approved_go_live_at IS NOT NULL", draft.ID).Scan(&planRevision); err != nil || planRevision != approvedRevision {
		t.Fatalf("saving C cancelled plan B: %d %v", planRevision, err)
	}
	public, err := m.svc.store.GetArticleBySlug(editor.Context, a.Slug)
	if err != nil || !public.Live || public.Title != a.Title || public.BodyMD != a.BodyMD || public.LiveRevisionID == nil || *public.LiveRevisionID != *a.LiveRevisionID {
		t.Fatalf("public A after C: %+v %v", public, err)
	}
	if public.GoLiveAt != nil {
		t.Fatalf("public A acquired B's scheduled time: %+v", public)
	}
	publicPage, err := m.svc.ArticlePage(editor, a.Slug)
	if err != nil || publicPage.Title != a.Title || publicPage.BodyHTML != a.BodyHTML || publicPage.CategoryName != category.Name || publicPage.FirstPublishedAt == nil || publicPage.LastPublishedAt == nil || !publicPage.FirstPublishedAt.Equal(*a.FirstPublishedAt) || !publicPage.LastPublishedAt.Equal(*a.LastPublishedAt) {
		t.Fatalf("public API leaked B/C or changed A publication: %+v %v", publicPage, err)
	}
	detail, err := m.editorProjection(editor, public)
	if err != nil || detail.Revision.Title != "Unapproved C" || !detail.Article.HasUnpublishedChanges || !detail.Article.ApprovedSchedule || detail.Article.LatestRevisionID == nil || *detail.Article.LatestRevisionID != latest.ID {
		t.Fatalf("editor C and schedule B projection: %+v %v", detail, err)
	}
	listed, err := m.svc.store.ListCategories(editor.Context)
	if err != nil {
		t.Fatal(err)
	}
	for _, item := range listed {
		if item.CanDelete {
			t.Fatalf("published A, planned B and private C categories must all remain protected: %+v", item)
		}
		want := 0
		if item.ID == privateCategory.ID {
			want = 1
		}
		if item.ArticleCount != want {
			t.Fatalf("display must count each page only under its latest category: %+v", item)
		}
	}
	round290ErrorStatus(t, m.svc.store.DeleteCategory(editor.Context, plannedCategory.ID), http.StatusUnprocessableEntity)
	if err := m.svc.Unpublish(editor, draft.ID); err != nil {
		t.Fatal(err)
	}
	unpublished, err := m.svc.store.GetArticleByID(editor.Context, draft.ID)
	if err != nil || unpublished.Live || unpublished.LiveRevisionID != nil || unpublished.ApprovedSchedule || unpublished.Expired || unpublished.GoLiveAt != nil {
		t.Fatalf("manual unpublish retained a live revision or schedule: %+v %v", unpublished, err)
	}
	_, err = m.svc.ArticlePage(editor, a.Slug)
	round290ErrorStatus(t, err, http.StatusNotFound)
	if err := m.svc.store.DeleteCategory(editor.Context, plannedCategory.ID); err != nil {
		t.Fatalf("cancelled plan still protects its old category: %v", err)
	}
}
