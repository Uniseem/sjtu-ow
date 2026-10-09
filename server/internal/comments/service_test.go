package comments

import (
	"context"
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
	d, err := db.Open(filepath.Join(t.TempDir(), "test_comments.sqlite"), db.WithWatchdog(10*time.Second, 0))
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

func setupTestArticle(t *testing.T, d *db.DB, pageID int64, live bool, commentsEnabled bool) {
	t.Helper()
	now := time.Now().UTC().Format(time.RFC3339Nano)
	liveInt := 0
	if live {
		liveInt = 1
	}
	commInt := 0
	if commentsEnabled {
		commInt = 1
	}

	err := d.WriteTx(context.Background(), func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `
			INSERT INTO pages (id, kind, slug, title, live, created_at, updated_at)
			VALUES (?, 'article', ?, '测试文章', ?, ?, ?)
			ON CONFLICT (id) DO UPDATE SET live = excluded.live
		`, pageID, "test-article", liveInt, now, now)
		if err != nil {
			return err
		}
		_, err = tx.ExecContext(txCtx, `
			INSERT INTO articles (page_id, comments_enabled, body_md, body_html)
			VALUES (?, ?, '正文', '<p>正文</p>')
			ON CONFLICT (page_id) DO UPDATE SET comments_enabled = excluded.comments_enabled
		`, pageID, commInt)
		return err
	})
	if err != nil {
		t.Fatalf("setupTestArticle: %v", err)
	}
}

// 契约 R171-R176: 评论门槛、字数限制、一层扁平化回复
func TestCommentsCreationAndReplyFlattening(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	store := NewStore(d)
	svc := NewService(store)

	insertTestUser(t, d, 1, "u1@sjtu.edu.cn", "选手1")
	insertTestUser(t, d, 2, "u2@sjtu.edu.cn", "选手2")
	insertTestUser(t, d, 3, "u3@sjtu.edu.cn", "选手3")

	u1Ctx := newTestCtx(ctx, 1, false)
	u2Ctx := newTestCtx(ctx, 2, false)
	u3Ctx := newTestCtx(ctx, 3, false)

	// 1. 未发布文章发表评论 -> 拦截 (规则 171)
	setupTestArticle(t, d, 10, false, true)
	_, err := svc.CreateComment(u1Ctx, CreateCommentInput{
		ArticleID: 10,
		Content:   "未发布文章评论",
	})
	if err == nil || !strings.Contains(err.Error(), "未发布") {
		t.Fatalf("未发布文章评论应被拦截, 实际: %v", err)
	}

	// 2. 关闭评论的文章发表评论 -> 拦截 (规则 172)
	setupTestArticle(t, d, 10, true, false)
	_, err = svc.CreateComment(u1Ctx, CreateCommentInput{
		ArticleID: 10,
		Content:   "关闭评论的文章评论",
	})
	if err == nil || !strings.Contains(err.Error(), "已关闭评论") {
		t.Fatalf("关闭评论的文章评论应被拦截, 实际: %v", err)
	}

	// 3. 发布且开启评论的文章
	setupTestArticle(t, d, 10, true, true)

	// 4. 空评论与超 500 字拦截 (规则 175)
	_, err = svc.CreateComment(u1Ctx, CreateCommentInput{
		ArticleID: 10,
		Content:   "   ",
	})
	if err == nil || !strings.Contains(err.Error(), "不能为空") {
		t.Fatalf("空评论应拦截, 实际: %v", err)
	}

	longContent := strings.Repeat("字", 501)
	_, err = svc.CreateComment(u1Ctx, CreateCommentInput{
		ArticleID: 10,
		Content:   longContent,
	})
	if err == nil || !strings.Contains(err.Error(), "最多 500 字") {
		t.Fatalf("超 500 字评论应拦截, 实际: %v", err)
	}

	// 5. 顶层评论发布
	root, err := svc.CreateComment(u1Ctx, CreateCommentInput{
		ArticleID: 10,
		Content:   "顶层评论内容",
	})
	if err != nil {
		t.Fatalf("发表顶层评论失败: %v", err)
	}
	if root.ParentID != nil {
		t.Fatalf("顶层评论 ParentID 应为 nil: %+v", root)
	}

	// 6. 二级回复 (用户 2 回复顶层评论)
	rep1, err := svc.CreateComment(u2Ctx, CreateCommentInput{
		ArticleID: 10,
		ParentID:  &root.ID,
		Content:   "回复顶层评论",
	})
	if err != nil {
		t.Fatalf("发表回复失败: %v", err)
	}
	if rep1.ParentID == nil || *rep1.ParentID != root.ID {
		t.Fatalf("回复 ParentID 应为 root.ID: %+v", rep1)
	}
	if rep1.ReplyToUserID == nil || *rep1.ReplyToUserID != 1 {
		t.Fatalf("回复的 ReplyToUserID 应为用户 1: %+v", rep1)
	}

	// 7. 三级回复扁平化至一层 (规则 174: 用户 3 回复用户 2 的二级回复)
	rep2, err := svc.CreateComment(u3Ctx, CreateCommentInput{
		ArticleID: 10,
		ParentID:  &rep1.ID, // 回复的是二级回复
		Content:   "回复楼中楼",
	})
	if err != nil {
		t.Fatalf("发表三级回复失败: %v", err)
	}
	// 应当扁平化：ParentID 指向顶层 root.ID，ReplyToUserID 指向用户 2
	if rep2.ParentID == nil || *rep2.ParentID != root.ID {
		t.Fatalf("三级回复应当扁平化 ParentID 至 root.ID (%d), 实际: %v", root.ID, rep2.ParentID)
	}
	if rep2.ReplyToUserID == nil || *rep2.ReplyToUserID != 2 {
		t.Fatalf("三级回复的 ReplyToUserID 应为被回复的用户 2, 实际: %v", rep2.ReplyToUserID)
	}
}

