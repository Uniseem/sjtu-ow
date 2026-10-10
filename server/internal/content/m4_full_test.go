package content

import (
	"context"
	"database/sql"
	"fmt"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_content.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func insertTestUser(t *testing.T, d *db.DB, id int64, email, nickname string) {
	t.Helper()
	now := time.Now().UTC().Format(time.RFC3339Nano)
	err := d.WriteTx(context.Background(), func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `
			INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at, agreed_cross_border_at, email_verified_at, is_active, created_at, updated_at)
			VALUES (?, ?, ?, 'hash', ?, 1, ?, ?, ?, 1, ?, ?)
			ON CONFLICT (id) DO NOTHING
		`, id, email, email, nickname, now, now, now, now, now)
		return err
	})
	if err != nil {
		t.Fatalf("insertTestUser failed: %v", err)
	}
}

func newTestCtx(ctx context.Context, userID int64, isSuperuser bool, caps ...app.Cap) *app.Ctx {
	cMap := make(map[app.Cap]struct{})
	for _, c := range caps {
		cMap[c] = struct{}{}
	}
	viewer := &app.Viewer{
		ID:            userID,
		Disabled:      false,
		EmailVerified: true,
		Superuser:     isSuperuser,
		Caps:          cMap,
	}
	return &app.Ctx{
		Context: ctx,
		Viewer:  viewer,
		Clock:   clock.System{},
	}
}

// 契约 R058-R060: Slug 生成与保留字避让
func TestSlugGenerationAndReservation(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	store := NewStore(d)

	// 1. 保留字避让 (e.g. "admin", "login", "news")
	reserved := "admin"
	safe, err := store.ResolveUniqueSlug(ctx, KindArticle, reserved, 0)
	if err != nil {
		t.Fatal(err)
	}
	if safe == "admin" || !strings.HasPrefix(safe, "admin-") {
		t.Fatalf("保留字 admin 未被规避: %s", safe)
	}

	// 2. 空白/全标点转换
	empty := Slugify("!@#$%^&*()")
	if empty != "article" {
		t.Fatalf("全标点转换预期 'article', 实际: %s", empty)
	}

	// 3. 中文转换 (Unicode 字符保留，空格连词符规范化)
	cn := Slugify("上海交通大学 守望先锋 社团成立")
	if cn != "上海交通大学-守望先锋-社团成立" {
		t.Fatalf("中文转换不符合预期: %s", cn)
	}

	// 4. 重复 slug 自增序号
	slug1, err := store.ResolveUniqueSlug(ctx, KindArticle, "test-article", 0)
	if err != nil || slug1 != "test-article" {
		t.Fatalf("首次 slug 应原样: %s", slug1)
	}
	// 插入一条占用 test-article
	now := time.Now().UTC().Format(time.RFC3339Nano)
	err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `
			INSERT INTO pages (id, kind, slug, title, live, created_at, updated_at)
			VALUES (1, 'article', 'test-article', 'Test 1', 1, ?, ?)
		`, now, now)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}

	slug2, err := store.ResolveUniqueSlug(ctx, KindArticle, "test-article", 0)
	if err != nil {
		t.Fatal(err)
	}
	if slug2 != "test-article-2" {
		t.Fatalf("冲突 slug 应当加 -2: %s", slug2)
	}
}

