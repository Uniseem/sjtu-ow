package content_test

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/content"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestHomePageAggregation(t *testing.T) {
	d, err := db.Open(filepath.Join(t.TempDir(), "test_home.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("打开测试库失败: %v", err)
	}
	defer d.Close()

	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("执行迁移失败: %v", err)
	}

	ctx := context.Background()

	// 插入设置、用户、战队、内战数据
	_, err = d.WritePool().ExecContext(ctx, `
		UPDATE site_settings SET founded_on = '2020-09-01T00:00:00Z', qq_group_url = 'https://qm.qq.com/test' WHERE id = 1;
		INSERT INTO users (id, email, email_norm, nickname, password_hash, is_sjtu, email_verified_at, agreed_terms_at, agreed_cross_border_at, is_active, created_at, updated_at)
		VALUES (1, 'u1@test.com', 'u1@test.com', '测试玩家', 'argon2id$xxx', 1, datetime('now'), datetime('now'), datetime('now'), 1, datetime('now'), datetime('now'));
		INSERT INTO teams (id, name, created_at, updated_at)
		VALUES (1, '战火战队', datetime('now'), datetime('now'));
		INSERT INTO scrims (id, title, format, status, starts_at, created_at, updated_at)
		VALUES (1, '周五内战', 'rq_5v5', 'published', '2026-10-16 20:00:00', datetime('now'), datetime('now'));
	`)
	if err != nil {
		t.Fatalf("插入测试数据失败: %v", err)
	}

	store := content.NewStore(d)
	now, _ := time.Parse("2006-01-02", "2026-10-09")
	home, err := store.GetHomePage(ctx, now)
	if err != nil {
		t.Fatalf("GetHomePage 失败: %v", err)
	}

	if home.Stats.MemberCount != 1 {
		t.Errorf("期望成员数 1，实际: %d", home.Stats.MemberCount)
	}
	if home.Stats.TeamCount != 1 {
		t.Errorf("期望战队数 1，实际: %d", home.Stats.TeamCount)
	}
	if home.Stats.Age == nil || home.Stats.Age.Years != 6 {
		t.Errorf("期望社区成立年数 6，实际: %+v", home.Stats.Age)
	}
	if home.Stats.QQGroupURL != "https://qm.qq.com/test" {
		t.Errorf("期望 QQ 群链接匹配，实际: %s", home.Stats.QQGroupURL)
	}
	if len(home.Scrims) != 1 || home.Scrims[0].Title != "周五内战" {
		t.Errorf("期望内战 1 场，实际: %+v", home.Scrims)
	}
	if len(home.Teams) != 1 || home.Teams[0].Name != "战火战队" {
		t.Errorf("期望战队 1 支，实际: %+v", home.Teams)
	}
}
