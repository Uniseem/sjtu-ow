package content

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type workerArticleFixture struct {
	m                      *Module
	d                      *db.DB
	editor                 *app.Ctx
	now                    time.Time
	page, approved, latest int64
	before                 *Article
}

func scheduledWorkerFixture(t *testing.T, live bool, expiresOldVersion bool) workerArticleFixture {
	t.Helper()
	m, database, editor, _ := round290Module(t)
	editor.Viewer.Caps[CapArticlesEditAny] = struct{}{}
	editor.Viewer.Caps[CapArticlesEditAuthor] = struct{}{}
	now := time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC)
	editor.Clock = clock.Fixed(now)
	category := &Category{Name: "Worker category", Slug: "worker-category", AllowSubmission: true}
	if err := m.svc.store.CreateCategory(editor.Context, category); err != nil {
		t.Fatal(err)
	}
	created, err := m.svc.CreateDraft(editor, CreateDraftInput{Title: "Public A", CategoryID: &category.ID, BodyMD: "Original public body A"})
	if err != nil {
		t.Fatal(err)
	}
	version := created.Version
	if expiresOldVersion {
		result, err := m.svc.SaveDraft(editor, created.ID, SaveDraftInput{BaseVersion: version, Changes: map[string]any{"expire_at": now.Add(45 * time.Minute).Format(time.RFC3339)}})
		if err != nil || len(result.Fields) != 0 {
			t.Fatalf("expiry A: %+v %v", result, err)
		}
		version = result.Version
	}
	if live {
		published, err := m.svc.Publish(editor, created.ID, PublishInput{BaseVersion: version})
		if err != nil {
			t.Fatal(err)
		}
		version = published.Version
	}
	before, err := m.svc.store.GetArticleByID(editor.Context, created.ID)
	if err != nil {
		t.Fatal(err)
	}
	b, err := m.svc.SaveDraft(editor, created.ID, SaveDraftInput{BaseVersion: version, Changes: map[string]any{
		"title": "Approved B", "summary": "Approved summary", "body_md": "## Approved heading\nScheduled public body B",
		"go_live_at": now.Add(time.Hour).Format(time.RFC3339), "expire_at": now.Add(3 * time.Hour).Format(time.RFC3339),
	}})
	if err != nil || len(b.Fields) != 0 {
		t.Fatalf("save B: %+v %v", b, err)
	}
	approved, err := m.svc.Publish(editor, created.ID, PublishInput{BaseVersion: b.Version})
	if err != nil || !approved.ApprovedSchedule {
		t.Fatalf("approve B: %+v %v", approved, err)
	}
	approvedID := *approved.LatestRevisionID
	c, err := m.svc.SaveDraft(editor, created.ID, SaveDraftInput{BaseVersion: approved.Version, Changes: map[string]any{
		"title": "Private C", "body_md": "Unapproved private body C",
	}})
	if err != nil || len(c.Fields) != 0 {
		t.Fatalf("save C: %+v %v", c, err)
	}
	latest, err := m.svc.store.GetLatestRevision(editor.Context, created.ID)
	if err != nil || latest.ID == approvedID || latest.ApprovedGoLiveAt != nil {
		t.Fatalf("latest C: %+v %v", latest, err)
	}
	return workerArticleFixture{m: m, d: database, editor: editor, now: now, page: created.ID, approved: approvedID, latest: latest.ID, before: before}
}