// 契约 R177-R183: 修改、软删除与墓碑、点赞、排序
func TestCommentsLifecycleAndTombstone(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	store := NewStore(d)
	svc := NewService(store)

	insertTestUser(t, d, 1, "u1@sjtu.edu.cn", "选手1")
	insertTestUser(t, d, 2, "u2@sjtu.edu.cn", "选手2")
	insertTestUser(t, d, 999, "mod@sjtu.edu.cn", "管理员")

	u1Ctx := newTestCtx(ctx, 1, false)
	u2Ctx := newTestCtx(ctx, 2, false)
	modCtx := newTestCtx(ctx, 999, true, CapCommentsModerate)

	setupTestArticle(t, d, 20, true, true)

	// 1. 用户 1 发表顶层评论
	c1, err := svc.CreateComment(u1Ctx, CreateCommentInput{
		ArticleID: 20,
		Content:   "第一版内容",
	})
	if err != nil {
		t.Fatal(err)
	}

	// 2. 他人尝试修改 -> 禁止
	_, err = svc.EditComment(u2Ctx, c1.ID, EditCommentInput{Content: "别人篡改"})
	if err == nil {
		t.Fatal("非作者修改评论应被拒绝")
	}

	// 3. 作者修改评论 (规则 175)
	c1Updated, err := svc.EditComment(u1Ctx, c1.ID, EditCommentInput{Content: "修改后的内容"})
	if err != nil {
		t.Fatalf("作者修改评论失败: %v", err)
	}
	if c1Updated.Content != "修改后的内容" {
		t.Fatalf("修改后内容不符: %s", c1Updated.Content)
	}

	// 4. 点赞切换 (规则 181)
	liked, count, err := svc.ToggleLike(u2Ctx, c1.ID)
	if err != nil || !liked || count != 1 {
		t.Fatalf("用户 2 点赞失败: liked=%v, count=%d, err=%v", liked, count, err)
	}
	// 再次点击取消点赞
	liked, count, err = svc.ToggleLike(u2Ctx, c1.ID)
	if err != nil || liked || count != 0 {
		t.Fatalf("用户 2 取消点赞失败: liked=%v, count=%d, err=%v", liked, count, err)
	}
	// 重新赞上
	_, _, _ = svc.ToggleLike(u2Ctx, c1.ID)

	// 5. 用户 2 增加回复
	_, err = svc.CreateComment(u2Ctx, CreateCommentInput{
		ArticleID: 20,
		ParentID:  &c1.ID,
		Content:   "子回复内容",
	})
	if err != nil {
		t.Fatal(err)
	}

	// 6. 用户 1 软删除自己的父评论 (规则 178, 182)
	err = svc.DeleteComment(u1Ctx, c1.ID)
	if err != nil {
		t.Fatalf("DeleteComment 失败: %v", err)
	}

	// 7. 查询列表：有回复的已删除评论渲染为墓碑 "[该评论已删除]" (规则 182)
	listRes, err := svc.ListComments(u2Ctx, 20, ListCommentsInput{SortBy: "new"})
	if err != nil {
		t.Fatalf("ListComments 失败: %v", err)
	}
	if len(listRes.Comments) != 1 {
		t.Fatalf("有回复的父评论删除后应留墓碑行: len=%d", len(listRes.Comments))
	}
	rootItem := listRes.Comments[0]
	if !rootItem.IsDeleted || rootItem.Content != "[该评论已删除]" {
		t.Fatalf("墓碑内容应为 '[该评论已删除]', 实际: %s, deleted=%v", rootItem.Content, rootItem.IsDeleted)
	}
	if len(rootItem.Replies) != 1 {
		t.Fatalf("子回复应依然保留展示: len=%d", len(rootItem.Replies))
	}

	// 8. 管理员置顶已删除评论应被拦截 (规则 180)
	err = svc.SetPinned(modCtx, 20, c1.ID, true)
	if err == nil {
		t.Fatal("置顶已删除评论应被拦截")
	}

	// 发表新顶层评论并置顶
	c2, err := svc.CreateComment(u2Ctx, CreateCommentInput{
		ArticleID: 20,
		Content:   "第二条活跃评论",
	})
	if err != nil {
		t.Fatal(err)
	}
	err = svc.SetPinned(modCtx, 20, c2.ID, true)
	if err != nil {
		t.Fatalf("管理员置顶活跃评论失败: %v", err)
	}

	// 9. 管理员隐藏与权限视角 (规则 179)
	err = svc.SetHidden(modCtx, rootItem.Replies[0].ID, true)
	if err != nil {
		t.Fatalf("管理员隐藏失败: %v", err)
	}

	// 普通用户查询：c1 已删除且子评论被隐藏，故普通视角下 c1 彻底不展示 (len=1，仅剩置顶活跃的 c2)
	anonList, err := svc.ListComments(u2Ctx, 20, ListCommentsInput{SortBy: "new"})
	if err != nil {
		t.Fatal(err)
	}
	if len(anonList.Comments) != 1 || anonList.Comments[0].ID != c2.ID {
		t.Fatalf("普通用户视角下仅应展示 c2: len=%d", len(anonList.Comments))
	}

	// mod 视角下：c1 (含被隐藏回复) 依然可见 (len=2，第 0 项是置顶 c2，第 1 项是 c1)
	modList, err := svc.ListComments(modCtx, 20, ListCommentsInput{SortBy: "new"})
	if err != nil {
		t.Fatal(err)
	}
	if len(modList.Comments) != 2 {
		t.Fatalf("mod 视角下应可见 2 条评论: len=%d", len(modList.Comments))
	}
	c1InMod := modList.Comments[1]
	if len(c1InMod.Replies) != 1 || !c1InMod.Replies[0].IsHidden {
		t.Fatalf("mod 视角下 c1 的被隐藏回复应可见且 IsHidden=true")
	}
}
