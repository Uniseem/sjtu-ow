package ops

import (
	"context"
	"database/sql"
	"fmt"
	"net/url"
	"os"
	"strings"
	"time"

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

	// Every query error is a failed gate, never a manufactured zero count.
	fkRows, err := newDB.QueryContext(ctx, "PRAGMA foreign_key_check")
	if err != nil {
		return result, err
	}
	result.FKCheckOK = true
	for fkRows.Next() {
		var table, parent string
		var rowid, fkid int64
		if err := fkRows.Scan(&table, &rowid, &parent, &fkid); err != nil {
			fkRows.Close()
			return result, err
		}
		result.FKCheckOK = false
		result.OverallOK = false
		result.FKViolations = append(result.FKViolations, fmt.Sprintf("表 %s rowid=%d 父表 %s", table, rowid, parent))
	}
	fkRows.Close()
	if err := fkRows.Err(); err != nil {
		return result, err
	}
	metrics := []struct {
		name, query string
		user        bool
	}{
		{"total_users", "SELECT count(*) FROM users", true},
		{"active_users", "SELECT count(*) FROM users WHERE is_active=1", true},
		{"superusers", "SELECT count(*) FROM users WHERE is_superuser=1", true},
		{"verified_users", "SELECT count(*) FROM users WHERE email_verified_at IS NOT NULL", true},
		{"sjtu_users", "SELECT count(*) FROM users WHERE is_sjtu=1", true},
		{"articles_published", "SELECT count(*) FROM articles a JOIN pages p ON p.id=a.page_id WHERE p.live=1", false},
		{"articles_draft", "SELECT count(*) FROM articles a JOIN pages p ON p.id=a.page_id WHERE p.live=0", false},
		{"tournaments_active", "SELECT count(*) FROM tournaments WHERE status='published'", false},
		{"tournaments_reg_open", "SELECT count(*) FROM tournaments WHERE status='published' AND registration_opens_at<=? AND registration_closes_at>?", false},
		{"scrims_active", "SELECT count(*) FROM scrims WHERE status='published'", false},
		{"scrims_open", "SELECT count(*) FROM scrims WHERE status='published' AND COALESCE(signup_closes_at,starts_at)>?", false},
		{"teams_active", "SELECT count(*) FROM teams WHERE disbanded_at IS NULL", false},
		{"teams_disbanded", "SELECT count(*) FROM teams WHERE disbanded_at IS NOT NULL", false},
		{"registrations_confirmed", "SELECT count(*) FROM registrations WHERE status='approved'", false},
		{"registrations_pending", "SELECT count(*) FROM registrations WHERE status='pending'", false},
		{"comments_normal", "SELECT count(*) FROM comments WHERE is_hidden=0", false},
		{"comments_hidden", "SELECT count(*) FROM comments WHERE is_hidden=1", false},
	}
	now := db.FormatUTC(time.Now().UTC())
	for _, metric := range metrics {
		args := []any{}
		for i := 0; i < strings.Count(metric.query, "?"); i++ {
			args = append(args, now)
		}
		var count int64
		if err := newDB.QueryRowContext(ctx, metric.query, args...).Scan(&count); err != nil {
			return result, fmt.Errorf("对账指标%s读取失败: %w", metric.name, err)
		}
		if metric.user {
			result.UserStats[metric.name] = count
		} else {
			result.DomainStats[metric.name] = count
		}
	}
	mappings := []struct{ entity, newTable, legacyTable string }{
		{"用户账号", "users", "accounts_user"},
		{"游戏ID", "game_accounts", "accounts_gameaccount"},
		{"联系方式", "contacts", "accounts_contactmethod"},
		{"战队", "teams", "teams_team"},
		{"战队成员", "team_memberships", "teams_teammembership"},
		{"赛事", "tournaments", "tournaments_tournament"},
		{"赛事报名", "registrations", "tournaments_registration"},
		{"赛事名单", "registration_members", "tournaments_registrationmember"},
		{"个人报名", "individual_signups", "tournaments_individualsignup"},
		{"内战", "scrims", "scrims_scrim"},
		{"内战报名", "scrim_signups", "scrims_scrimsignup"},
		{"文章", "articles", "content_articlepage"},
		{"普通页", "site_pages", "content_standardpage"},
		{"评论", "comments", "comments_comment"},
		{"图片母版", "images", "wagtailimages_image"},
		{"图片集合", "image_collections", "wagtailcore_collection"},
		{"成员分组", "member_groups", "members_membergroup"},
		{"审核记录", "moderation_items", "moderation_moderationitem"},
		{"站点设置", "site_settings", "core_sitesettings"},
		{"字体", "font_families", "core_fontfamily"},
		{"字体切片记录", "font_faces", "core_fontface"},
		{"冻结信", "held_letters", "core_heldletter"},
	}
	var legacyDB *sql.DB
	if legacyPath != "" {
		if info, err := os.Stat(legacyPath); err != nil || !info.Mode().IsRegular() || info.Size() == 0 {
			return result, fmt.Errorf("旧库输入不存在或为空")
		}
		legacyDB, err = sql.Open("sqlite", (&url.URL{Scheme: "file", Path: legacyPath, RawQuery: "mode=ro"}).String())
		if err != nil {
			return result, err
		}
		defer legacyDB.Close()
		if err := legacyDB.PingContext(ctx); err != nil {
			return result, err
		}
	}
	for _, mapping := range mappings {
		stat := TableStat{EntityName: mapping.entity, NewTable: mapping.newTable, LegacyTable: mapping.legacyTable, LegacyCount: -1, Status: "OK"}
		if err := newDB.QueryRowContext(ctx, "SELECT count(*) FROM "+mapping.newTable).Scan(&stat.NewCount); err != nil {
			return result, err
		}
		if legacyDB != nil {
			if err := legacyDB.QueryRowContext(ctx, "SELECT count(*) FROM "+mapping.legacyTable).Scan(&stat.LegacyCount); err != nil {
				stat.Status = "LEGACY_QUERY_FAILED"
				result.OverallOK = false
			} else if stat.NewCount != stat.LegacyCount {
				stat.Status = "COUNT_DIFF"
				result.OverallOK = false
			} else {
				stat.Status = "MATCH"
			}
		}
		result.Tables = append(result.Tables, stat)
	}
	if legacyDB != nil {
		if err := reconcileAudit(ctx, newDB, legacyDB, result); err != nil {
			return result, err
		}
	}
	// Identity/title samples compare by preserved IDs. Reports contain counts
	// and flags only: no actual addresses, nicknames or article titles.
	if legacyDB != nil {
		for _, sample := range []struct{ name, current, legacy string }{
			{"users", "SELECT id,is_superuser,is_active FROM users ORDER BY id LIMIT 5", "SELECT is_superuser,is_active FROM accounts_user WHERE id=?"},
			{"articles", "SELECT p.id,p.title,p.slug FROM articles a JOIN pages p ON p.id=a.page_id ORDER BY p.id LIMIT 3", "SELECT p.title,p.slug FROM content_articlepage a JOIN wagtailcore_page p ON p.id=a.page_ptr_id WHERE p.id=?"},
			{"teams", "SELECT id,name,name FROM teams ORDER BY id LIMIT 3", "SELECT name,name FROM teams_team WHERE id=?"},
		} {
			rows, err := newDB.QueryContext(ctx, sample.current)
			if err != nil {
				return result, err
			}
			matched, checked := 0, 0
			for rows.Next() {
				var id int64
				var first, second, oldFirst, oldSecond string
				if err := rows.Scan(&id, &first, &second); err != nil {
					rows.Close()
					return result, err
				}
				checked++
				if err := legacyDB.QueryRowContext(ctx, sample.legacy, id).Scan(&oldFirst, &oldSecond); err == nil && first == oldFirst && second == oldSecond {
					matched++
				} else {
					result.OverallOK = false
				}
			}
			rows.Close()
			if err := rows.Err(); err != nil {
				return result, err
			}
			result.SampleReport = append(result.SampleReport, fmt.Sprintf("%s checked=%d matched=%d", sample.name, checked, matched))
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
