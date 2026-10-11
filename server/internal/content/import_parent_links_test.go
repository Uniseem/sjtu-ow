package content

import (
	"context"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
)

func TestImportContentParentLinks(t *testing.T) {
	ctx := context.Background()
	d := newTestDB(t)
	legacy := newLegacyContentDB(t)
	_, err := legacy.Exec(`ALTER TABLE wagtailcore_collection ADD COLUMN path TEXT;
 INSERT INTO wagtailcore_collection (id,name,path) VALUES
 (100,'根','0001'),(200,'默认封面','00010001'),(150,'地图','000100010001'),(140,'二级','0001000100010001'),(250,'默认封面','000100010002'),
 (300,'默认头像','00010002'),(290,'坦克','000100020001'),(280,'二级','0001000200010001');
 INSERT INTO wagtailimages_image (id,collection_id,title,file,width,height,created_at,uploaded_by_user_id,file_size) VALUES
 (10,200,'封面1','1.jpg',100,100,'2026-10-10',NULL,1),(30,150,'封面2','2.jpg',100,100,'2026-10-10',NULL,1),(20,140,'封面3','3.jpg',100,100,'2026-10-10',NULL,1),
 (40,250,'重名子目录','4.jpg',100,100,'2026-10-10',NULL,1),(50,280,'头像','5.jpg',100,100,'2026-10-10',NULL,1);
 INSERT INTO wagtailcore_page (id,path,slug,title,first_published_at) VALUES
 (1,'0001','root','根',NULL),(2,'00010001','news','栏目',NULL),
 (3,'000100010001','one','文章1','2026-10-10 00:00:00'),(4,'000100010002','two','文章2','2026-10-11 00:00:00'),
 (5,'00010002','other','另一栏目',NULL),(6,'000100020001','three','文章3','2026-10-10 12:00:00');
 INSERT INTO content_articlepage (page_ptr_id,body) VALUES (3,'正文'),(4,'正文'),(6,'正文');`)
	if err != nil {
		t.Fatal(err)
	}
	for range 2 {
		if err := ImportLegacyContent(ctx, d, legacy, "https://example.test"); err != nil {
			t.Fatal(err)
		}
		for _, tc := range []struct {
			table      string
			id, parent int64
		}{{"image_collections", 150, 200}, {"image_collections", 140, 150}, {"image_collections", 250, 200}, {"image_collections", 280, 290}, {"pages", 3, 2}, {"pages", 4, 2}, {"pages", 6, 5}} {
			var parent int64
			if err := d.ReadPool().QueryRowContext(ctx, "SELECT parent_id FROM "+tc.table+" WHERE id=?", tc.id).Scan(&parent); err != nil || parent != tc.parent {
				t.Fatalf("%s id=%d parent=%d err=%v", tc.table, tc.id, parent, err)
			}
		}
		cover, err := media.LoadPool(ctx, d.ReadPool(), "default_cover")
		if err != nil || len(cover) != 4 || cover[0].ID != 10 || cover[1].ID != 20 || cover[2].ID != 30 || cover[3].ID != 40 {
			t.Fatalf("cover=%+v err=%v", cover, err)
		}
		face, err := media.LoadPool(ctx, d.ReadPool(), "default_avatar")
		if err != nil || len(face) != 1 || face[0].ID != 50 || face[0].Role != "tank" {
			t.Fatalf("avatar=%+v err=%v", face, err)
		}
		out, err := NewService(NewStore(d), "https://example.test").ArticlePage(&app.Ctx{Context: ctx}, "one")
		if err != nil || out.Newer == nil || out.Newer.Slug != "two" {
			t.Fatalf("next=%+v err=%v", out.Newer, err)
		}
	}
}

func TestNewArticleUsesNewsParent(t *testing.T) {
	d := newTestDB(t)
	insertTestUser(t, d, 1, "member@example.test", "成员")
	projectionExec(t, d, `INSERT INTO pages (id,kind,slug,title,created_at,updated_at) VALUES (20,'news_index','news','资讯','2026-10-10','2026-10-10')`)
	id := int64(1)
	article, _, err := NewStore(d).CreateArticleDraft(context.Background(), &Page{Slug: "new", Title: "新文章", OwnerID: &id}, &Article{AuthorID: &id}, "{}", id)
	if err != nil {
		t.Fatal(err)
	}
	var parent int64
	if err := d.ReadPool().QueryRowContext(context.Background(), `SELECT parent_id FROM pages WHERE id=?`, article.ID).Scan(&parent); err != nil || parent != 20 {
		t.Fatalf("parent=%d err=%v", parent, err)
	}
}
