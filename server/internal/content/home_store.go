package content

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/agenda"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/media"
	"github.com/Uniseem/sjtu-ow/server/internal/scrims"
	"github.com/Uniseem/sjtu-ow/server/internal/tournaments"
)

// HomePage 聚合首屏与本人的安排；一个请求取同一份时钟。
func (s *Service) HomePage(ctx *app.Ctx) (*HomePageOut, error) {
	now := ctx.Now()
	out, err := s.store.GetHomePage(ctx.Context, now)
	if err != nil {
		return nil, err
	}
	if v := ctx.Viewer; v != nil && !v.Disabled && v.ID > 0 {
		out.Agenda, err = agenda.Items(ctx.Context, s.store.d.ReadPool(), v.ID, now, agenda.MaxItems)
		if err != nil {
			return nil, err
		}
	}
	return out, nil
}

func (s *Store) GetHomePage(ctx context.Context, now time.Time) (*HomePageOut, error) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		return nil, err
	}
	out := &HomePageOut{Stats: &HomeStatsOut{}, Scrims: []*HomeScrimItem{}, News: []*NewsItemOut{}, Notices: []*HomeNoticeItem{}, Teams: []*HomeTeamItem{}, Agenda: []agenda.Item{}}
	pool := s.d.ReadPool()
	err = pool.QueryRowContext(ctx, `SELECT (SELECT COUNT(*) FROM users WHERE is_active=1 AND email_verified_at IS NOT NULL),
 (SELECT COUNT(*) FROM teams WHERE disbanded_at IS NULL),(SELECT COUNT(*) FROM scrims WHERE status='finished')`).Scan(&out.Stats.MemberCount, &out.Stats.TeamCount, &out.Stats.ScrimsHeld)
	if err != nil {
		return nil, err
	}
	var founded, qq sql.NullString
	var hero sql.NullInt64
	err = pool.QueryRowContext(ctx, `SELECT founded_on,hero_image_id,qq_group_url FROM site_settings WHERE id=1`).Scan(&founded, &hero, &qq)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}
	out.Stats.FoundedOn = founded.String
	out.Stats.QQGroupURL = qq.String
	if hero.Valid {
		out.Stats.HeroImageID = &hero.Int64
	}
	out.Stats.Age, err = communityAge(founded.String, now, loc)
	if err != nil {
		return nil, err
	}
	covers, err := media.LoadPool(ctx, pool, "default_cover")
	if err != nil {
		return nil, err
	}
	candidates, err := tournaments.HomeCandidates(ctx, pool)
	if err != nil {
		return nil, err
	}
	if chosen := homeFeature(candidates, now); chosen != nil {
		var approved int
		if err := pool.QueryRowContext(ctx, `SELECT COUNT(*) FROM registrations WHERE tournament_id=? AND status='approved'`, chosen.ID).Scan(&approved); err != nil {
			return nil, err
		}
		out.FeatureTournament = featureOut(chosen, approved, now, loc, media.PickCover(covers, chosen.ID, 13))
	}
	out.Scrims, err = s.homeScrims(ctx, now, loc)
	if err != nil {
		return nil, err
	}
	articles, pins, err := s.homeNews(ctx)
	if err != nil {
		return nil, err
	}
	out.News, err = s.newsItems(ctx, articles, covers)
	if err != nil {
		return nil, err
	}
	for _, item := range out.News {
		item.Pinned = pins[item.ID]
	}
	out.Notices, err = s.homeNotices(ctx, loc)
	if err != nil {
		return nil, err
	}
	out.Teams, err = s.homeTeams(ctx, loc)
	if err != nil {
		return nil, err
	}
	return out, nil
}

func communityAge(raw string, now time.Time, loc *time.Location) (*HomeAge, error) {
	if raw == "" {
		return nil, nil
	}
	founded, err := time.Parse("2006-01-02", raw)
	if err != nil {
		founded, err = db.ParseUTC(raw)
		if err != nil {
			return nil, fmt.Errorf("社区成立日期: %w", err)
		}
		founded = founded.In(loc)
	}
	date := func(t time.Time) time.Time { return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, time.UTC) }
	today := date(now.In(loc))
	founded = date(founded)
	if founded.After(today) {
		return nil, nil
	}
	anniversary := func(year int) time.Time {
		day := min(founded.Day(), time.Date(year, founded.Month()+1, 0, 0, 0, 0, 0, time.UTC).Day())
		return time.Date(year, founded.Month(), day, 0, 0, 0, 0, time.UTC)
	}
	years := today.Year() - founded.Year()
	if anniversary(today.Year()).After(today) {
		years--
	}
	return &HomeAge{Years: years, Days: int(today.Sub(anniversary(founded.Year()+years)).Hours() / 24)}, nil
}

