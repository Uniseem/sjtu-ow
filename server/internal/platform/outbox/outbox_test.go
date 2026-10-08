package outbox

import (
	"context"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/jobs"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/mail"
)

func newDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestHoldMergesAndDecideClaimsOnce(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	batch := Open(7)
	letter := mail.Letter{Subject: "赛事已取消：秋季杯", Lead: "这场取消了。", Reason: "因为你报了名。"}
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		n, err := Send(ctx, tx, batch, "https://example.com", letter, []mail.Person{{Address: "a@example.com", Name: "甲"}}, now)
		if err != nil || n != 0 || batch.Held != 1 {
			t.Fatalf("应冻住：n=%d held=%d err=%v", n, batch.Held, err)
		}
		n, err = Send(ctx, tx, batch, "https://example.com", letter, []mail.Person{{Address: "b@example.com", Name: "乙"}, {Address: "gone@example.com.invalid", Name: "注销"}}, now)
		if err != nil || n != 0 || batch.Held != 1 {
			t.Fatalf("同一封应合并，注销的不算：n=%d held=%d err=%v", n, batch.Held, err)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	var id int64
	var recipients string
	if err := d.ReadPool().QueryRow(`SELECT id, recipients FROM held_letters`).Scan(&id, &recipients); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(recipients, "a@example.com") || !strings.Contains(recipients, "b@example.com") || strings.Contains(recipients, "invalid") {
		t.Fatalf("收件人 %s", recipients)
	}
	var letters, people int
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var err error
		letters, people, err = Decide(ctx, tx, 7, batch.Key, []int64{id}, false, "https://example.com", now)
		return err
	})
	if err != nil || letters != 1 || people != 2 {
		t.Fatalf("应发出 1 封给 2 人：%d %d %v", letters, people, err)
	}
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		var err error
		letters, people, err = Decide(ctx, tx, 7, batch.Key, []int64{id}, false, "https://example.com", now)
		return err
	})
	if err != nil || letters != 0 || people != 0 {
		t.Fatalf("第二次点不应再发：%d %d %v", letters, people, err)
	}
	var queued int
	if err := d.ReadPool().QueryRow(`SELECT count(*) FROM jobs WHERE kind = ?`, KindLetter).Scan(&queued); err != nil {
		t.Fatal(err)
	}
	if queued != 2 {
		t.Fatalf("应入队 2 封，得到 %d", queued)
	}
}

func TestNoBatchEnqueuesAndOldOnesDropOff(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 3, 0, 0, 0, time.UTC)
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		n, err := Send(ctx, tx, nil, "https://example.com", mail.Letter{Subject: "验证码", Lead: "看下面。"}, []mail.Person{{Address: "a@example.com"}}, now)
		if err != nil || n != 1 {
			t.Fatalf("没人在场应直接入队：n=%d err=%v", n, err)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	batch := Open(7)
	old := now.Add(-8 * 24 * time.Hour)
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := Send(ctx, tx, batch, "https://example.com", mail.Letter{Subject: "旧的", Lead: "过期了。"}, []mail.Person{{Address: "a@example.com"}}, old); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, `UPDATE held_letters SET created_at = ?`, db.FormatUTC(old))
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	var id int64
	if err := d.ReadPool().QueryRow(`SELECT id FROM held_letters`).Scan(&id); err != nil {
		t.Fatal(err)
	}
	err = d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		n, _, err := Decide(ctx, tx, 7, batch.Key, []int64{id}, false, "https://example.com", now)
		if err != nil || n != 0 {
			t.Fatalf("过了 7 天不应再发：%d %v", n, err)
		}
		n, _, err = Decide(ctx, tx, 7, batch.Key, []int64{id}, true, "https://example.com", now)
		if err != nil || n != 1 {
			t.Fatalf("系统代发应不受 7 天限制：%d %v", n, err)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}

func TestCleanupDropsMonthOldHeldLetters(t *testing.T) {
	d := newDB(t)
	ctx := context.Background()
	now := time.Date(2026, 10, 8, 4, 0, 0, 0, time.UTC)
	old := db.FormatUTC(now.Add(-40 * 24 * time.Hour))
	fresh := db.FormatUTC(now)
	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, `INSERT INTO held_letters
			(batch, actor_id, letter, recipients, state, created_at)
			VALUES ('old', 1, '{}', '[]', 'sent', ?)`, old); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, `INSERT INTO held_letters
			(batch, actor_id, letter, recipients, state, created_at)
			VALUES ('new', 1, '{}', '[]', 'waiting', ?)`, fresh)
		return err
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := jobs.Cleanup(ctx, d, now); err != nil {
		t.Fatal(err)
	}
	var n int
	if err := d.ReadPool().QueryRow(`SELECT count(*) FROM held_letters`).Scan(&n); err != nil {
		t.Fatal(err)
	}
	if n != 1 {
		t.Fatalf("应只留下 30 天内的，得到 %d", n)
	}
}