// 契约 R043-R047: 自动保存 v2 与版本冲突检测
func TestAutosaveV2AndConflict(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	fixedNow := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := clock.Fixed(fixedNow)
	store := NewStore(d)
	svc := NewService(store, "https://sjtu.ow-shanghaiuniversity.com")

	insertTestUser(t, d, 100, "user100@sjtu.edu.cn", "选手100")

	user1Ctx := newTestCtx(ctx, 100, false)
	user1Ctx.Clock = clk

	// 先建立一个测试分类
	cat := &Category{
		Name:            "测试分类",
		Slug:            "test-cat",
		AllowSubmission: true,
	}
	if err := store.CreateCategory(ctx, cat); err != nil {
		t.Fatal(err)
	}

	// 1. 用户 100 创建草稿
	draft1, err := svc.CreateDraft(user1Ctx, CreateDraftInput{
		Title:      "第一版草稿",
		CategoryID: &cat.ID,
		Summary:    "摘要",
		BodyMD:     "# 标题一\n内容段落",
	})
	if err != nil {
		t.Fatalf("CreateDraft 失败: %v", err)
	}
	if draft1.Version <= 0 {
		t.Fatalf("首个草稿版本应大于 0, 实际: %d", draft1.Version)
	}

	// 2. 30 分钟内再次保存 (更新草稿, 版本单调自增)
	clk10 := clock.Fixed(fixedNow.Add(10 * time.Minute))
	user1Ctx.Clock = clk10

	draft2, err := svc.SaveDraft(user1Ctx, draft1.ID, SaveDraftInput{
		BaseVersion: draft1.Version,
		Changes: map[string]interface{}{
			"title":   "第一版草稿修改",
			"body_md": "# 标题一\n修改后的内容",
		},
	})
	if err != nil {
		t.Fatalf("30分钟内覆盖草稿失败: %v", err)
	}
	if draft2.Version <= draft1.Version {
		t.Fatalf("保存后版本号应自增: draft1=%d, draft2=%d", draft1.Version, draft2.Version)
	}

	// 3. 超过 30 分钟保存 -> 产生新版本草稿
	clk35 := clock.Fixed(fixedNow.Add(35 * time.Minute))
	user1Ctx.Clock = clk35

	draft3, err := svc.SaveDraft(user1Ctx, draft1.ID, SaveDraftInput{
		BaseVersion: draft2.Version,
		Changes: map[string]interface{}{
			"title":   "新版本草稿",
			"body_md": "# 标题一\n35分钟后的新版本",
		},
	})
	if err != nil {
		t.Fatalf("30分钟后新草稿失败: %v", err)
	}
	if draft3.Version <= draft2.Version {
		t.Fatalf("新草稿版本号应递增: draft2.ver=%d, draft3.ver=%d", draft2.Version, draft3.Version)
	}

	// 4. 版本冲突检测 (BaseVersion 落后于 draft3 的版本)
	_, err = svc.SaveDraft(user1Ctx, draft1.ID, SaveDraftInput{
		BaseVersion: draft1.Version, // 已落后
		Changes: map[string]interface{}{
			"title": "冲突内容",
		},
	})
	if err == nil || !strings.Contains(err.Error(), "stale") {
		t.Fatalf("落后版本应返回冲突错误 (409 stale), 实际: %v", err)
	}
}

// 契约 R048-R053, R054-R057: 权限管理与定时发布/到期撤下
func TestPermissionsAndLifecycle(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	clk := clock.Fixed(now)
	store := NewStore(d)
	svc := NewService(store, "https://sjtu.ow-shanghaiuniversity.com")

	insertTestUser(t, d, 100, "author@sjtu.edu.cn", "作者")
	insertTestUser(t, d, 200, "editor@sjtu.edu.cn", "编辑")
	insertTestUser(t, d, 300, "other@sjtu.edu.cn", "路人")

	authorCtx := newTestCtx(ctx, 100, false)
	authorCtx.Clock = clk
	editorCtx := newTestCtx(ctx, 200, false, CapArticlesEditAny, CapArticlesPublishOwn)
	editorCtx.Clock = clk

	// 插入分类
	cat := &Category{Name: "新闻", Slug: "news", AllowSubmission: true}
	if err := store.CreateCategory(ctx, cat); err != nil {
		t.Fatal(err)
	}

	// 1. 普通用户创建文章草稿并保存
	draft, err := svc.CreateDraft(authorCtx, CreateDraftInput{
		Title:      "作者的文章",
		CategoryID: &cat.ID,
		BodyMD:     "## 守望先锋二周年\n高校赛圆满落幕",
	})
	if err != nil {
		t.Fatal(err)
	}

	// 2. 外部路人尝试修改他人草稿
	otherUserCtx := newTestCtx(ctx, 300, false)
	otherUserCtx.Clock = clk
	_, err = svc.SaveDraft(otherUserCtx, draft.ID, SaveDraftInput{
		BaseVersion: draft.Version,
		Changes:     map[string]interface{}{"title": "越权修改"},
	})
	if err == nil {
		t.Fatal("非作者且无 CapArticlesEditAny 应禁止修改草稿")
	}

	// 3. 内容编辑设置定时发布 (未来 2 小时发布，48 小时后到期)
	futurePub := now.Add(2 * time.Hour)
	expireAt := now.Add(48 * time.Hour)
	saveRes, err := svc.SaveDraft(editorCtx, draft.ID, SaveDraftInput{
		BaseVersion: draft.Version,
		Changes: map[string]interface{}{
			"go_live_at": futurePub.Format(time.RFC3339),
			"expire_at":  expireAt.Format(time.RFC3339),
		},
	})
	if err != nil {
		t.Fatalf("设置定时字段失败: %v", err)
	}

	// 4. 执行发布
	article, err := svc.Publish(editorCtx, draft.ID, PublishInput{
		BaseVersion: saveRes.Version,
	})
	if err != nil {
		t.Fatalf("发布失败: %v", err)
	}
	// 定时发布在未来，状态尚未 live
	if article.Live {
		t.Fatalf("定时发布未到期前 live 应为 false: %+v", article)
	}

	// 5. 访客从公开接口读不到未 live 的文章
	anonArticle, err := store.GetArticleBySlug(ctx, article.Slug)
	if err != nil {
		t.Fatal(err)
	}
	if anonArticle.Live {
		t.Fatal("未到定时发布时间，文章不应为 live")
	}

	// 6. 后台 Worker 检查 (模拟 3 小时后，到达发布时间)
	err = svc.CheckScheduledWorker(ctx, now.Add(3*time.Hour))
	if err != nil {
		t.Fatalf("CheckScheduledWorker: %v", err)
	}
	refreshed, err := store.GetArticleByID(ctx, draft.ID)
	if err != nil || refreshed == nil {
		t.Fatal("获取文章失败")
	}
	if !refreshed.Live {
		t.Fatal("Worker 检查后，到达定时上线时间的文章应自动变 live")
	}

	// 7. 模拟 50 小时后，到达到期撤下时间
	err = svc.CheckScheduledWorker(ctx, now.Add(50*time.Hour))
	if err != nil {
		t.Fatalf("CheckScheduledWorker: %v", err)
	}
	expiredArt, err := store.GetArticleByID(ctx, draft.ID)
	if err != nil || expiredArt == nil {
		t.Fatal("获取文章失败")
	}
	if expiredArt.Live {
		t.Fatal("到达 expire_at 后的文章应被 Worker 自动撤下 (live=0)")
	}
}

