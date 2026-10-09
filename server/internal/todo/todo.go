package todo

import (
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Item 是后台待办的一项。
type Item struct {
	Text  string `json:"text"`
	URL   string `json:"url"`
	Count int    `json:"count"`
}

// Result 是待办查询结果。
type Result struct {
	HasDuties bool   `json:"has_duties"`
	Items     []Item `json:"items"`
}

// Service 负责聚合后台各模块的待办事项。
type Service struct {
	d *db.DB
}

// NewService 创建待办服务。
func NewService(d *db.DB) *Service {
	return &Service{d: d}
}

// GetDuties 查询当前用户的待办事项。
func (s *Service) GetDuties(ctx *app.Ctx) (*Result, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled {
		return &Result{HasDuties: false, Items: []Item{}}, nil
	}

	isSuper := v.Superuser
	canTourn := isSuper || v.HasRole(accounts.RoleTournamentAdmin) || v.HasCap(accounts.CapTournamentsManage)
	canScrim := isSuper || v.HasRole(accounts.RoleScrimAdmin) || v.HasCap(accounts.CapScrimsManage)
	canContent := isSuper || v.HasRole(accounts.RoleContentEditor) || v.HasCap(accounts.CapArticlesEditAny)

	now := ctx.Now().UTC()
	nowStr := db.FormatUTC(now)
	items := []Item{}

	rd := s.d.ReadPool()

	// 1. 待发信确认（规则 206–207，design 10.5）
	var letterBatches int
	_ = rd.QueryRowContext(ctx.Context, `
		SELECT COUNT(DISTINCT batch_id)
		FROM held_letters
		WHERE author_id = ? AND status = 'waiting' AND expires_at > ?
	`, v.ID, nowStr).Scan(&letterBatches)
	if letterBatches > 0 {
		items = append(items, Item{
			Text:  fmt.Sprintf("有 %d 件事的信还没决定发不发", letterBatches),
			URL:   "/admin/letters/",
			Count: letterBatches,
		})
	}

	// 2. 赛事管理员待办（规则 142）
	if canTourn {
		// 待审核报名
		var pendingRegs int
		_ = rd.QueryRowContext(ctx.Context, `
			SELECT COUNT(*)
			FROM tournament_registrations tr
			JOIN tournaments t ON t.id = tr.tournament_id
			WHERE tr.status = 'pending' AND t.status != 'cancelled'
		`).Scan(&pendingRegs)
		if pendingRegs > 0 {
			items = append(items, Item{
				Text:  fmt.Sprintf("%d 份报名等待审核", pendingRegs),
				URL:   "/admin/registrations/?status=pending",
				Count: pendingRegs,
			})
		}

		// 等待编队的散人
		waitingRows, err := rd.QueryContext(ctx.Context, `
			SELECT t.id, t.title, COUNT(*)
			FROM tournament_individual_signups s
			JOIN tournaments t ON t.id = s.tournament_id
			WHERE s.registration_id IS NULL AND t.status = 'published'
			GROUP BY t.id, t.title
			ORDER BY t.title ASC
		`)
		if err == nil {
			defer waitingRows.Close()
			for waitingRows.Next() {
				var tID int64
				var tTitle string
				var cnt int
				if err := waitingRows.Scan(&tID, &tTitle, &cnt); err == nil && cnt > 0 {
					items = append(items, Item{
						Text:  fmt.Sprintf("「%s」有 %d 人等待编队", tTitle, cnt),
						URL:   fmt.Sprintf("/admin/tournaments/%d/teams/", tID),
						Count: cnt,
					})
				}
			}
		}

		// 开赛超 3 天未结束
		threeDaysAgo := db.FormatUTC(now.AddDate(0, 0, -3))
		overRows, err := rd.QueryContext(ctx.Context, `
			SELECT id, title
			FROM tournaments
			WHERE status = 'published' AND starts_at IS NOT NULL AND starts_at < ?
			ORDER BY starts_at ASC
		`, threeDaysAgo)
		if err == nil {
			defer overRows.Close()
			for overRows.Next() {
				var tID int64
				var tTitle string
				if err := overRows.Scan(&tID, &tTitle); err == nil {
					items = append(items, Item{
						Text:  fmt.Sprintf("「%s」开赛已经 3 天以上，打完了的话在赛事列表的「更多」里标记已结束", tTitle),
						URL:   "/admin/tournaments/",
						Count: 1,
					})
				}
			}
		}
	}

	// 3. 内战管理员待办（规则 168）
	if canScrim {
		unsplitRows, err := rd.QueryContext(ctx.Context, `
			SELECT s.id, s.title
			FROM scrims s
			WHERE s.status = 'published'
			  AND s.signup_closes_at <= ? AND s.starts_at > ?
			  AND NOT EXISTS (
			      SELECT 1 FROM scrim_signups ss
			      WHERE ss.scrim_id = s.id AND ss.team IN ('a', 'b')
			  )
			ORDER BY s.starts_at ASC
		`, nowStr, nowStr)
		if err == nil {
			defer unsplitRows.Close()
			for unsplitRows.Next() {
				var sID int64
				var sTitle string
				if err := unsplitRows.Scan(&sID, &sTitle); err == nil {
					items = append(items, Item{
						Text:  fmt.Sprintf("「%s」报名已截止，还没分队", sTitle),
						URL:   fmt.Sprintf("/admin/scrims/%d/split/", sID),
						Count: 1,
					})
				}
			}
		}
	}

	// 4. 超管待办（全站维护与健康）
	if isSuper {
		// 队长已停用的战队（规则 108，design 3.7）
		var stuckTeams int
		_ = rd.QueryRowContext(ctx.Context, `
			SELECT COUNT(*)
			FROM teams t
			JOIN users u ON u.id = t.captain_id
			WHERE t.is_disbanded = 0 AND u.is_active = 0
		`).Scan(&stuckTeams)
		if stuckTeams > 0 {
			items = append(items, Item{
				Text:  fmt.Sprintf("%d 支战队的队长账号已停用，没人能审批入队申请、为它报名，去指定新队长", stuckTeams),
				URL:   "/admin/teams/?captain=gone",
				Count: stuckTeams,
			})
		}

		// AI 审核没看成
		var aiStuck int
		var aiErr string
		_ = rd.QueryRowContext(ctx.Context, `
			SELECT COUNT(*), COALESCE(MAX(last_error), '')
			FROM moderation_items
			WHERE status = 'pending' AND attempts > 0
		`).Scan(&aiStuck, &aiErr)
		if aiStuck > 0 {
			errSummary := aiErr
			if len(errSummary) > 60 {
				errSummary = errSummary[:60] + "..."
			}
			items = append(items, Item{
				Text:  fmt.Sprintf("AI 审核有 %d 条内容没看成（%s），下次巡查再试；检查全站设置里的 AI 审核，点「试一下 AI」", aiStuck, errSummary),
				URL:   "/admin/settings/site/",
				Count: aiStuck,
			})
		}

		// 后台任务 worker 心跳检测（设计 14.1，v6.44）
		var lastHeartbeatStr sql.NullString
		_ = rd.QueryRowContext(ctx.Context, `SELECT heartbeat_at FROM worker_status WHERE id = 1`).Scan(&lastHeartbeatStr)
		workerBeating := false
		if lastHeartbeatStr.Valid {
			hbTime, _ := db.ParseUTC(lastHeartbeatStr.String)
			if now.Sub(hbTime) < 120*time.Second {
				workerBeating = true
			}
		}
		if !workerBeating {
			items = append(items, Item{
				Text:  "后台任务（worker）没在运行。邮件、提醒、静态页都停了，到服务器上看 worker 容器",
				URL:   "/healthz",
				Count: 1,
			})
		}
	}

	hasDuties := isSuper || canTourn || canScrim || canContent || letterBatches > 0
	return &Result{
		HasDuties: hasDuties,
		Items:     items,
	}, nil
}
