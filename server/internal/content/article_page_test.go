package content

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/comments"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func articleProjectionFixture(t *testing.T) (*db.DB, *Service) {
	t.Helper()
	d := newTestDB(t)
	insertTestUser(t, d, 1, "private@example.test", "作者")
	insertTestUser(t, d, 2, "other@example.test", "另一位")
	projectionExec(t, d, `INSERT INTO image_collections (id,name,key,created_at,parent_id) VALUES
 (10,'地图','maps','2026-10-10',1),(11,'坦克','tank','2026-10-10',2),(12,'二级','nested','2026-10-10',11),
 (13,'支援','support','2026-10-10',2),(14,'未分类','other','2026-10-10',2),(15,'坦克','nested-tank','2026-10-10',14),(16,'二级','nested-cover','2026-10-10',10);
 INSERT INTO images (id,collection_id,title,file_name,file_size,width,height,created_at) VALUES
 (10,4,'池外图','10.jpg',1,100,100,'2026-10-10'),(20,1,'根封面','20.jpg',1,100,100,'2026-10-10'),
 (30,10,'子封面','30.jpg',1,100,100,'2026-10-10'),(40,16,'孙封面','40.jpg',1,100,100,'2026-10-10'),
 (50,3,'上传头像','50.jpg',1,100,100,'2026-10-10'),(60,11,'坦克1','60.jpg',1,100,100,'2026-10-10'),
 (70,12,'坦克2','70.jpg',1,100,100,'2026-10-10'),(80,13,'支援','80.jpg',1,100,100,'2026-10-10'),(90,15,'未分类','90.jpg',1,100,100,'2026-10-10');
 UPDATE users SET avatar_image_id=50,motto='宣言',main_role='tank' WHERE id=1;
 INSERT INTO article_categories (id,name,slug,created_at,updated_at) VALUES (1,'资讯','news','2026-10-10','2026-10-10'),(2,'公告','notice','2026-10-10','2026-10-10');
 INSERT INTO pages (id,kind,slug,title,live,search_public,parent_id,first_published_at,last_published_at,seo_title,search_description,created_at,updated_at) VALUES
 (100,'article','current','当前',1,1,900,'2026-10-10T08:00:00Z','2026-10-11T09:00:00.123456Z','文章 SEO','文章描述','2026-10-10T08:00:00Z','2026-10-10T08:00:00Z'),
 (101,'article','older','前篇',1,1,900,'2026-10-09T08:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (102,'article','newer','后篇',1,1,900,'2026-10-11T08:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (103,'article','cross','跨栏目',1,1,901,'2026-10-10T08:00:00.000001Z',NULL,'','','2026-10-10','2026-10-10'),
 (104,'article','draft','草稿',0,1,900,'2026-10-10T09:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (105,'article','restricted','受限',1,0,900,'2026-10-10T10:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (106,'article','same','同时间',1,1,900,'2026-10-10T08:00:00.000000Z',NULL,'','','2026-10-10','2026-10-10'),
 (107,'article','more-12','更多12',1,1,900,'2026-10-12T08:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (108,'article','more-13','更多13',1,1,900,'2026-10-13T08:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (109,'article','more-14','更多14',1,1,900,'2026-10-14T08:00:00Z',NULL,'','','2026-10-10','2026-10-10'),
 (110,'article','undated','无作者无日期',1,1,900,NULL,NULL,'','','2026-10-10','2026-10-10');
 INSERT INTO articles (page_id,category_id,author_id,summary,body_html,char_count,reading_time,related_tournament_id) VALUES
 (100,1,1,'摘要','<h2>正文</h2>',400,1,2),(101,2,1,'','',0,1,NULL),(102,1,1,'','',0,1,NULL),
 (103,1,1,'','',0,1,NULL),(104,1,1,'','',0,1,NULL),(105,1,1,'','',0,1,NULL),(106,1,1,'','',0,1,NULL),
 (107,1,2,'','',0,1,NULL),(108,1,1,'','',0,1,NULL),(109,1,1,'','',0,1,NULL),(110,NULL,NULL,'','',0,1,NULL);
 INSERT INTO tournaments (id,title,status,starts_at,registration_opens_at,registration_closes_at,registration_mode,roster_min,roster_max,sjtu_only,participant_contact,created_at,updated_at) VALUES
 (2,'关联赛事','published','2100-01-01T08:00:00Z','2020-01-01T00:00:00Z','2099-01-01T00:00:00Z','team',5,6,1,'PRIVATE CONTACT','2026-10-10','2026-10-10');
 INSERT INTO comments (id,article_id,user_id,parent_id,content,is_hidden,is_deleted,created_at,updated_at) VALUES
 (1,100,1,NULL,'可见',0,0,'2026-10-10','2026-10-10'),(2,100,1,NULL,'墓碑',0,1,'2026-10-10','2026-10-10'),
 (3,100,1,2,'存活回复',0,0,'2026-10-10','2026-10-10'),(4,100,1,NULL,'隐藏',1,0,'2026-10-10','2026-10-10'),
 (5,100,1,NULL,'已删',0,1,'2026-10-10','2026-10-10'),(6,100,1,5,'隐藏回复',1,0,'2026-10-10','2026-10-10'),
 (7,100,1,NULL,'已删空楼',0,1,'2026-10-10','2026-10-10'),(8,100,1,NULL,'已删空楼',0,1,'2026-10-10','2026-10-10'),
 (9,100,1,8,'已删回复',0,1,'2026-10-10','2026-10-10'),(10,100,1,NULL,'隐藏墓碑',1,0,'2026-10-10','2026-10-10'),
 (11,100,1,10,'存活回复',0,0,'2026-10-10','2026-10-10'),(12,100,1,NULL,'可见',0,0,'2026-10-10','2026-10-10'),
 (13,100,1,12,'已删回复',0,1,'2026-10-10','2026-10-10');`)
	projectionExec(t, d, `INSERT INTO pages (id,kind,slug,title,live,parent_id,first_published_at,created_at,updated_at) VALUES
 (112,'article','latest-other-category','另一分类新文章',1,900,'2030-01-01T00:00:00Z','2026-10-10','2026-10-10'),
 (113,'article','older-far','更早前篇',1,900,'2026-10-08T08:00:00Z','2026-10-10','2026-10-10');
 INSERT INTO articles (page_id,category_id,author_id) VALUES (112,2,2),(113,2,2);`)
	projectionExec(t, d, `INSERT INTO pages (id,kind,slug,title,live,search_public,parent_id,first_published_at,created_at,updated_at) VALUES
 (114,'article','latest-draft','新草稿',0,1,900,'2099-10-10T09:00:00Z','2026-10-10','2026-10-10'),
 (115,'article','latest-restricted','新受限',1,0,900,'2080-10-10T10:00:00Z','2026-10-10','2026-10-10');
 INSERT INTO articles (page_id,category_id,author_id) VALUES (114,1,2),(115,1,2);`)
	projectionExec(t, d, "UPDATE pages SET is_public=search_public")
	return d, NewService(NewStore(d), "https://example.test")
}

