package ops

import (
	"context"
	"strings"
	"testing"
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
