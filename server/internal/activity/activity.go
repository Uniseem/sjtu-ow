package activity

import (
	"bytes"
	"context"
	"encoding/csv"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Event 表示一条活动事件（内战或赛事）。
type Event struct {
	When    time.Time `json:"when"`
	Kind    string    `json:"kind"` // "内战" 或 "赛事"
	Title   string    `json:"title"`
	Status  string    `json:"status"`
	Entries int       `json:"entries"` // scrims: 报名人次; tournaments: 审核通过队伍数
	Players int       `json:"players"` // scrims: 选上场人数; tournaments: 参赛队伍队员总数
	URL     string    `json:"url"`
}

// Totals 是一段时间内的活动汇总数据。
type Totals struct {
	Members          int `json:"members"`
	SJTUMembers      int `json:"sjtu_members"`
	Scrims           int `json:"scrims"`
	ScrimSignups     int `json:"scrim_signups"`
	ScrimPlayers     int `json:"scrim_players"`
	ScrimPeople      int `json:"scrim_people"`
	Tournaments      int `json:"tournaments"`
	TournamentTeams  int `json:"tournament_teams"`
	TournamentPeople int `json:"tournament_people"`
	Articles         int `json:"articles"`
	Comments         int `json:"comments"`
	Teams            int `json:"teams"`
}

// Period 表示统计时间区间（上海时区）。
type Period struct {
	Start time.Time `json:"start"`
	End   time.Time `json:"end"`
}

// Service 提供活动数据统计与导出。
type Service struct {
	d       *db.DB
	siteURL string
}

// NewService 创建活动数据服务。
func NewService(d *db.DB, siteURL string) *Service {
	return &Service{d: d, siteURL: siteURL}
}

var shLoc *time.Location

func init() {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		loc = time.FixedZone("CST", 8*3600)
	}
	shLoc = loc
}

// DatesToPeriod 解析参数中的日期或预设，返回对应的 since 与 until。
func DatesToPeriod(preset, startStr, endStr string, now time.Time) (Period, string) {
	today := now.In(shLoc)
	todayDate := time.Date(today.Year(), today.Month(), today.Day(), 0, 0, 0, 0, shLoc)

	switch preset {
	case "last_year":
		year := today.Year()
		if today.Month() < time.September {
			year--
		}
		since := time.Date(year-1, time.September, 1, 0, 0, 0, 0, shLoc)
		until := time.Date(year, time.September, 1, 0, 0, 0, 0, shLoc)
		return Period{Start: since, End: until.Add(-time.Second)}, ""
	case "recent_30":
		since := todayDate.AddDate(0, 0, -29)
		until := todayDate.AddDate(0, 0, 1)
		return Period{Start: since, End: until.Add(-time.Second)}, ""
	}

	if startStr != "" && endStr != "" {
		s, err1 := time.ParseInLocation("2006-01-02", startStr, shLoc)
		e, err2 := time.ParseInLocation("2006-01-02", endStr, shLoc)
		if err1 == nil && err2 == nil {
			if s.After(e) {
				// 错误回退到本学年
				p, _ := DatesToPeriod("this_year", "", "", now)
				return p, "开始日期晚于结束日期，下面是本学年的数据。"
			}
			since := time.Date(s.Year(), s.Month(), s.Day(), 0, 0, 0, 0, shLoc)
			until := time.Date(e.Year(), e.Month(), e.Day()+1, 0, 0, 0, 0, shLoc)
			return Period{Start: since, End: until.Add(-time.Second)}, ""
		}
		p, _ := DatesToPeriod("this_year", "", "", now)
		return p, "日期格式不对，下面是本学年的数据。"
	}

	// 默认本学年
	year := today.Year()
	if today.Month() < time.September {
		year--
	}
	since := time.Date(year, time.September, 1, 0, 0, 0, 0, shLoc)
	until := todayDate.AddDate(0, 0, 1)
	return Period{Start: since, End: until.Add(-time.Second)}, ""
}

