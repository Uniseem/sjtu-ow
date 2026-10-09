package scrims

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Card 是列表里的一场内战。
type Card struct {
	ID             int64      `json:"id"`
	Title          string     `json:"title"`
	StartsAt       *time.Time `json:"starts_at"`
	SignupDeadline *time.Time `json:"signup_deadline"`
	Format         string     `json:"format"`
	FormatLabel    string     `json:"format_label"`
	SjtuOnly       bool       `json:"sjtu_only"`
	Status         string     `json:"status"`
	SignupOpen     bool       `json:"signup_open"`
	SignupTotal    int        `json:"signup_total"`
	PlayersNeeded  int        `json:"players_needed"`
}

func cardOf(sc *Scrim, total int, now time.Time) Card {
	return Card{ID: sc.ID, Title: sc.Title, StartsAt: sc.StartsAt, SignupDeadline: sc.Deadline(), Format: sc.Format,
		FormatLabel: FormatLabels[sc.Format], SjtuOnly: sc.SjtuOnly, Status: sc.Status, SignupOpen: sc.SignupOpen(now),
		SignupTotal: total, PlayersNeeded: sc.PlayersNeeded()}
}

func signupTotals(ctx context.Context, q db.DBTX) (map[int64]int, error) {
	rows, err := q.QueryContext(ctx, `SELECT scrim_id, COUNT(*) FROM scrim_signups GROUP BY scrim_id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[int64]int{}
	for rows.Next() {
		var id int64
		var n int
		if err := rows.Scan(&id, &n); err != nil {
			return nil, err
		}
		out[id] = n
	}
	return out, rows.Err()
}

func loadScrims(ctx context.Context, q db.DBTX, where string, args ...any) ([]*Scrim, error) {
	rows, err := q.QueryContext(ctx, `SELECT `+scrimCols+` FROM scrims `+where, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []*Scrim
	for rows.Next() {
		sc, err := scanScrim(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, sc)
	}
	return out, rows.Err()
}

// List 公开列表（规则 149）：已发布的，加上 30 天内结束的；已取消的离开列表（详情页还在）；草稿没有。
func (s *Service) List(ctx context.Context, now time.Time) ([]Card, error) {
	rd := s.d.ReadPool()
	cutoff := db.FormatUTC(now.Add(-FinishedVisibleDays * 24 * time.Hour))
	list, err := loadScrims(ctx, rd, `WHERE status = 'published' OR (status = 'finished' AND starts_at >= ?) ORDER BY starts_at, id`, cutoff)
	if err != nil {
		return nil, err
	}
	totals, err := signupTotals(ctx, rd)
	if err != nil {
		return nil, err
	}
	out := make([]Card, 0, len(list))
	for _, sc := range list {
		out = append(out, cardOf(sc, totals[sc.ID], now))
	}
	return out, nil
}

// PublicSignup 是详情页上公开的名单一行：昵称和能打的位置，不带游戏 ID 和分队。
type PublicSignup struct {
	Nickname string   `json:"nickname"`
	Roles    []string `json:"roles"`
}

// MySignup 是登录的人自己的报名和去向（规则 166：只给本人，公开页面没有任何分队）。
type MySignup struct {
	ID            int64    `json:"id"`
	GameAccountID *int64   `json:"game_account_id"`
	Roles         []string `json:"roles"`
	Placement     string   `json:"placement"`
	CanCancel     bool     `json:"can_cancel"`
}

// Counts 是详情页上的人数。
type Counts struct {
	Total   int `json:"total"`
	Tank    int `json:"tank"`
	Damage  int `json:"damage"`
	Support int `json:"support"`
}

// Page 是内战详情页要的全部。
type Page struct {
	Scrim    *Scrim         `json:"scrim"`
	Card     Card           `json:"card"`
	Counts   Counts         `json:"counts"`
	Signups  []PublicSignup `json:"signups"`
	Mine     *MySignup      `json:"mine"`
	Problems []string       `json:"problems"`
}

// Detail 详情（公开；草稿是 404，不泄露存在，规则 148）。
func (s *Service) Detail(ctx *app.Ctx, id int64) (*Page, error) {
	rd := s.d.ReadPool()
	sc, err := GetScrim(ctx.Context, rd, id)
	if err != nil {
		return nil, err
	}
	if sc == nil || !sc.IsPublic() {
		return nil, api.NotFound("内战不存在")
	}
	now := ctx.Now().UTC()
	rows, err := listSignups(ctx.Context, rd, id)
	if err != nil {
		return nil, err
	}
	p := &Page{Scrim: sc, Signups: []PublicSignup{}, Problems: []string{}}
	hasSplit := false
	for _, g := range rows {
		p.Counts.Total++
		if g.RoleTank {
			p.Counts.Tank++
		}
		if g.RoleDamage {
			p.Counts.Damage++
		}
		if g.RoleSupport {
			p.Counts.Support++
		}
		if g.Team != "" {
			hasSplit = true
		}
		var nick string
		if err := rd.QueryRowContext(ctx.Context, `SELECT nickname FROM users WHERE id = ?`, g.UserID).Scan(&nick); err != nil {
			return nil, err
		}
		p.Signups = append(p.Signups, PublicSignup{Nickname: nick, Roles: g.Roles()})
	}
	p.Card = cardOf(sc, p.Counts.Total, now)
	v := ctx.Viewer
	if v != nil && !v.Disabled && v.ID > 0 {
		var mine *Signup
		for _, g := range rows {
			if g.UserID == v.ID {
				mine = g
			}
		}
		if mine != nil {
			d := sc.Deadline()
			p.Mine = &MySignup{ID: mine.ID, GameAccountID: mine.GameAccountID, Roles: mine.Roles(),
				Placement: PlacementText(sc, mine, hasSplit), CanCancel: d != nil && !now.After(*d)}
		} else {
			if p.Problems, err = s.signupProblems(ctx.Context, rd, sc, v.ID, now); err != nil {
				return nil, err
			}
		}
	}
	return p, nil
}

// AdminRow 是后台内战列表的一行。
type AdminRow struct {
	Card
	Missing   []string `json:"missing"`
	CanDelete bool     `json:"can_delete"`
	Stale     bool     `json:"teams_stale"`
}

// AdminList 后台列表（含草稿和已取消的）。
func (s *Service) AdminList(ctx *app.Ctx) ([]AdminRow, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	rd := s.d.ReadPool()
	list, err := loadScrims(ctx.Context, rd, `ORDER BY starts_at IS NULL DESC, starts_at DESC, id DESC`)
	if err != nil {
		return nil, err
	}
	totals, err := signupTotals(ctx.Context, rd)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	out := make([]AdminRow, 0, len(list))
	for _, sc := range list {
		miss := Missing(sc)
		if miss == nil {
			miss = []string{}
		}
		out = append(out, AdminRow{Card: cardOf(sc, totals[sc.ID], now), Missing: miss,
			CanDelete: sc.Status == StatusDraft && totals[sc.ID] == 0, Stale: teamsStale(sc)})
	}
	return out, nil
}

// AdminGet 后台读一场内战（含草稿）。
func (s *Service) AdminGet(ctx *app.Ctx, id int64) (*AdminRow, *Scrim, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, nil, err
	}
	rd := s.d.ReadPool()
	sc, err := GetScrim(ctx.Context, rd, id)
	if err != nil {
		return nil, nil, err
	}
	if sc == nil {
		return nil, nil, api.NotFound("内战不存在")
	}
	totals, err := signupTotals(ctx.Context, rd)
	if err != nil {
		return nil, nil, err
	}
	miss := Missing(sc)
	if miss == nil {
		miss = []string{}
	}
	row := &AdminRow{Card: cardOf(sc, totals[sc.ID], ctx.Now().UTC()), Missing: miss,
		CanDelete: sc.Status == StatusDraft && totals[sc.ID] == 0, Stale: teamsStale(sc)}
	return row, sc, nil
}