func projectionExec(t *testing.T, d *db.DB, query string, args ...any) {
	t.Helper()
	if err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error { _, err := tx.ExecContext(ctx, query, args...); return err }); err != nil {
		t.Fatal(err)
	}
}

func TestArticleProjectionAPI(t *testing.T) {
	d, svc := articleProjectionFixture(t)
	reg := &api.Registry{}
	NewModule(svc).Routes(reg)
	var viewer *app.Viewer
	handler := reg.Handler(func(*http.Request) *app.Viewer { return viewer })
	read := func() NewsDetailOut {
		t.Helper()
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/page/news/current", nil))
		if rec.Code != 200 {
			t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
		}
		var raw map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &raw); err != nil {
			t.Fatal(err)
		}
		for _, key := range []string{"author", "author_article_count", "last_published_at", "comment_total", "older", "newer", "related", "category_slug", "default_cover_image_id", "tournament", "seo_title", "search_description"} {
			if _, ok := raw[key]; !ok {
				t.Fatalf("missing %s: %s", key, rec.Body.String())
			}
		}
		for _, object := range []map[string]any{raw["author"].(map[string]any), raw["tournament"].(map[string]any)} {
			for _, key := range []string{"email", "contacts", "participant_contact", "password_hash"} {
				if _, ok := object[key]; ok {
					t.Fatalf("private field %s", key)
				}
			}
		}
		var out NewsDetailOut
		if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
			t.Fatal(err)
		}
		return out
	}
	out := read()
	if out.ID != 100 || out.SeoTitle != "文章 SEO" || out.SearchDescription != "文章描述" || out.CategorySlug != "news" || out.LastPublishedAt == nil || out.LastPublishedAt.Format(time.RFC3339Nano) != "2026-10-11T09:00:00.123456Z" {
		t.Fatalf("metadata=%+v", out)
	}
	if out.Author == nil || out.Author.UserID != 1 || out.Author.Nickname != "作者" || out.Author.Motto != "宣言" || !out.Author.IsActive || out.Author.AvatarImageID == nil || *out.Author.AvatarImageID != 50 || out.AuthorArticleCount != 7 {
		t.Fatalf("author=%+v count=%d", out.Author, out.AuthorArticleCount)
	}
	if out.Older == nil || out.Older.Slug != "older" || out.Newer == nil || out.Newer.Slug != "newer" {
		t.Fatalf("neighbours=%+v %+v", out.Older, out.Newer)
	}
	if len(out.Related) != 3 || out.Related[0].ID != 109 || out.Related[1].ID != 108 || out.Related[2].ID != 107 {
		t.Fatalf("related=%+v", out.Related)
	}
	if out.DefaultCoverImageID == nil || *out.DefaultCoverImageID != 30 || out.Related[0].DefaultCoverImageID == nil || *out.Related[0].DefaultCoverImageID != 30 {
		t.Fatal("wrong cover pool or selection")
	}
	if out.Tournament == nil || out.Tournament.ID != 2 || out.Tournament.Phase != "open" || out.Tournament.RegistrationModeLabel != "整队报名" || out.Tournament.TakesIndividuals || !out.Tournament.SJTUOnly || out.Tournament.RosterMin != 5 || out.Tournament.RosterMax != 6 || out.Tournament.DefaultCoverImageID == nil || *out.Tournament.DefaultCoverImageID != 20 || out.Tournament.StartsAt == nil || out.Tournament.RegistrationOpensAt == nil || out.Tournament.RegistrationClosesAt == nil {
		t.Fatalf("tournament=%+v", out.Tournament)
	}
	if out.CommentTotal != 4 {
		t.Fatalf("visitor total=%d", out.CommentTotal)
	}
	for _, tc := range []struct {
		viewer *app.Viewer
		want   int
	}{
		{&app.Viewer{ID: 1}, 4}, {&app.Viewer{ID: 1, Caps: map[app.Cap]struct{}{comments.CapCommentsModerate: {}}}, 6},
		{&app.Viewer{ID: 1, Superuser: true}, 6}, {&app.Viewer{ID: 1, Superuser: true, Disabled: true}, 4},
	} {
		viewer = tc.viewer
		out = read()
		if out.CommentTotal != tc.want {
			t.Fatalf("viewer=%+v total=%d", viewer, out.CommentTotal)
		}
		roots, total, err := comments.NewStore(d).ListRootComments(context.Background(), 100, 1, tc.want == 6, "new", 20, 0)
		if err != nil || total != tc.want || len(roots) != tc.want {
			t.Fatalf("thread=%v total=%d err=%v", roots, total, err)
		}
		if tc.want == 6 {
			ids := []int64{8, 12}
			replies, err := comments.NewStore(d).ListRepliesForRoots(context.Background(), ids, 1, true)
			if err != nil || len(replies[8]) != 0 || len(replies[12]) != 0 {
				t.Fatalf("deleted replies=%v err=%v", replies, err)
			}
		}
	}
}