func homeFeature(candidates []*tournaments.Tournament, now time.Time) *tournaments.Tournament {
	var open, ahead, finished *tournaments.Tournament
	when := func(t *tournaments.Tournament) *time.Time {
		if t.StartsAt != nil {
			return t.StartsAt
		}
		return t.RegistrationOpensAt
	}
	earlier := func(a, b *time.Time) bool { return a != nil && (b == nil || a.Before(*b)) }
	for _, t := range candidates {
		switch t.Phase(now) {
		case "open":
			if open == nil || earlier(t.RegistrationClosesAt, open.RegistrationClosesAt) {
				open = t
			}
		case "upcoming", "closed":
			if ahead == nil || earlier(when(t), when(ahead)) {
				ahead = t
			}
		case "finished":
			if finished == nil {
				finished = t
			}
		}
	}
	if open != nil {
		return open
	}
	if ahead != nil {
		return ahead
	}
	return finished
}

func featureOut(t *tournaments.Tournament, approved int, now time.Time, loc *time.Location, cover *int64) *HomeFeatureTournament {
	phase := t.Phase(now)
	labels := map[string]string{"open": "报名中", "upcoming": "即将开始报名", "closed": "报名已截止", "finished": "已结束"}
	facts := "整队报名"
	if t.TakesIndividuals() {
		facts = "个人报名"
	}
	if phase == "open" && t.RegistrationClosesAt != nil {
		facts += " · 报名截止 " + t.RegistrationClosesAt.In(loc).Format("01.02 15:04")
	}
	if phase == "upcoming" && t.RegistrationOpensAt != nil {
		facts += " · " + t.RegistrationOpensAt.In(loc).Format("01.02 15:04") + " 开放报名"
	}
	if t.StartsAt != nil {
		if phase == "finished" {
			facts += " · " + t.StartsAt.In(loc).Format("2006.01.02")
		} else {
			facts += " · " + t.StartsAt.In(loc).Format("01.02") + " 比赛"
		}
	}
	if phase != "upcoming" {
		label := "已通过"
		if t.TakesIndividuals() {
			label = "已编成"
		}
		facts += fmt.Sprintf(" · %s %d 队", label, approved)
	}
	out := &HomeFeatureTournament{ID: t.ID, Title: t.Title, Phase: phase, PhaseLabel: labels[phase], RegistrationMode: t.RegistrationMode, TakesIndividuals: t.TakesIndividuals(), ApprovedTeams: approved, CoverImageID: t.CoverImageID, DefaultCoverImageID: cover, Facts: facts}
	if t.StartsAt != nil {
		out.StartsAt = db.FormatUTC(*t.StartsAt)
	}
	if t.RegistrationOpensAt != nil {
		out.RegistrationOpensAt = db.FormatUTC(*t.RegistrationOpensAt)
	}
	if t.RegistrationClosesAt != nil {
		out.RegistrationClosesAt = db.FormatUTC(*t.RegistrationClosesAt)
	}
	return out
}