// QueryEvents 查询指定时间区间的内战与赛事。
func (s *Service) QueryEvents(ctx context.Context, p Period) ([]Event, error) {
	sinceStr := db.FormatUTC(p.Start)
	untilStr := db.FormatUTC(p.End.Add(time.Second)) // 补回闭合区间上界

	events := []Event{}

	// 1. 查询内战
	scrimRows, err := s.d.ReadPool().QueryContext(ctx, `
		SELECT s.id, s.title, s.status, s.starts_at,
		       (SELECT COUNT(*) FROM scrim_signups ss WHERE ss.scrim_id = s.id) AS entries,
		       (SELECT COUNT(*) FROM scrim_signups ss WHERE ss.scrim_id = s.id AND ss.is_selected = 1) AS players
		FROM scrims s
		WHERE s.status IN ('published', 'finished')
		  AND s.starts_at >= ? AND s.starts_at < ?
		ORDER BY s.starts_at ASC
	`, sinceStr, untilStr)
	if err != nil {
		return nil, fmt.Errorf("查询内战失败: %w", err)
	}
	defer scrimRows.Close()

	for scrimRows.Next() {
		var id int64
		var title, status, startsAtStr string
		var entries, players int
		if err := scrimRows.Scan(&id, &title, &status, &startsAtStr, &entries, &players); err != nil {
			return nil, err
		}
		when, _ := db.ParseUTC(startsAtStr)
		stDisplay := "已发布"
		if status == "finished" {
			stDisplay = "已结束"
		}
		events = append(events, Event{
			When:    when.In(shLoc),
			Kind:    "内战",
			Title:   title,
			Status:  stDisplay,
			Entries: entries,
			Players: players,
			URL:     fmt.Sprintf("/admin/scrims/%d/", id),
		})
	}

	// 2. 查询赛事
	tournRows, err := s.d.ReadPool().QueryContext(ctx, `
		SELECT t.id, t.title, t.status, COALESCE(t.starts_at, t.registration_closes_at, t.created_at) AS day_time,
		       (SELECT COUNT(*) FROM registrations tr WHERE tr.tournament_id = t.id AND tr.status = 'approved') AS approved_teams,
		       (SELECT COUNT(DISTINCT tm.user_id)
		        FROM registration_members tm
		        JOIN registrations tr ON tr.id = tm.registration_id
		        WHERE tr.tournament_id = t.id AND tr.status = 'approved' AND tm.is_active = 1) AS roster_players
		FROM tournaments t
		WHERE t.status IN ('published', 'finished')
		  AND COALESCE(t.starts_at, t.registration_closes_at, t.created_at) >= ?
		  AND COALESCE(t.starts_at, t.registration_closes_at, t.created_at) < ?
		ORDER BY day_time ASC
	`, sinceStr, untilStr)
	if err != nil {
		return nil, fmt.Errorf("查询赛事失败: %w", err)
	}
	defer tournRows.Close()

	for tournRows.Next() {
		var id int64
		var title, status, dayTimeStr string
		var entries, players int
		if err := tournRows.Scan(&id, &title, &status, &dayTimeStr, &entries, &players); err != nil {
			return nil, err
		}
		when, _ := db.ParseUTC(dayTimeStr)
		stDisplay := "已发布"
		if status == "finished" {
			stDisplay = "已结束"
		}
		events = append(events, Event{
			When:    when.In(shLoc),
			Kind:    "赛事",
			Title:   title,
			Status:  stDisplay,
			Entries: entries,
			Players: players,
			URL:     fmt.Sprintf("/admin/tournaments/%d/", id),
		})
	}

	return events, nil
}

// QueryTotals 查询指定时间区间的宏观统计。
func (s *Service) QueryTotals(ctx context.Context, p Period, evs []Event) (Totals, error) {
	sinceStr := db.FormatUTC(p.Start)
	untilStr := db.FormatUTC(p.End.Add(time.Second))

	var t Totals

	// 内战/赛事聚合
	for _, e := range evs {
		if e.Kind == "内战" {
			t.Scrims++
			t.ScrimSignups += e.Entries
			t.ScrimPlayers += e.Players
		} else if e.Kind == "赛事" {
			t.Tournaments++
			t.TournamentTeams += e.Entries
		}
	}

	rd := s.d.ReadPool()

	// 独立报名内战的人数
	_ = rd.QueryRowContext(ctx, `
		SELECT COUNT(DISTINCT ss.user_id)
		FROM scrim_signups ss
		JOIN scrims s ON s.id = ss.scrim_id
		WHERE s.status IN ('published', 'finished')
		  AND s.starts_at >= ? AND s.starts_at < ?
	`, sinceStr, untilStr).Scan(&t.ScrimPeople)

	// 独立参赛队伍队员数
	_ = rd.QueryRowContext(ctx, `
		SELECT COUNT(DISTINCT tm.user_id)
		FROM registration_members tm
		JOIN registrations tr ON tr.id = tm.registration_id
		JOIN tournaments t ON t.id = tr.tournament_id
		WHERE t.status IN ('published', 'finished')
		  AND tr.status = 'approved' AND tm.is_active = 1
		  AND COALESCE(t.starts_at, t.registration_closes_at, t.created_at) >= ?
		  AND COALESCE(t.starts_at, t.registration_closes_at, t.created_at) < ?
	`, sinceStr, untilStr).Scan(&t.TournamentPeople)

	// 注册用户（已加入成员：邮箱已验证）
	_ = rd.QueryRowContext(ctx, `
		SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_sjtu = 1 THEN 1 ELSE 0 END), 0)
		FROM users
		WHERE is_active = 1 AND email_verified_at IS NOT NULL
		  AND created_at >= ? AND created_at < ?
	`, sinceStr, untilStr).Scan(&t.Members, &t.SJTUMembers)

	// 文章发布数
	_ = rd.QueryRowContext(ctx, `
		SELECT COUNT(*)
		FROM pages
		WHERE status = 'published'
		  AND first_published_at >= ? AND first_published_at < ?
	`, sinceStr, untilStr).Scan(&t.Articles)

	// 评论数（未删未隐）
	_ = rd.QueryRowContext(ctx, `
		SELECT COUNT(*)
		FROM comments
		WHERE is_deleted = 0 AND is_hidden = 0
		  AND created_at >= ? AND created_at < ?
	`, sinceStr, untilStr).Scan(&t.Comments)

	// 战队新建数
	_ = rd.QueryRowContext(ctx, `
		SELECT COUNT(*)
		FROM teams
		WHERE created_at >= ? AND created_at < ?
	`, sinceStr, untilStr).Scan(&t.Teams)

	return t, nil
}

// GenerateCSV 导出 UTF-8 BOM CSV。
func GenerateCSV(events []Event) ([]byte, error) {
	var buf bytes.Buffer
	buf.WriteString("\xef\xbb\xbf") // UTF-8 BOM for Excel
	w := csv.NewWriter(&buf)

	if err := w.Write([]string{"日期", "类型", "标题", "状态", "报名人次或队伍", "上场或参赛人数"}); err != nil {
		return nil, err
	}

	for _, e := range events {
		row := []string{
			e.When.Format("2006-01-02 15:04"),
			e.Kind,
			e.Title,
			e.Status,
			fmt.Sprintf("%d", e.Entries),
			fmt.Sprintf("%d", e.Players),
		}
		if err := w.Write(row); err != nil {
			return nil, err
		}
	}
	w.Flush()
	return buf.Bytes(), w.Error()
}