func TestArticleProjectionAuthorAvatars(t *testing.T) {
	for _, tc := range []struct {
		name   string
		sql    string
		want   int64
		active bool
	}{
		{"custom", "", 50, true},
		{"main position", "UPDATE users SET avatar_image_id=NULL WHERE id=1", 70, true},
		{"flex position order", "UPDATE users SET avatar_image_id=NULL,main_role='',flex_roles='support,tank' WHERE id=1", 70, true},
		{"another user keeps top-folder role", "UPDATE articles SET author_id=2 WHERE page_id=100; UPDATE users SET main_role='tank' WHERE id=2", 60, true},
		{"support", "UPDATE users SET avatar_image_id=NULL,main_role='support' WHERE id=1", 80, true},
		{"empty role folder", "UPDATE users SET avatar_image_id=NULL,main_role='damage' WHERE id=1", 70, true},
		{"stopped with custom", "UPDATE users SET is_active=0 WHERE id=1", 0, false},
		{"stopped with default", "UPDATE users SET is_active=0,avatar_image_id=NULL WHERE id=1", 0, false},
		{"empty avatar pool", "UPDATE users SET avatar_image_id=NULL WHERE id=1; DELETE FROM images WHERE id>=60", 0, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			d, svc := articleProjectionFixture(t)
			if tc.sql != "" {
				projectionExec(t, d, tc.sql)
			}
			out, err := svc.ArticlePage(&app.Ctx{Context: context.Background()}, "current")
			if err != nil {
				t.Fatal(err)
			}
			if out.Author == nil || out.Author.IsActive != tc.active {
				t.Fatalf("author=%+v", out.Author)
			}
			got := int64(0)
			if out.Author.AvatarImageID != nil {
				got = *out.Author.AvatarImageID
			}
			if got != tc.want {
				t.Fatalf("avatar=%d want=%d", got, tc.want)
			}
		})
	}
}

