package search

import (
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func newTestDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test_search.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

// 契约 R233: 全站搜索大小写折叠、子串匹配与安全边界
func TestSearchService(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d)

	// 1. 空查询
	emptyRes, err := svc.Search(ctx, "   ")
	if err != nil || len(emptyRes.Articles) != 0 {
		t.Fatalf("空查询应当返回空结果: %+v", emptyRes)
	}

	// 2. 超长查询照旧截断到 50 字符
	longQuery := strings.Repeat("词", 51)
	longRes, err := svc.Search(ctx, longQuery)
	if err != nil || longRes.Query != strings.Repeat("词", 50) {
		t.Fatalf("超长查询未截断: %+v, %v", longRes, err)
	}

	// 插入测试分类与文章
	now := time.Now().UTC().Format(time.RFC3339Nano)
	err = d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(txCtx, `
			INSERT INTO article_categories (id, name, slug, created_at, updated_at)
			VALUES (1, '社团公告', 'notices', ?, ?)
		`, now, now)
		if err != nil {
			return err
		}

		// 文章 1: live=1, search_text 包含 "守望先锋 sjtu ow 大赛"
		_, err = tx.ExecContext(txCtx, `
			INSERT INTO pages (id, kind, slug, title, live, first_published_at, created_at, updated_at)
			VALUES (101, 'article', 'ow-cup', '守望先锋高校赛', 1, ?, ?, ?)
		`, now, now, now)
		if err != nil {
			return err
		}
		_, err = tx.ExecContext(txCtx, `
			INSERT INTO articles (page_id, category_id, summary, search_text, body_plain)
			VALUES (101, 1, '交大杯高校赛圆满落幕', '守望先锋高校赛\n交大杯高校赛圆满落幕\nsjtu ow 线下总决赛圆满成功', 'sjtu ow 线下总决赛圆满成功')
		`)
		if err != nil {
			return err
		}

		// 文章 2: live=0 (未发布), 不应搜出
		_, err = tx.ExecContext(txCtx, `
			INSERT INTO pages (id, kind, slug, title, live, created_at, updated_at)
			VALUES (102, 'article', 'draft-article', '守望先锋未发布草稿', 0, ?, ?)
		`, now, now)
		if err != nil {
			return err
		}
		_, err = tx.ExecContext(txCtx, `
			INSERT INTO articles (page_id, category_id, summary, search_text)
			VALUES (102, 1, '草稿摘要', '守望先锋未发布草稿\n线下总决赛')
		`)
		return err
	})
	if err != nil {
		t.Fatalf("插入测试数据失败: %v", err)
	}

	// 3. 大小写折叠子串搜索 (SJTU 大写应搜出 sjtu)
	res, err := svc.Search(ctx, "SJTU 守望")
	if err != nil {
		t.Fatalf("Search 失败: %v", err)
	}
	if len(res.Articles) != 1 || res.Articles[0].ID != 101 {
		t.Fatalf("大写 SJTU 应搜出文章 101: %+v", res.Articles)
	}
	if res.Articles[0].CategoryName != "社团公告" {
		t.Fatalf("分类名校验失败: %s", res.Articles[0].CategoryName)
	}

	// 4. 搜索未命中的关键词
	resMiss, err := svc.Search(ctx, "英雄联盟")
	if err != nil {
		t.Fatalf("Search 失败: %v", err)
	}
	if len(resMiss.Articles) != 0 {
		t.Fatalf("未命中的关键词应返回空结果: %+v", resMiss.Articles)
	}
}

// 契约 R233、R236：搜索覆盖战队（未解散的，名字或简介）和成员（只有已加入的，只搜昵称）
func TestSearchTeamsAndMembers(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d)
	now := "2026-10-09T00:00:00.000000Z"
	exec := func(q string, args ...any) {
		t.Helper()
		if err := d.WriteTx(ctx, func(txCtx context.Context, tx *db.Tx) error {
			_, err := tx.ExecContext(txCtx, q, args...)
			return err
		}); err != nil {
			t.Fatalf("%s: %v", q, err)
		}
	}
	user := func(id int64, nick string, active int, verified any) {
		exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at,
			agreed_cross_border_at, email_verified_at, is_active, motto, created_at, updated_at)
			VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, ?, '座右铭', ?, ?)`,
			id, nick+"@x.com", nick+"@x.com", nick, now, now, verified, active, now, now)
	}
	user(1, "Dva小姐", 1, now)
	user(2, "停用的Dva", 0, now)
	user(3, "没验证的Dva", 1, nil)
	exec(`INSERT INTO teams (id, name, description, is_recruiting, created_at, updated_at)
		VALUES (1, 'Dva 战队', '', 1, ?, ?), (2, '另一队', '我们喜欢 DVA', 0, ?, ?), (3, '散伙的 Dva 队', '', 1, ?, ?)`,
		now, now, now, now, now, now)
	exec(`UPDATE teams SET disbanded_at = ? WHERE id = 3`, now)

	res, err := svc.Search(ctx, "dva")
	if err != nil {
		t.Fatal(err)
	}
	if len(res.Teams) != 2 {
		t.Fatalf("战队：名字或简介命中，解散的不算：%+v", res.Teams)
	}
	if len(res.Members) != 1 || res.Members[0].ID != 1 || res.Members[0].Motto != "座右铭" {
		t.Fatalf("成员：只有已加入的，大小写不分：%+v", res.Members)
	}
	// 搜简介里的词不会命中成员（只搜昵称）
	res, _ = svc.Search(ctx, "座右铭")
	if len(res.Members) != 0 {
		t.Fatalf("成员只搜昵称：%+v", res.Members)
	}
}