// 契约 R080-R082: 首页置顶数量约束
func TestPinConstraints(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	now := time.Now()
	clk := clock.Fixed(now)
	store := NewStore(d)
	svc := NewService(store, "https://sjtu.ow-shanghaiuniversity.com")

	insertTestUser(t, d, 1, "admin@sjtu.edu.cn", "站长")
	editorCtx := newTestCtx(ctx, 1, true)
	editorCtx.Clock = clk

	cat := &Category{Name: "快讯", Slug: "flash", AllowSubmission: true}
	if err := store.CreateCategory(ctx, cat); err != nil {
		t.Fatal(err)
	}

	// 创建 4 篇已发布文章
	var aIDs []int64
	for i := 1; i <= 4; i++ {
		dRes, err := svc.CreateDraft(editorCtx, CreateDraftInput{
			Title:      fmt.Sprintf("新闻 %d", i),
			CategoryID: &cat.ID,
			BodyMD:     fmt.Sprintf("正文 %d", i),
		})
		if err != nil {
			t.Fatal(err)
		}
		art, err := svc.Publish(editorCtx, dRes.ID, PublishInput{BaseVersion: dRes.Version})
		if err != nil {
			t.Fatal(err)
		}
		aIDs = append(aIDs, art.ID)
	}

	// 置顶前 3 篇 (上限 3)
	err := store.SetHomePins(ctx, aIDs[:3])
	if err != nil {
		t.Fatalf("置顶前 3 篇失败: %v", err)
	}

	pins, err := store.GetHomePins(ctx)
	if err != nil || len(pins) != 3 {
		t.Fatalf("应成功查询到 3 条首页置顶: %v, len=%d", err, len(pins))
	}

	// 置顶 4 篇应当报错 (超过上限 3)
	err = store.SetHomePins(ctx, aIDs)
	if err == nil {
		t.Fatal("首页置顶超过 3 篇应报错拦截")
	}
}

// 契约: Sitemap 与 Robots.txt 生成
func TestSitemapAndRobots(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	now := time.Now()
	clk := clock.Fixed(now)
	store := NewStore(d)
	svc := NewService(store, "https://sjtu.ow-shanghaiuniversity.com")

	insertTestUser(t, d, 1, "admin@sjtu.edu.cn", "站长")
	editorCtx := newTestCtx(ctx, 1, true)
	editorCtx.Clock = clk

	cat := &Category{Name: "公告", Slug: "notice", AllowSubmission: true}
	if err := store.CreateCategory(ctx, cat); err != nil {
		t.Fatal(err)
	}

	// 发布一篇公开新闻
	dRes, err := svc.CreateDraft(editorCtx, CreateDraftInput{
		Title:      "站点上线公告",
		CategoryID: &cat.ID,
		BodyMD:     "## 站点上线\n欢迎访问",
	})
	if err != nil {
		t.Fatal(err)
	}
	_, err = svc.Publish(editorCtx, dRes.ID, PublishInput{BaseVersion: dRes.Version})
	if err != nil {
		t.Fatal(err)
	}

	// Sitemap 生成
	sitemapXML, err := svc.GenerateSitemap(ctx, time.Now())
	if err != nil {
		t.Fatalf("GenerateSitemap: %v", err)
	}
	if !strings.Contains(sitemapXML, "<urlset") || !strings.Contains(sitemapXML, "news/") {
		t.Fatalf("Sitemap XML 内容不符合预期: %s", sitemapXML)
	}

	// Robots 生成
	robots := svc.GenerateRobots()
	if !strings.Contains(robots, "User-agent: *") || !strings.Contains(robots, "sitemap.xml") {
		t.Fatalf("Robots 内容不符合预期: %s", robots)
	}
}

