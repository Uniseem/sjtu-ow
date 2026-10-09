package content

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// HomeAge 社区成立年龄。
type HomeAge struct {
	Years int `json:"years"`
	Days  int `json:"days"`
}

// HomeStatsOut 首页社区统计指标。
type HomeStatsOut struct {
	MemberCount int      `json:"member_count"`
	TeamCount   int      `json:"team_count"`
	ScrimsHeld  int      `json:"scrims_held"`
	FoundedOn   string   `json:"founded_on,omitempty"`
	Age         *HomeAge `json:"age,omitempty"`
	HeroImageID *int64   `json:"hero_image_id,omitempty"`
	QQGroupURL  string   `json:"qq_group_url,omitempty"`
}

// HomeFeatureTournament 近期大图推荐赛事。
type HomeFeatureTournament struct {
	ID                   int64  `json:"id"`
	Title                string `json:"title"`
	Phase                string `json:"phase"`
	PhaseLabel           string `json:"phase_label"`
	RegistrationMode     string `json:"registration_mode"`
	TakesIndividuals     bool   `json:"takes_individuals"`
	ApprovedTeams        int    `json:"approved_teams"`
	StartsAt             string `json:"starts_at,omitempty"`
	RegistrationOpensAt  string `json:"registration_opens_at,omitempty"`
	RegistrationClosesAt string `json:"registration_closes_at,omitempty"`
	CoverImageID         *int64 `json:"cover_image_id,omitempty"`
	Facts                string `json:"facts"`
}

// HomeScrimItem 近期内战行项目。
type HomeScrimItem struct {
	ID         int64  `json:"id"`
	Title      string `json:"title"`
	StartsAt   string `json:"starts_at"`
	Month      int    `json:"month"`
	Day        int    `json:"day"`
	Weekday    string `json:"weekday"`
	Time       string `json:"time"`
	Count      int    `json:"count"`
	Capacity   int    `json:"capacity"`
	SignupOpen bool   `json:"signup_open"`
}

// HomeNoticeItem 公告行项目。
type HomeNoticeItem struct {
	ID             int64  `json:"id"`
	Slug           string `json:"slug"`
	Title          string `json:"title"`
	Month          int    `json:"month"`
	Day            int    `json:"day"`
	PublishedAtRaw string `json:"published_at_raw"`
}

// HomeTeamItem 战队卡片项目。
type HomeTeamItem struct {
	ID             int64  `json:"id"`
	Name           string `json:"name"`
	LogoImageID    *int64 `json:"logo_image_id,omitempty"`
	MemberCount    int    `json:"member_count"`
	IsRecruiting   bool   `json:"is_recruiting"`
	WantedRoles    string `json:"wanted_roles,omitempty"`
	CreatedAtMonth string `json:"created_at_month"`
}

// HomePageIn 是 GET /api/page/home 的入参（空）。
type HomePageIn struct{}

// HomePageOut 是 GET /api/page/home 的出参。
type HomePageOut struct {
	Stats             *HomeStatsOut          `json:"stats"`
	FeatureTournament *HomeFeatureTournament `json:"feature_tournament,omitempty"`
	Scrims            []*HomeScrimItem       `json:"scrims"`
	News              []*NewsItemOut         `json:"news"`
	Notices           []*HomeNoticeItem      `json:"notices"`
	Teams             []*HomeTeamItem        `json:"teams"`
}

// HomePage 聚合首页所需要的全部首屏展示数据。
func (s *Service) HomePage(ctx *app.Ctx) (*HomePageOut, error) {
	return s.store.GetHomePage(ctx.Context, time.Now())
}