func TestScheduledWorkerPublishesApprovedRevisionAndKeepsNewerPrivateDraft(t *testing.T) {
	for _, initiallyLive := range []bool{false, true} {
		name := "first publication"
		if initiallyLive {
			name = "replace live revision"
		}
		t.Run(name, func(t *testing.T) {
			fixture := scheduledWorkerFixture(t, initiallyLive, false)
			if err := fixture.d.WriteTx(fixture.editor.Context, func(c context.Context, tx *db.Tx) error {
				_, err := tx.ExecContext(c, "INSERT INTO broadcasts(kind,object_id,audience,waits_for_publish,created_at) VALUES('article',?,'everyone',1,?)", fixture.page, db.FormatUTC(fixture.now))
				return err
			}); err != nil {
				t.Fatal(err)
			}
			before, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
			if err != nil {
				t.Fatal(err)
			}
			for _, offset := range []time.Duration{30 * time.Minute, time.Hour} {
				if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, fixture.now.Add(offset)); err != nil {
					t.Fatal(err)
				}
				unchanged, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
				if err != nil || unchanged.Version != before.Version || unchanged.Live != initiallyLive {
					t.Fatalf("published before approval time: %+v %v", unchanged, err)
				}
			}
			due := fixture.now.Add(90 * time.Minute)
			if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, due); err != nil {
				t.Fatal(err)
			}
			article, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
			if err != nil {
				t.Fatal(err)
			}
			if !article.Live || article.Expired || article.Title != "Approved B" || article.Summary != "Approved summary" || !strings.Contains(article.BodyHTML, "Scheduled public body B") || strings.Contains(article.BodyHTML, "private body C") {
				t.Fatalf("worker published wrong body: %+v", article)
			}
			if article.LiveRevisionID == nil || *article.LiveRevisionID != fixture.approved || article.LatestRevisionID == nil || *article.LatestRevisionID != fixture.latest || !article.HasUnpublishedChanges || article.ApprovedSchedule {
				t.Fatalf("revision state: %+v", article)
			}
			if article.LastPublishedAt == nil || !article.LastPublishedAt.Equal(due) || article.FirstPublishedAt == nil {
				t.Fatalf("publication time: %+v", article)
			}
			if initiallyLive && !article.FirstPublishedAt.Equal(*fixture.before.FirstPublishedAt) || !initiallyLive && !article.FirstPublishedAt.Equal(due) {
				t.Fatalf("first publication time changed: %+v", article)
			}
			projection, err := fixture.m.editorProjection(fixture.editor, article)
			if err != nil || projection.Revision.Title != "Private C" || projection.Revision.BodyMD != "Unapproved private body C" {
				t.Fatalf("private latest draft lost: %+v %v", projection.Revision, err)
			}
			var waiting, jobs int
			if err := fixture.d.ReadPool().QueryRowContext(fixture.editor.Context, "SELECT waits_for_publish FROM broadcasts WHERE kind='article' AND object_id=?", fixture.page).Scan(&waiting); err != nil || waiting != 0 {
				t.Fatalf("waiting notification not released: %d %v", waiting, err)
			}
			if err := fixture.d.ReadPool().QueryRowContext(fixture.editor.Context, "SELECT COUNT(*) FROM jobs").Scan(&jobs); err != nil || jobs != 1 {
				t.Fatalf("notification delivery jobs=%d %v", jobs, err)
			}
			if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, due.Add(time.Minute)); err != nil {
				t.Fatal(err)
			}
			again, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
			if err != nil || again.Version != article.Version {
				t.Fatalf("worker republished same revision: %+v %v", again, err)
			}
			var repeatedJobs int
			if err := fixture.d.ReadPool().QueryRowContext(fixture.editor.Context, "SELECT COUNT(*) FROM jobs").Scan(&repeatedJobs); err != nil || repeatedJobs != jobs {
				t.Fatalf("duplicate waiting delivery=%d %v", repeatedJobs, err)
			}
		})
	}
}

func TestScheduledWorkerExpiryCancelsPlansAndCannotResurrectWithdrawnArticle(t *testing.T) {
	for _, offset := range []time.Duration{50 * time.Minute, 90 * time.Minute} {
		t.Run(offset.String(), func(t *testing.T) {
			fixture := scheduledWorkerFixture(t, true, true)
			// The old command uses strict expiry < now, then clears all plans.
			if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, fixture.now.Add(45*time.Minute)); err != nil {
				t.Fatal(err)
			}
			boundary, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
			if err != nil || !boundary.Live || boundary.Expired || !boundary.ApprovedSchedule {
				t.Fatalf("expired at exact boundary: %+v %v", boundary, err)
			}
			// At 90m A's expiry and B's approval are both due. Even though B's
			// own expiry is still future, expiring A cancels B before publication.
			if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, fixture.now.Add(offset)); err != nil {
				t.Fatal(err)
			}
			expired, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
			if err != nil {
				t.Fatal(err)
			}
			if expired.Live || !expired.Expired || expired.LiveRevisionID != nil || expired.ApprovedSchedule || !expired.HasUnpublishedChanges || expired.BodyMD != "Original public body A" || expired.LatestRevisionID == nil || *expired.LatestRevisionID != fixture.latest {
				t.Fatalf("expiry did not cancel B and preserve C: %+v", expired)
			}
			if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, fixture.now.Add(2*time.Hour)); err != nil {
				t.Fatal(err)
			}
			again, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
			if err != nil || again.Live || again.Version != expired.Version {
				t.Fatalf("cancelled plan resurrected page: %+v %v", again, err)
			}
		})
	}
}

