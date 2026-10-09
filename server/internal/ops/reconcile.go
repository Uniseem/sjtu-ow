package ops

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	_ "modernc.org/sqlite"
)

// TableStat 单表统计对比。
type TableStat struct {
	EntityName  string
	NewTable    string
	LegacyTable string
	NewCount    int64
	LegacyCount int64
	Status      string
}

// ReconcileResult 对账与一致性检查结果（12 号文档 8.3）。
type ReconcileResult struct {
	IntegrityOK  bool
	FKCheckOK    bool
	FKViolations []string
	Tables       []TableStat
	UserStats    map[string]int64
	SampleReport []string
}

// Reconcile 执行数据库一致性自检与新旧库对账。
func Reconcile(ctx context.Context, d *db.DB, legacyPath string) (*ReconcileResult, error) {
	if d == nil {
		return nil, fmt.Errorf("数据库连接为空")
	}

	newDB := d.ReadPool()

	result := &ReconcileResult{
		UserStats: make(map[string]int64),
	}

	// 1. 完整性检查
	var integrityStr string
	err := newDB.QueryRowContext(ctx, "PRAGMA integrity_check;").Scan(&integrityStr)
	if err != nil || integrityStr != "ok" {
		result.IntegrityOK = false
		return result, fmt.Errorf("PRAGMA integrity_check 失败: %s (err: %v)", integrityStr, err)
	}
	result.IntegrityOK = true

	// 2. 外键引用完整性检查
	fkRows, err := newDB.QueryContext(ctx, "PRAGMA foreign_key_check;")
	if err == nil {
		defer fkRows.Close()
		result.FKCheckOK = true
		for fkRows.Next() {
			var table, parent string
			var rowid, fkid int64
			if err := fkRows.Scan(&table, &rowid, &parent, &fkid); err == nil {
				result.FKCheckOK = false
				result.FKViolations = append(result.FKViolations, fmt.Sprintf("表 %s (rowid %d) -> 父表 %s (fkid %d)", table, rowid, parent, fkid))
			}
		}
	}

	// 3. 用户域详细统计
	countQuery := func(query string) int64 {
		var cnt int64
		_ = newDB.QueryRowContext(ctx, query).Scan(&cnt)
		return cnt
	}

	result.UserStats["total_users"] = countQuery("SELECT count(*) FROM users")
	result.UserStats["active_users"] = countQuery("SELECT count(*) FROM users WHERE is_active = 1")
	result.UserStats["superusers"] = countQuery("SELECT count(*) FROM users WHERE is_superuser = 1")
	result.UserStats["verified_users"] = countQuery("SELECT count(*) FROM users WHERE email_verified_at IS NOT NULL")
	result.UserStats["sjtu_users"] = countQuery("SELECT count(*) FROM users WHERE is_sjtu = 1")

	// 4. 统计新表行数
	tableMappings := []struct {
		entity string
		newTab string
		legTab string
	}{
		{"用户账号", "users", "accounts_user"},
		{"战队", "teams", "teams_team"},
		{"赛事", "tournaments", "tournaments_tournament"},
		{"内战", "scrims", "scrims_scrim"},
		{"文章", "articles", "content_articlepage"},
		{"评论", "comments", "comments_comment"},
		{"图片母版", "images", "wagtailimages_image"},
		{"成员分组", "member_groups", "members_membergroup"},
		{"审核记录", "moderation_records", "moderation_moderationrecord"},
	}

	var legacyDB *sql.DB
	if legacyPath != "" {
		ldb, err := sql.Open("sqlite", fmt.Sprintf("file:%s?mode=ro", legacyPath))
		if err == nil {
			legacyDB = ldb
			defer legacyDB.Close()
		}
	}

	for _, m := range tableMappings {
		newCnt := countQuery(fmt.Sprintf("SELECT count(*) FROM %s", m.newTab))
		var legCnt int64 = -1
		status := "OK"

		if legacyDB != nil {
			var cnt int64
			err := legacyDB.QueryRowContext(ctx, fmt.Sprintf("SELECT count(*) FROM %s", m.legTab)).Scan(&cnt)
			if err == nil {
				legCnt = cnt
				if newCnt == legCnt {
					status = "MATCH"
				} else {
					status = "COUNT_DIFF"
				}
			} else {
				status = "LEGACY_TABLE_MISSING"
			}
		}

		result.Tables = append(result.Tables, TableStat{
			EntityName:  m.entity,
			NewTable:    m.newTab,
			LegacyTable: m.legTab,
			NewCount:    newCnt,
			LegacyCount: legCnt,
			Status:      status,
		})
	}

	// 5. 若有旧库，抽样比对超级管理员与关键用户
	if legacyDB != nil {
		rows, err := newDB.QueryContext(ctx, "SELECT email, is_superuser, is_active FROM users ORDER BY id LIMIT 5")
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var email string
				var isSuper, isActive int
				if err := rows.Scan(&email, &isSuper, &isActive); err == nil {
					var legSuper, legActive int
					// 在 Django 的 auth_user 中核对
					q := "SELECT is_superuser, is_active FROM auth_user WHERE email = ? LIMIT 1"
					err := legacyDB.QueryRowContext(ctx, q, email).Scan(&legSuper, &legActive)
					if err == nil {
						match := (isSuper == legSuper) && (isActive == legActive)
						result.SampleReport = append(result.SampleReport,
							fmt.Sprintf("用户 %s: 新库 (super=%d, active=%d) vs 旧库 (super=%d, active=%d) -> match=%v",
								email, isSuper, isActive, legSuper, legActive, match))
					} else {
						result.SampleReport = append(result.SampleReport, fmt.Sprintf("用户 %s: 旧库中未检索到同邮箱记录", email))
					}
				}
			}
		}
	}

	return result, nil
}

// FormatReport 格式化输出对账结果报告。
func (r *ReconcileResult) FormatReport() string {
	var sb strings.Builder
	sb.WriteString("=== SJTU-OW 数据库一致性与对账报告 ===\n")
	sb.WriteString(fmt.Sprintf("PRAGMA integrity_check: %v\n", r.IntegrityOK))
	sb.WriteString(fmt.Sprintf("PRAGMA foreign_key_check: %v\n", r.FKCheckOK))
	if len(r.FKViolations) > 0 {
		sb.WriteString("  外键破坏条目:\n")
		for _, v := range r.FKViolations {
			sb.WriteString(fmt.Sprintf("    - %s\n", v))
		}
	}

	sb.WriteString("\n--- 用户域指标 ---\n")
	for k, v := range r.UserStats {
		sb.WriteString(fmt.Sprintf("  %-18s: %d\n", k, v))
	}

	sb.WriteString("\n--- 表行数对照 ---\n")
	sb.WriteString(fmt.Sprintf("  %-12s %-20s %-26s %-10s %-10s %-8s\n", "实体", "新表", "旧表", "新库行数", "旧库行数", "状态"))
	for _, t := range r.Tables {
		legStr := "-"
		if t.LegacyCount >= 0 {
			legStr = fmt.Sprintf("%d", t.LegacyCount)
		}
		sb.WriteString(fmt.Sprintf("  %-12s %-20s %-26s %-10d %-10s %-8s\n",
			t.EntityName, t.NewTable, t.LegacyTable, t.NewCount, legStr, t.Status))
	}

	if len(r.SampleReport) > 0 {
		sb.WriteString("\n--- 关键用户抽样比对 ---\n")
		for _, s := range r.SampleReport {
			sb.WriteString(fmt.Sprintf("  * %s\n", s))
		}
	}
	sb.WriteString("======================================\n")
	return sb.String()
}
