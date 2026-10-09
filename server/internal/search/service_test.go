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

	// 2. 超长查询拦截 (> 50 字符)
	longQuery := strings.Repeat("词", 51)
	_, err = svc.Search(ctx, longQuery)
	if err == nil || !strings.Contains(err.Error(), "超过 50 个字符") {
		t.Fatalf("超长查询应拦截: %v", err)
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
			INSERT INTO articles (page_id, category_id, summary, search_text)
			VALUES (101, 1, '交大杯高校赛圆满落幕', '守望先锋高校赛\n交大杯高校赛圆满落幕\nsjtu ow 线下总决赛圆满成功')
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