func TestScheduledWorkerRechecksApprovalAfterConcurrentUnpublish(t *testing.T) {
	fixture := scheduledWorkerFixture(t, true, false)
	due := fixture.now.Add(90 * time.Minute)
	candidates, err := approvedArticleCandidates(fixture.editor.Context, fixture.d.ReadPool(), due)
	if err != nil || len(candidates) != 1 {
		t.Fatalf("candidates=%v %v", candidates, err)
	}
	if err := fixture.m.svc.Unpublish(fixture.editor, fixture.page); err != nil {
		t.Fatal(err)
	}
	before, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
	if err != nil {
		t.Fatal(err)
	}
	var published *Article
	err = fixture.d.WriteTx(fixture.editor.Context, func(c context.Context, tx *db.Tx) error {
		var err error
		published, err = fixture.m.svc.publishApprovedArticle(c, tx, candidates[0], due)
		return err
	})
	if err != nil || published != nil {
		t.Fatalf("stale worker candidate published: %+v %v", published, err)
	}
	after, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
	if err != nil || after.Live || after.Version != before.Version {
		t.Fatalf("concurrent withdrawal overwritten: %+v %v", after, err)
	}
}

func TestScheduledWorkerDefaultsLegacyNullAuthorToPageOwner(t *testing.T) {
	fixture := scheduledWorkerFixture(t, true, false)
	if err := fixture.d.WriteTx(fixture.editor.Context, func(c context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(c, "UPDATE page_revisions SET content=json_set(content,'$.author_id',NULL) WHERE id=?", fixture.approved)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	if err := fixture.m.svc.CheckScheduledWorker(fixture.editor.Context, fixture.now.Add(90*time.Minute)); err != nil {
		t.Fatal(err)
	}
	article, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
	if err != nil {
		t.Fatal(err)
	}
	if article.AuthorID == nil || article.OwnerID == nil || *article.AuthorID != *article.OwnerID || article.Title != "Approved B" || article.LiveRevisionID == nil || *article.LiveRevisionID != fixture.approved {
		t.Fatalf("legacy approved author did not default to owner: %+v", article)
	}
}

func TestScheduledWorkerRechecksExpiryAfterConcurrentNewPublication(t *testing.T) {
	fixture := scheduledWorkerFixture(t, true, true)
	due := fixture.now.Add(50 * time.Minute)
	candidates, err := expiryCandidates(fixture.editor.Context, fixture.d.ReadPool(), due)
	if err != nil || len(candidates) != 1 {
		t.Fatalf("expiry candidates=%v %v", candidates, err)
	}
	current, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
	if err != nil {
		t.Fatal(err)
	}
	saved, err := fixture.m.svc.SaveDraft(fixture.editor, fixture.page, SaveDraftInput{BaseVersion: current.Version, Changes: map[string]any{"title": "New public D", "go_live_at": nil, "expire_at": fixture.now.Add(4 * time.Hour).Format(time.RFC3339)}})
	if err != nil || len(saved.Fields) != 0 {
		t.Fatalf("save new D: %+v %v", saved, err)
	}
	before, err := fixture.m.svc.Publish(fixture.editor, fixture.page, PublishInput{BaseVersion: saved.Version})
	if err != nil {
		t.Fatal(err)
	}
	if err := fixture.d.WriteTx(fixture.editor.Context, func(c context.Context, tx *db.Tx) error { return expireArticleCandidate(c, tx, candidates[0], due) }); err != nil {
		t.Fatal(err)
	}
	after, err := fixture.m.svc.store.GetArticleByID(fixture.editor.Context, fixture.page)
	if err != nil || !after.Live || after.Expired || after.Title != "New public D" || after.Version != before.Version {
		t.Fatalf("new publication overwritten by old expiry: %+v %v", after, err)
	}
}