// GetHomePage 从数据库只读聚合首页全部数据。
func (s *Store) GetHomePage(ctx context.Context, now time.Time) (*HomePageOut, error) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		loc = time.FixedZone("CST", 8*3600)
	}
	nowInLoc := now.In(loc)

	pool := s.d.ReadPool()
	out := &HomePageOut{
		Stats:   &HomeStatsOut{},
		Scrims:  []*HomeScrimItem{},
		News:    []*NewsItemOut{},
		Notices: []*HomeNoticeItem{},
		Teams:   []*HomeTeamItem{},
	}

	// 1. 统计与全站设置
	_ = pool.QueryRowContext(ctx, `SELECT COUNT(*) FROM users WHERE is_active = 1`).Scan(&out.Stats.MemberCount)
	_ = pool.QueryRowContext(ctx, `SELECT COUNT(*) FROM teams WHERE disbanded_at IS NULL`).Scan(&out.Stats.TeamCount)
	_ = pool.QueryRowContext(ctx, `SELECT COUNT(*) FROM scrims WHERE status = 'finished'`).Scan(&out.Stats.ScrimsHeld)

	var foundedOn sql.NullString
	var heroImageID sql.NullInt64
	var qqGroupURL sql.NullString
	_ = pool.QueryRowContext(ctx, `SELECT founded_on, hero_image_id, qq_group_url FROM site_settings WHERE id = 1`).
		Scan(&foundedOn, &heroImageID, &qqGroupURL)

	if heroImageID.Valid {
		out.Stats.HeroImageID = &heroImageID.Int64
	}
	if qqGroupURL.Valid {
		out.Stats.QQGroupURL = qqGroupURL.String
	}
	if foundedOn.Valid && foundedOn.String != "" {
		out.Stats.FoundedOn = foundedOn.String
		foundedDate, err := time.Parse(time.RFC3339, foundedOn.String)
		if err != nil {
			foundedDate, err = time.Parse("2006-01-02", foundedOn.String)
		}
		if err == nil {
			fInLoc := foundedDate.In(loc)
			today := time.Date(nowInLoc.Year(), nowInLoc.Month(), nowInLoc.Day(), 0, 0, 0, 0, loc)
			fZero := time.Date(fInLoc.Year(), fInLoc.Month(), fInLoc.Day(), 0, 0, 0, 0, loc)
			if !fZero.After(today) {
				years := today.Year() - fZero.Year()
				anniv := time.Date(today.Year(), fZero.Month(), fZero.Day(), 0, 0, 0, 0, loc)
				if today.Before(anniv) {
					years--
					anniv = time.Date(today.Year()-1, fZero.Month(), fZero.Day(), 0, 0, 0, 0, loc)
				}
				days := int(today.Sub(anniv).Hours() / 24)
				out.Stats.Age = &HomeAge{Years: years, Days: days}
			}
		}
	}

	// 2. 近期推荐赛事 (Feature Tournament)
	type rawTourn struct {
		id            int64
		title         string
		status        string
		startsAt      sql.NullString
		regOpensAt    sql.NullString
		regClosesAt   sql.NullString
		regMode       string
		takesIndiv    int
		coverImageID  sql.NullInt64
		parsedStarts  *time.Time
		parsedOpens   *time.Time
		parsedCloses  *time.Time
		phase         string
		approvedCount int
	}

	tRows, err := pool.QueryContext(ctx, `
		SELECT id, title, status, starts_at, registration_opens_at, registration_closes_at, registration_mode, takes_individuals, cover_image_id
		FROM tournaments
		WHERE status IN ('published', 'finished')
		ORDER BY starts_at DESC, id DESC
	`)
	if err == nil {
		defer tRows.Close()
		var candidateList []*rawTourn
		for tRows.Next() {
			var t rawTourn
			if err := tRows.Scan(&t.id, &t.title, &t.status, &t.startsAt, &t.regOpensAt, &t.regClosesAt, &t.regMode, &t.takesIndiv, &t.coverImageID); err == nil {
				if t.startsAt.Valid {
					if pt, err := db.ParseUTC(t.startsAt.String); err == nil {
						t.parsedStarts = &pt
					}
				}
				if t.regOpensAt.Valid {
					if pt, err := db.ParseUTC(t.regOpensAt.String); err == nil {
						t.parsedOpens = &pt
					}
				}
				if t.regClosesAt.Valid {
					if pt, err := db.ParseUTC(t.regClosesAt.String); err == nil {
						t.parsedCloses = &pt
					}
				}

				if t.status == "finished" {
					t.phase = "finished"
				} else {
					if t.parsedOpens != nil && now.Before(*t.parsedOpens) {
						t.phase = "upcoming"
					} else if t.parsedCloses != nil && now.After(*t.parsedCloses) {
						t.phase = "closed"
					} else {
						t.phase = "open"
					}
				}
				candidateList = append(candidateList, &t)
			}
		}

		var chosen *rawTourn
		// 优先取 open 中最先截止的
		for _, cand := range candidateList {
			if cand.phase == "open" {
				if chosen == nil || (cand.parsedCloses != nil && (chosen.parsedCloses == nil || cand.parsedCloses.Before(*chosen.parsedCloses))) {
					chosen = cand
				}
			}
		}
		// 其次取 upcoming 或 closed 中最先开始的
		if chosen == nil {
			for _, cand := range candidateList {
				if cand.phase == "upcoming" || cand.phase == "closed" {
					if chosen == nil {
						chosen = cand
					}
				}
			}
		}
		// 再次取最近结束的
		if chosen == nil {
			for _, cand := range candidateList {
				if cand.phase == "finished" {
					chosen = cand
					break
				}
			}
		}

		if chosen != nil {
			_ = pool.QueryRowContext(ctx, `SELECT COUNT(*) FROM registrations WHERE tournament_id = ? AND status = 'approved'`, chosen.id).
				Scan(&chosen.approvedCount)

			phaseLabels := map[string]string{
				"open":     "报名中",
				"upcoming": "即将开始报名",
				"closed":   "报名已截止",
				"finished": "已结束",
			}
			modeLabel := "整队报名"
			if chosen.takesIndiv == 1 || chosen.regMode == "individual" {
				modeLabel = "个人报名"
			}

			facts := modeLabel
			if chosen.phase == "open" && chosen.parsedCloses != nil {
				cLoc := chosen.parsedCloses.In(loc)
				facts += fmt.Sprintf(" · 报名截止 %d月%d日 %s", cLoc.Month(), cLoc.Day(), cLoc.Format("15:04"))
			} else if chosen.phase == "upcoming" && chosen.parsedOpens != nil {
				oLoc := chosen.parsedOpens.In(loc)
				facts += fmt.Sprintf(" · %d月%d日 %s 开放报名", oLoc.Month(), oLoc.Day(), oLoc.Format("15:04"))
			} else if chosen.parsedStarts != nil {
				sLoc := chosen.parsedStarts.In(loc)
				if chosen.phase == "finished" {
					facts += fmt.Sprintf(" · %d.%02d.%02d", sLoc.Year(), sLoc.Month(), sLoc.Day())
				} else {
					facts += fmt.Sprintf(" · %d月%d日 比赛", sLoc.Month(), sLoc.Day())
				}
			}
			if chosen.phase != "upcoming" {
				if chosen.takesIndiv == 1 {
					facts += fmt.Sprintf(" · 已编成 %d 队", chosen.approvedCount)
				} else {
					facts += fmt.Sprintf(" · 已通过 %d 队", chosen.approvedCount)
				}
			}

			ft := &HomeFeatureTournament{
				ID:               chosen.id,
				Title:            chosen.title,
				Phase:            chosen.phase,
				PhaseLabel:       phaseLabels[chosen.phase],
				RegistrationMode: chosen.regMode,
				TakesIndividuals: chosen.takesIndiv == 1,
				ApprovedTeams:    chosen.approvedCount,
				Facts:            facts,
			}
			if chosen.coverImageID.Valid {
				ft.CoverImageID = &chosen.coverImageID.Int64
			}
			if chosen.startsAt.Valid {
				ft.StartsAt = chosen.startsAt.String
			}
			if chosen.regOpensAt.Valid {
				ft.RegistrationOpensAt = chosen.regOpensAt.String
			}
			if chosen.regClosesAt.Valid {
				ft.RegistrationClosesAt = chosen.regClosesAt.String
			}
			out.FeatureTournament = ft
		}
	}

	// 3. 近期内战 (最多 5 场)
	weekdays := []string{"周日", "周一", "周二", "周三", "周四", "周五", "周六"}
	sRows, err := pool.QueryContext(ctx, `
		SELECT s.id, s.title, s.status, s.starts_at, s.format,
		       (SELECT COUNT(*) FROM scrim_signups ss WHERE ss.scrim_id = s.id) as signup_count
		FROM scrims s
		WHERE s.status = 'published'
		ORDER BY s.starts_at ASC
		LIMIT 5
	`)
	if err == nil {
		defer sRows.Close()
		for sRows.Next() {
			var sItem HomeScrimItem
			var format string
			var startsAt sql.NullString
			if err := sRows.Scan(&sItem.ID, &sItem.Title, &sItem.StartsAt, &startsAt, &format, &sItem.Count); err == nil {
				sItem.SignupOpen = true
				sItem.Capacity = 10
				if format == "rq_6v6" || format == "open_6v6" {
					sItem.Capacity = 12
				}
				if startsAt.Valid {
					sItem.StartsAt = startsAt.String
					if st, err := db.ParseUTC(startsAt.String); err == nil {
						stLoc := st.In(loc)
						sItem.Month = int(stLoc.Month())
						sItem.Day = stLoc.Day()
						sItem.Weekday = weekdays[stLoc.Weekday()]
						sItem.Time = stLoc.Format("15:04")
					}
				}
				out.Scrims = append(out.Scrims, &sItem)
			}
		}
	}

	// 4. 资讯 (最多 4 篇，优先置顶)
	pinnedIDs := make(map[int64]bool)
	pinRows, err := pool.QueryContext(ctx, `
		SELECT p.id, p.slug, p.title, c.name, p.first_published_at, r.cover_image_id, r.summary, r.reading_time, u.nickname
		FROM home_pins hp
		JOIN pages p ON p.id = hp.article_id
		JOIN articles a ON a.page_id = p.id
		JOIN article_categories c ON c.id = a.category_id
		LEFT JOIN article_revisions r ON r.page_id = p.id AND r.is_latest_published = 1
		LEFT JOIN users u ON u.id = a.author_id
		WHERE p.live = 1
		ORDER BY hp.pin_order ASC
		LIMIT 4
	`)
	if err == nil {
		defer pinRows.Close()
		for pinRows.Next() {
			var item NewsItemOut
			var coverID sql.NullInt64
			var summary sql.NullString
			var readTime sql.NullInt64
			var author sql.NullString
			var firstPub sql.NullString
			if err := pinRows.Scan(&item.ID, &item.Slug, &item.Title, &item.CategoryName, &firstPub, &coverID, &summary, &readTime, &author); err == nil {
				item.Pinned = true
				if coverID.Valid {
					item.CoverImageID = &coverID.Int64
				}
				if summary.Valid {
					item.Summary = summary.String
				}
				if readTime.Valid {
					item.ReadingTime = int(readTime.Int64)
				}
				if author.Valid {
					item.AuthorName = author.String
				}
				if firstPub.Valid {
					if pt, err := db.ParseUTC(firstPub.String); err == nil {
						item.FirstPublishedAt = &pt
					}
				}
				pinnedIDs[item.ID] = true
				out.News = append(out.News, &item)
			}
		}
	}

	if len(out.News) < 4 {
		limit := 4 - len(out.News)
		artRows, err := pool.QueryContext(ctx, `
			SELECT p.id, p.slug, p.title, c.name, p.first_published_at, r.cover_image_id, r.summary, r.reading_time, u.nickname
			FROM pages p
			JOIN articles a ON a.page_id = p.id
			JOIN article_categories c ON c.id = a.category_id
			LEFT JOIN article_revisions r ON r.page_id = p.id AND r.is_latest_published = 1
			LEFT JOIN users u ON u.id = a.author_id
			WHERE p.kind = 'article' AND p.live = 1
			ORDER BY p.first_published_at DESC
			LIMIT 10
		`)
		if err == nil {
			defer artRows.Close()
			for artRows.Next() {
				if len(out.News) >= 4 {
					break
				}
				var item NewsItemOut
				var coverID sql.NullInt64
				var summary sql.NullString
				var readTime sql.NullInt64
				var author sql.NullString
				var firstPub sql.NullString
				if err := artRows.Scan(&item.ID, &item.Slug, &item.Title, &item.CategoryName, &firstPub, &coverID, &summary, &readTime, &author); err == nil {
					if pinnedIDs[item.ID] {
						continue
					}
					if coverID.Valid {
						item.CoverImageID = &coverID.Int64
					}
					if summary.Valid {
						item.Summary = summary.String
					}
					if readTime.Valid {
						item.ReadingTime = int(readTime.Int64)
					}
					if author.Valid {
						item.AuthorName = author.String
					}
					if firstPub.Valid {
						if pt, err := db.ParseUTC(firstPub.String); err == nil {
							item.FirstPublishedAt = &pt
						}
					}
					out.News = append(out.News, &item)
					limit--
				}
			}
		}
	}

	// 5. 公告 (最多 5 篇)
	nRows, err := pool.QueryContext(ctx, `
		SELECT p.id, p.slug, p.title, p.first_published_at
		FROM pages p
		JOIN articles a ON a.page_id = p.id
		JOIN article_categories c ON c.id = a.category_id
		WHERE p.kind = 'article' AND p.live = 1 AND c.slug IN ('notice', 'event-notice')
		ORDER BY p.first_published_at DESC
		LIMIT 5
	`)
	if err == nil {
		defer nRows.Close()
		for nRows.Next() {
			var nItem HomeNoticeItem
			var pubTimeStr sql.NullString
			if err := nRows.Scan(&nItem.ID, &nItem.Slug, &nItem.Title, &pubTimeStr); err == nil {
				if pubTimeStr.Valid {
					nItem.PublishedAtRaw = pubTimeStr.String
					if pt, err := db.ParseUTC(pubTimeStr.String); err == nil {
						pLoc := pt.In(loc)
						nItem.Month = int(pLoc.Month())
						nItem.Day = pLoc.Day()
					}
				}
				out.Notices = append(out.Notices, &nItem)
			}
		}
	}

	// 6. 战队 (最多 6 支活跃战队)
	teamRows, err := pool.QueryContext(ctx, `
		SELECT t.id, t.name, t.logo_image_id, t.is_recruiting, t.recruiting_roles, t.created_at,
		       (SELECT COUNT(*) FROM team_memberships tm WHERE tm.team_id = t.id) as member_count
		FROM teams t
		WHERE t.disbanded_at IS NULL
		ORDER BY t.created_at DESC
		LIMIT 6
	`)
	if err == nil {
		defer teamRows.Close()
		for teamRows.Next() {
			var tm HomeTeamItem
			var logoID sql.NullInt64
			var isRecruit int
			var wanted sql.NullString
			var createdAt string
			if err := teamRows.Scan(&tm.ID, &tm.Name, &logoID, &isRecruit, &wanted, &createdAt, &tm.MemberCount); err == nil {
				if logoID.Valid {
					tm.LogoImageID = &logoID.Int64
				}
				tm.IsRecruiting = isRecruit == 1
				if wanted.Valid {
					tm.WantedRoles = wanted.String
				}
				if ct, err := db.ParseUTC(createdAt); err == nil {
					tm.CreatedAtMonth = ct.In(loc).Format("2006.01")
				}
				out.Teams = append(out.Teams, &tm)
			}
		}
	}

	return out, nil
}
