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
	EntityName  string `json:"entity_name"`
	NewTable    string `json:"new_table"`
	LegacyTable string `json:"legacy_table"`
	NewCount    int64  `json:"new_count"`
	LegacyCount int64  `json:"legacy_count"`
	Status      string `json:"status"`
}

// ReconcileResult 对账与一致性检查结果（12 号文档 8.3）。
type ReconcileResult struct {
	IntegrityOK  bool             `json:"integrity_ok"`
	FKCheckOK    bool             `json:"fk_check_ok"`
	FKViolations []string         `json:"fk_violations,omitempty"`
	Tables       []TableStat      `json:"tables"`
	UserStats    map[string]int64 `json:"user_stats"`
	DomainStats  map[string]int64 `json:"domain_stats"`
	SampleReport []string         `json:"sample_report,omitempty"`
	OverallOK    bool             `json:"overall_ok"`
}

// Reconcile 执行数据库一致性自检与新旧库对账。
func Reconcile(ctx context.Context, d *db.DB, legacyPath string) (*ReconcileResult, error) {
	if d == nil {
		return nil, fmt.Errorf("数据库连接为空")
	}

	newDB := d.ReadPool()

	result := &ReconcileResult{
		UserStats:   make(map[string]int64),
		DomainStats: make(map[string]int64),
		OverallOK:   true,
	}

	// 1. 完整性检查
	var integrityStr string
	err := newDB.QueryRowContext(ctx, "PRAGMA integrity_check;").Scan(&integrityStr)
	if err != nil || integrityStr != "ok" {
		result.IntegrityOK = false
		result.OverallOK = false
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
				result.OverallOK = false
				result.FKViolations = append(result.FKViolations, fmt.Sprintf("表 %s (rowid %d) -> 父表 %s (fkid %d)", table, rowid, parent, fkid))
			}
		}
	}

	// 3. 用户与各领域指标统计（按状态分组，12 号文档 8.3）
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

	// 领域指标状态分组
	result.DomainStats["articles_published"] = countQuery("SELECT count(*) FROM articles WHERE live = 1")
	result.DomainStats["articles_draft"] = countQuery("SELECT count(*) FROM articles WHERE live = 0")
	result.DomainStats["tournaments_active"] = countQuery("SELECT count(*) FROM tournaments WHERE is_active = 1")
	result.DomainStats["tournaments_reg_open"] = countQuery("SELECT count(*) FROM tournaments WHERE registration_open = 1")
	result.DomainStats["scrims_active"] = countQuery("SELECT count(*) FROM scrims WHERE is_active = 1")
	result.DomainStats["scrims_open"] = countQuery("SELECT count(*) FROM scrims WHERE is_open = 1")
	result.DomainStats["teams_active"] = countQuery("SELECT count(*) FROM teams WHERE disbanded_at IS NULL")
	result.DomainStats["teams_disbanded"] = countQuery("SELECT count(*) FROM teams WHERE disbanded_at IS NOT NULL")
	result.DomainStats["registrations_confirmed"] = countQuery("SELECT count(*) FROM registrations WHERE status = 'confirmed'")
	result.DomainStats["registrations_pending"] = countQuery("SELECT count(*) FROM registrations WHERE status = 'pending'")
	result.DomainStats["comments_normal"] = countQuery("SELECT count(*) FROM comments WHERE is_hidden = 0")
	result.DomainStats["comments_hidden"] = countQuery("SELECT count(*) FROM comments WHERE is_hidden = 1")

	// 4. 统计新表行数与新旧表对照
	tableMappings := []struct {
		entity string
		newTab string
		legTab string
	}{
		{"用户账号", "users", "accounts_user"},
		{"战队", "teams", "teams_team"},
		{"战队成员", "team_memberships", "teams_teammembership"},
		{"赛事", "tournaments", "tournaments_tournament"},
		{"赛事报名", "registrations", "tournaments_registration"},
		{"内战", "scrims", "scrims_scrim"},
		{"内战报名", "scrim_signups", "scrims_scrimsignup"},
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
					result.OverallOK = false
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

	// 5. 若有旧库，抽样比对超级管理员、文章与战队（12 号文档 8.3）
	if legacyDB != nil {
		// (1) 用户抽样
		rows, err := newDB.QueryContext(ctx, "SELECT email, is_superuser, is_active FROM users ORDER BY id LIMIT 5")
		if err == nil {
			defer rows.Close()
			for rows.Next() {
				var email string
				var isSuper, isActive int
				if err := rows.Scan(&email, &isSuper, &isActive); err == nil {
					var legSuper, legActive int
					q := "SELECT is_superuser, is_active FROM accounts_user WHERE email = ? LIMIT 1"
					err := legacyDB.QueryRowContext(ctx, q, email).Scan(&legSuper, &legActive)
					if err == nil {
						match := (isSuper == legSuper) && (isActive == legActive)
						result.SampleReport = append(result.SampleReport,
							fmt.Sprintf("用户 %s: 新库 (super=%d, active=%d) vs 旧库 (super=%d, active=%d) -> match=%v",
								email, isSuper, isActive, legSuper, legActive, match))
						if !match {
							result.OverallOK = false
						}
					} else {
						result.SampleReport = append(result.SampleReport, fmt.Sprintf("用户 %s: 旧库中未检索到同邮箱记录", email))
					}
				}
			}
		}

		// (2) 文章抽样
		artRows, err := newDB.QueryContext(ctx, "SELECT id, title, slug FROM articles ORDER BY id LIMIT 3")
		if err == nil {
			defer artRows.Close()
			for artRows.Next() {
				var id int64
				var title, slug string
				if err := artRows.Scan(&id, &title, &slug); err == nil {
					var legTitle string
					q := "SELECT p.title FROM content_articlepage a JOIN wagtailcore_page p ON a.page_ptr_id = p.id WHERE a.page_ptr_id = ?"
					err := legacyDB.QueryRowContext(ctx, q, id).Scan(&legTitle)
					if err == nil {
						match := (title == legTitle)
						result.SampleReport = append(result.SampleReport,
							fmt.Sprintf("文章 #%d: 新库「%s」vs 旧库「%s」-> match=%v", id, title, legTitle, match))
					}
				}
			}
		}

		// (3) 战队抽样
		teamRows, err := newDB.QueryContext(ctx, "SELECT id, name FROM teams ORDER BY id LIMIT 3")
		if err == nil {
			defer teamRows.Close()
			for teamRows.Next() {
				var id int64
				var name string
				if err := teamRows.Scan(&id, &name); err == nil {
					var legName string
					q := "SELECT name FROM teams_team WHERE id = ?"
					err := legacyDB.QueryRowContext(ctx, q, id).Scan(&legName)
					if err == nil {
						match := (name == legName)
						result.SampleReport = append(result.SampleReport,
							fmt.Sprintf("战队 #%d: 新库「%s」vs 旧库「%s」-> match=%v", id, name, legName, match))
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
	sb.WriteString("=== SJTU-OW 数据库一致性与新旧对账报告 ===\n")
	sb.WriteString(fmt.Sprintf("综合自检结果: %s\n", statusBadge(r.OverallOK)))
	sb.WriteString(fmt.Sprintf("PRAGMA integrity_check: %s\n", statusBadge(r.IntegrityOK)))
	sb.WriteString(fmt.Sprintf("PRAGMA foreign_key_check: %s\n", statusBadge(r.FKCheckOK)))
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

	sb.WriteString("\n--- 业务领域状态指标 ---\n")
	for k, v := range r.DomainStats {
		sb.WriteString(fmt.Sprintf("  %-24s: %d\n", k, v))
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
		sb.WriteString("\n--- 关键对象抽样比对 ---\n")
		for _, s := range r.SampleReport {
			sb.WriteString(fmt.Sprintf("  * %s\n", s))
		}
	}
	sb.WriteString("==========================================\n")
	return sb.String()
}
