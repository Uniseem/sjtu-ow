package content

import (
	"context"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
)

func TestImportedHomepageKeepsLivePinsSeparateFromLatestDraft(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	projectionExec(t, d, `INSERT INTO pages(id,kind,slug,title,live,created_at,updated_at) VALUES
 (10,'article','live-pin','线上置顶',1,'2026-10-10','2026-10-10'),
 (11,'article','draft-pin','草稿置顶',1,'2026-10-10','2026-10-10');
 INSERT INTO articles(page_id) VALUES(10),(11);
 INSERT INTO home_pins(article_page_id,sort_order) VALUES(10,0);`)
	if _, err := legacy.Exec(`CREATE TABLE content_homepage(page_ptr_id INTEGER PRIMARY KEY);
 INSERT INTO content_homepage VALUES(2);
 INSERT INTO content_homepagepinnedarticle VALUES(10,0);
 INSERT INTO wagtailcore_page(id,slug,title,live,has_unpublished_changes,last_published_at) VALUES(2,'home','首页',1,1,'2026-10-09 01:02:03.123456');
 INSERT INTO django_content_type VALUES(4,'content','homepage');
 INSERT INTO wagtailcore_revision VALUES
 (201,'2',NULL,'{"pinned_articles":[{"article":10,"sort_order":0}]}','2026-10-09 01:02:03.123456',NULL,4),
 (202,'2',NULL,'{"pinned_articles":[{"article":11,"sort_order":0}]}','2026-10-10 04:05:06',NULL,4);`); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := importHomeState(ctx, d, legacy); err != nil {
			t.Fatal(err)
		}
	}
	m := NewModule(NewService(NewStore(d), "https://example.test"))
	viewer := newTestCtx(ctx, 1, true)
	viewer.Clock = clock.Fixed(time.Date(2026, 10, 13, 4, 5, 6, 0, time.UTC))
	out, err := m.readHomeDraft(viewer, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	if out.ID != 2 || !out.Live || !out.HasUnpublishedChanges || len(out.Draft.ArticleIDs) != 1 || out.Draft.ArticleIDs[0] != 11 || out.LastPublishedAt == nil || out.LastPublishedAt.Format(time.RFC3339Nano) != "2026-10-09T01:02:03.123456Z" {
		t.Fatalf("source state lost: %+v", out)
	}
	pins, err := m.svc.store.GetHomePins(ctx)
	if err != nil || len(pins) != 1 || pins[0].ArticlePageID != 10 {
		t.Fatalf("live pins overwritten: %+v, %v", pins, err)
	}
	var count int
	if err := d.ReadPool().QueryRowContext(ctx, "SELECT COUNT(*) FROM content_home_revisions").Scan(&count); err != nil || count != 2 {
		t.Fatalf("history count=%d error=%v", count, err)
	}
	insertTestUser(t, d, 1, "editor@example.test", "编辑")
	published, err := m.publishHomeDraft(viewer, SiteDraftPublishIn{BaseVersion: out.Version})
	if err != nil {
		t.Fatal(err)
	}
	if published.Version != out.Version+1 {
		t.Fatalf("publish version=%d", published.Version)
	}
	refreshed, err := m.readHomeDraft(viewer, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	pins, err = m.svc.store.GetHomePins(ctx)
	if err != nil || len(pins) != 1 || pins[0].ArticlePageID != 11 {
		t.Fatalf("published pins=%+v error=%v", pins, err)
	}
	if refreshed.HasUnpublishedChanges || refreshed.LastPublishedAt == nil || !refreshed.LastPublishedAt.Equal(viewer.Now().UTC()) {
		t.Fatalf("publish state=%+v", refreshed)
	}
	if err := ImportLegacyContent(ctx, d, legacy, "https://example.test"); err != nil {
		t.Fatal(err)
	}
	refreshed, err = m.readHomeDraft(viewer, struct{}{})
	if err != nil {
		t.Fatal(err)
	}
	pins, err = m.svc.store.GetHomePins(ctx)
	if err != nil || len(pins) != 1 || pins[0].ArticlePageID != 11 {
		t.Fatalf("repeat import resurrected old pins=%+v error=%v", pins, err)
	}
	if refreshed.Version != published.Version || refreshed.HasUnpublishedChanges {
		t.Fatalf("repeat import replaced published state: %+v", refreshed)
	}
}

func TestImportedPlainPageExpiryAndApprovedSchedule(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	projectionExec(t, d, `INSERT INTO pages(id,kind,slug,title,live,created_at,updated_at) VALUES(30,'site_page','expired','已撤下',0,'2026-10-10','2026-10-10');
 INSERT INTO site_pages(page_id,body_md,body_html,body_plain) VALUES(30,'正文','<p>正文</p>','正文');
 INSERT INTO page_revisions(id,page_id,content,created_at,approved_go_live_at) VALUES(300,30,'{}','2026-10-10','2026-10-20T00:00:00Z');`)
	if _, err := legacy.Exec(`ALTER TABLE wagtailcore_page ADD COLUMN expired INTEGER NOT NULL DEFAULT 0;
 INSERT INTO wagtailcore_page(id,slug,title,live,expired,go_live_at,expire_at) VALUES(30,'expired','已撤下',0,1,'2026-10-20 00:00:00','2026-10-01 00:00:00');
 INSERT INTO content_standardpage VALUES(30,'正文');`); err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := importPlainPageState(ctx, d, legacy); err != nil {
			t.Fatal(err)
		}
	}
	detail, err := readPlainPageRow(ctx, d.ReadPool(), 30)
	if err != nil {
		t.Fatal(err)
	}
	if !detail.Page.Expired || !detail.Page.ApprovedSchedule || detail.Page.Live {
		t.Fatalf("expiry or approved schedule lost: %+v", detail.Page)
	}
	m := NewModule(NewService(NewStore(d), "https://example.test"))
	insertTestUser(t, d, 1, "editor@example.test", "编辑")
	_, err = m.publishPlainPage(newTestCtx(ctx, 1, true), PlainPagePublishIn{ID: api.ID(30), BaseVersion: detail.Version})
	if err != nil {
		t.Fatal(err)
	}
	detail, err = readPlainPageRow(ctx, d.ReadPool(), 30)
	if err != nil {
		t.Fatal(err)
	}
	if detail.Page.Expired || detail.Page.ApprovedSchedule || !detail.Page.Live {
		t.Fatalf("published page still expired/scheduled: %+v", detail.Page)
	}
}