func TestArticleProjectionEdges(t *testing.T) {
	d, svc := articleProjectionFixture(t)
	ctx := &app.Ctx{Context: context.Background()}
	out, err := svc.ArticlePage(ctx, "undated")
	if err != nil || out.Author != nil || out.AuthorArticleCount != 0 || out.LastPublishedAt != nil || out.Older != nil || out.Newer != nil || out.Tournament != nil || out.Related == nil || len(out.Related) != 0 || out.CategorySlug != "" {
		t.Fatalf("undated=%+v err=%v", out, err)
	}
	// 无分类也可以有相关文章，不是返回全部分类。
	projectionExec(t, d, "UPDATE articles SET category_id=NULL WHERE page_id=101")
	out, err = svc.ArticlePage(ctx, "undated")
	if err != nil || len(out.Related) != 1 || out.Related[0].ID != 101 {
		t.Fatalf("null related=%+v err=%v", out.Related, err)
	}
	// 相同首发时按最近发布排序，再截前三。
	projectionExec(t, d, `UPDATE pages SET first_published_at='2026-10-14T08:00:00.123456Z',last_published_at='2026-10-15T00:00:00Z' WHERE id IN (108,109);
 UPDATE pages SET first_published_at='2026-10-14T08:00:00.123456Z',last_published_at='2026-10-16T00:00:00Z' WHERE id=107;`)
	out, err = svc.ArticlePage(ctx, "current")
	if err != nil || out.Related[0].ID != 107 {
		t.Fatalf("last published order=%+v err=%v", out.Related, err)
	}
	// 比当前多一个微秒的同栏目文章也应是下一篇。
	projectionExec(t, d, `UPDATE pages SET parent_id=900 WHERE id=103`)
	out, err = svc.ArticlePage(ctx, "current")
	if err != nil || out.Newer == nil || out.Newer.Slug != "cross" {
		t.Fatalf("microsecond neighbour=%+v err=%v", out.Newer, err)
	}
	for _, tc := range []struct {
		sql, phase string
		year       int
		want       bool
		individual bool
	}{
		{"UPDATE tournaments SET status='draft' WHERE id=2", "", 2026, false, false},
		{"UPDATE tournaments SET status='published' WHERE id=2", "upcoming", 2000, true, false},
		{"", "closed", 2110, true, false},
		{"UPDATE tournaments SET status='finished' WHERE id=2", "finished", 2026, true, false},
		{"UPDATE tournaments SET status='cancelled',registration_mode='individual' WHERE id=2", "cancelled", 2026, true, true},
		{"UPDATE articles SET related_tournament_id=99999 WHERE page_id=100", "", 2026, false, false},
	} {
		if tc.sql != "" {
			projectionExec(t, d, tc.sql)
		}
		ctx.Clock = clock.Fixed(time.Date(tc.year, 1, 1, 0, 0, 0, 0, time.UTC))
		out, err = svc.ArticlePage(ctx, "current")
		if err != nil {
			t.Fatal(err)
		}
		if (out.Tournament != nil) != tc.want {
			t.Fatalf("tournament=%+v", out.Tournament)
		}
		if tc.want && (out.Tournament.Phase != tc.phase || out.Tournament.TakesIndividuals != tc.individual || (tc.individual && out.Tournament.RegistrationModeLabel != "个人报名")) {
			t.Fatalf("tournament=%+v want=%+v", out.Tournament, tc)
		}
	}
	// 旧 Go 库的父栏目未知时，不猜测所有 NULL 都属于同一栏目。
	projectionExec(t, d, "UPDATE pages SET parent_id=NULL WHERE id IN (100,101)")
	out, err = svc.ArticlePage(ctx, "current")
	if err != nil || out.Older != nil || out.Newer != nil {
		t.Fatalf("unknown parent old=%+v new=%+v err=%v", out.Older, out.Newer, err)
	}
	projectionExec(t, d, "DELETE FROM images WHERE id IN (20,30,40)")
	out, err = svc.ArticlePage(ctx, "current")
	if err != nil || out.DefaultCoverImageID != nil {
		t.Fatalf("empty cover=%v err=%v", out.DefaultCoverImageID, err)
	}
	for _, item := range out.Related {
		if item.DefaultCoverImageID != nil {
			t.Fatal("related must use empty pool")
		}
	}
	// 数据库读取失败不能变成缺作者或空相关文章的成功页。
	projectionExec(t, d, "DROP TABLE comments")
	if _, err := svc.ArticlePage(ctx, "current"); err == nil {
		t.Fatal("lost projection query error")
	}
}