func (s *Store) homeScrims(ctx context.Context, now time.Time, loc *time.Location) ([]*HomeScrimItem, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT s.id,s.title,s.starts_at,s.signup_closes_at,s.format,
 (SELECT COUNT(*) FROM scrim_signups g WHERE g.scrim_id=s.id) FROM scrims s
 WHERE s.status='published' AND julianday(s.starts_at)>=julianday(?) ORDER BY julianday(s.starts_at),s.id LIMIT 5`, db.FormatUTC(now))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []*HomeScrimItem{}
	weekdays := []string{"周日", "周一", "周二", "周三", "周四", "周五", "周六"}
	for rows.Next() {
		var item HomeScrimItem
		var raw string
		var close sql.NullString
		var sc scrims.Scrim
		if err := rows.Scan(&item.ID, &item.Title, &raw, &close, &sc.Format, &item.Count); err != nil {
			return nil, err
		}
		starts, err := db.ParseUTC(raw)
		if err != nil {
			return nil, err
		}
		sc.StartsAt = &starts
		sc.Status = scrims.StatusPublished
		if close.Valid && close.String != "" {
			end, err := db.ParseUTC(close.String)
			if err != nil {
				return nil, err
			}
			sc.SignupClosesAt = &end
		}
		local := starts.In(loc)
		item.StartsAt = db.FormatUTC(starts)
		item.Month = int(local.Month())
		item.Day = local.Day()
		item.Weekday = weekdays[local.Weekday()]
		item.Time = local.Format("15:04")
		item.Capacity = sc.PlayersNeeded()
		item.SignupOpen = sc.SignupOpen(now)
		out = append(out, &item)
	}
	return out, rows.Err()
}

func (s *Store) homeNews(ctx context.Context) ([]*Article, map[int64]bool, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT `+articleColumns+`,hp.article_page_id FROM pages p JOIN articles a ON a.page_id=p.id
 LEFT JOIN article_categories c ON c.id=a.category_id LEFT JOIN users u ON u.id=a.author_id LEFT JOIN (SELECT hp.article_page_id,hp.sort_order FROM home_pins hp JOIN pages pp ON pp.id=hp.article_page_id WHERE pp.live=1 AND pp.search_public=1 ORDER BY hp.sort_order LIMIT 3) hp ON hp.article_page_id=p.id
 WHERE p.live=1 AND p.search_public=1 ORDER BY CASE WHEN hp.article_page_id IS NULL THEN 1 ELSE 0 END,hp.sort_order,
 `+utcTimeOrder("p.first_published_at")+` DESC,`+utcTimeOrder("p.last_published_at")+` DESC,p.id ASC LIMIT 4`)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	out := []*Article{}
	pins := map[int64]bool{}
	for rows.Next() {
		var pin sql.NullInt64
		item, err := scanArticleWithPin(rows, &pin)
		if err != nil {
			return nil, nil, err
		}
		out = append(out, item)
		pins[item.ID] = pin.Valid
	}
	return out, pins, rows.Err()
}

// scanArticleWithPin 复用实体扫描，不复制长字段表。
type extraScan struct {
	row  interface{ Scan(...any) error }
	tail any
}

func (r extraScan) Scan(args ...any) error { return r.row.Scan(append(args, r.tail)...) }
func scanArticleWithPin(row interface{ Scan(...any) error }, pin *sql.NullInt64) (*Article, error) {
	return scanArticle(extraScan{row, pin})
}

func (s *Store) homeNotices(ctx context.Context, loc *time.Location) ([]*HomeNoticeItem, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT p.id,p.slug,p.title,p.first_published_at FROM pages p JOIN articles a ON a.page_id=p.id JOIN article_categories c ON c.id=a.category_id
 WHERE p.live=1 AND p.search_public=1 AND c.slug IN ('notice','event-notice') ORDER BY `+utcTimeOrder("p.first_published_at")+` DESC,`+utcTimeOrder("p.last_published_at")+` DESC,p.id ASC LIMIT 5`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []*HomeNoticeItem{}
	for rows.Next() {
		var item HomeNoticeItem
		var at sql.NullString
		if err := rows.Scan(&item.ID, &item.Slug, &item.Title, &at); err != nil {
			return nil, err
		}
		if at.Valid && at.String != "" {
			t, err := db.ParseUTC(at.String)
			if err != nil {
				return nil, err
			}
			item.PublishedAtRaw = db.FormatUTC(t)
			t = t.In(loc)
			item.Month = int(t.Month())
			item.Day = t.Day()
		}
		out = append(out, &item)
	}
	return out, rows.Err()
}

func (s *Store) homeTeams(ctx context.Context, loc *time.Location) ([]*HomeTeamItem, error) {
	rows, err := s.d.ReadPool().QueryContext(ctx, `SELECT t.id,t.name,t.logo_image_id,t.is_recruiting,t.recruiting_roles,t.created_at,
 (SELECT COUNT(*) FROM team_memberships m WHERE m.team_id=t.id) FROM teams t WHERE t.disbanded_at IS NULL ORDER BY t.created_at DESC,t.id ASC LIMIT 6`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []*HomeTeamItem{}
	for rows.Next() {
		var item HomeTeamItem
		var active int
		var at string
		if err := rows.Scan(&item.ID, &item.Name, &item.LogoImageID, &active, &item.WantedRoles, &at, &item.MemberCount); err != nil {
			return nil, err
		}
		t, err := db.ParseUTC(at)
		if err != nil {
			return nil, err
		}
		item.IsRecruiting = active == 1
		item.CreatedAtMonth = t.In(loc).Format("2006.01")
		out = append(out, &item)
	}
	return out, rows.Err()
}