// 契约: Legacy Wagtail 页面迁移
func TestImportLegacyContent(t *testing.T) {
	newDB := newTestDB(t)
	ctx := context.Background()

	// 临时建一个包含 Wagtail 页面表的旧库
	legacyPath := filepath.Join(t.TempDir(), "legacy_wagtail.sqlite")
	legacyDB, err := sql.Open("sqlite", legacyPath)
	if err != nil {
		t.Fatal(err)
	}
	defer legacyDB.Close()

	schema := `
	CREATE TABLE wagtailcore_page (
		id INTEGER PRIMARY KEY,
		slug TEXT NOT NULL,
		title TEXT NOT NULL,
		live INTEGER NOT NULL DEFAULT 1,
		has_unpublished_changes INTEGER NOT NULL DEFAULT 0,
		go_live_at TEXT,
		expire_at TEXT,
		first_published_at TEXT,
		last_published_at TEXT,
		live_revision_id INTEGER,
		owner_id INTEGER,
		seo_title TEXT DEFAULT '',
		search_description TEXT DEFAULT ''
	);
	CREATE TABLE content_articlecategory (
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		slug TEXT NOT NULL,
		sort_order INTEGER NOT NULL DEFAULT 0,
		allow_submission INTEGER NOT NULL DEFAULT 1
	);
	CREATE TABLE content_articlepage (
		page_ptr_id INTEGER PRIMARY KEY,
		category_id INTEGER,
		cover_id INTEGER,
		summary TEXT DEFAULT '',
		body TEXT NOT NULL,
		body_plain TEXT DEFAULT '',
		body_words INTEGER DEFAULT 0,
		body_minutes INTEGER DEFAULT 1,
		author_id INTEGER,
		comments_enabled INTEGER DEFAULT 1,
		tournament_id INTEGER
	);
	CREATE TABLE wagtailcore_collection (
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL
	);
	CREATE TABLE wagtailimages_image (
		id INTEGER PRIMARY KEY,
		collection_id INTEGER,
		title TEXT NOT NULL,
		file TEXT NOT NULL,
		width INTEGER NOT NULL,
		height INTEGER NOT NULL,
		created_at TEXT NOT NULL,
		uploaded_by_user_id INTEGER,
		file_size INTEGER
	);
	`
	if _, err := legacyDB.ExecContext(ctx, schema); err != nil {
		t.Fatal(err)
	}

	// 灌入模拟分类与 Wagtail 页面
	nowStr := "2026-09-18 12:00:00"
	streamMarkdown := "旧站的一段正文\n\n## 二级标题"
	_, err = legacyDB.ExecContext(ctx, `
		INSERT INTO content_articlecategory (id, name, slug, sort_order, allow_submission)
		VALUES (1, '赛事速递', 'match-news', 0, 1);
	`)
	if err != nil {
		t.Fatal(err)
	}
	_, err = legacyDB.ExecContext(ctx, `
		INSERT INTO wagtailcore_page (id, slug, title, live, has_unpublished_changes, first_published_at, last_published_at)
		VALUES (55, 'old-wagtail-post', '旧站迁移文章', 1, 0, ?, ?);
	`, nowStr, nowStr)
	if err != nil {
		t.Fatal(err)
	}
	_, err = legacyDB.ExecContext(ctx, `
		INSERT INTO content_articlepage (page_ptr_id, category_id, summary, body, body_plain, body_words, body_minutes, comments_enabled)
		VALUES (55, 1, '摘要内容', ?, '旧站的一段正文 二级标题', 15, 1, 1);
	`, streamMarkdown)
	if err != nil {
		t.Fatal(err)
	}

	// 执行导入
	err = ImportLegacyContent(ctx, newDB, legacyDB, "https://sjtu.ow-shanghaiuniversity.com")
	if err != nil {
		t.Fatalf("ImportLegacyContent 失败: %v", err)
	}

	// 验证文章已进入 newDB 且保留原始 ID 55
	store := NewStore(newDB)
	art, err := store.GetArticleByID(ctx, 55)
	if err != nil || art == nil {
		t.Fatalf("导入的文章应当存在且 ID=55: %+v, err=%v", art, err)
	}
	if art.Title != "旧站迁移文章" || art.Summary != "摘要内容" {
		t.Fatalf("导入字段校验失败: %+v", art)
	}
	if !strings.Contains(art.BodyMD, "旧站的一段正文") {
		t.Fatalf("正文校验失败: %s", art.BodyMD)
	}
}
