package ops

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// 契约 R015 割接对账与一致性检查测试。
func TestReconcileDetailed(t *testing.T) {
	ctx := context.Background()
	d, _ := setupTestDB(t)

	// 创建一个测试超管
	err := CreateSuperuser(ctx, d, SuperuserOptions{
		Email:    "reconcile_admin@sjtu.edu.cn",
		Nickname: "对账测试员",
		Password: "Password-For-Reconcile-2026!",
		IsSJTU:   true,
	})
	if err != nil {
		t.Fatalf("CreateSuperuser 失败: %v", err)
	}

	res, err := Reconcile(ctx, d, "")
	if err != nil {
		t.Fatalf("Reconcile 失败: %v", err)
	}

	if !res.IntegrityOK {
		t.Errorf("PRAGMA integrity_check 预期为 true")
	}
	if !res.FKCheckOK {
		t.Errorf("PRAGMA foreign_key_check 预期为 true")
	}
	if !res.OverallOK {
		t.Errorf("OverallOK 预期为 true")
	}

	if res.UserStats["total_users"] < 1 {
		t.Errorf("用户统计异常: %+v", res.UserStats)
	}
	if res.UserStats["superusers"] < 1 {
		t.Errorf("超管统计异常: %+v", res.UserStats)
	}

	report := res.FormatReport()
	if !strings.Contains(report, "PRAGMA integrity_check: [PASS]") {
		t.Errorf("报告缺少 PASS 标记:\n%s", report)
	}
	if !strings.Contains(report, "业务领域状态指标") {
		t.Errorf("报告缺少领域指标:\n%s", report)
	}
}

func TestReconcileMissingLegacySourceNeverReportsGreen(t *testing.T) {
	d, _ := setupTestDB(t)
	missing := filepath.Join(t.TempDir(), "missing.sqlite3")
	if _, err := Reconcile(context.Background(), d, missing); err == nil {
		t.Fatal("missing explicit old database was accepted")
	}
	if _, err := os.Stat(missing); !os.IsNotExist(err) {
		t.Fatalf("created old database: %v", err)
	}
}

func TestReconcileMissingLegacyTablesFailTheGate(t *testing.T) {
	d, _ := setupTestDB(t)
	oldPath := filepath.Join(t.TempDir(), "partial.sqlite3")
	old, err := sql.Open("sqlite", oldPath)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := old.Exec("CREATE TABLE marker (id INTEGER)"); err != nil {
		t.Fatal(err)
	}
	old.Close()
	result, err := Reconcile(context.Background(), d, oldPath)
	if err != nil {
		t.Fatal(err)
	}
	if result.OverallOK {
		t.Fatal("missing old tables reported a matching migration")
	}
}

func TestReconcilePublishedArticlesReadActualPageSchema(t *testing.T) {
	d, _ := setupTestDB(t)
	if err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		if _, err := tx.ExecContext(ctx, `INSERT INTO pages(id,kind,slug,title,live,created_at,updated_at) VALUES(7,'article','counted','Counted',1,'2026-10-12T00:00:00Z','2026-10-12T00:00:00Z')`); err != nil {
			return err
		}
		_, err := tx.ExecContext(ctx, `INSERT INTO articles(page_id) VALUES(7)`)
		return err
	}); err != nil {
		t.Fatal(err)
	}
	result, err := Reconcile(context.Background(), d, "")
	if err != nil {
		t.Fatal(err)
	}
	if result.DomainStats["articles_published"] != 1 {
		t.Fatalf("published metric silently became zero: %+v", result.DomainStats)
	}
}
