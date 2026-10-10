// Package agenda 是「我的安排」和「订阅到手机日历」（设计 5.2、13.5）：
// 一个人报了名、还没发生的内战和赛事，按时间排。日历订阅是同一份数据的 iCalendar 形式，
// 地址里带签名，不用登录（规则 216 限流）。
package agenda

import (
	"context"
	"database/sql"
	"net/http"
	"sort"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/djsign"
	"github.com/Uniseem/sjtu-ow/server/internal/scrims"
)

// MaxItems 首页「我的安排」最多几条（设计 5.2）。
const MaxItems = 4

// ScrimGrace 内战开始后还在安排里多久（它开始 6 小时后自动结束，设计 9.1）。
const ScrimGrace = 6 * time.Hour

// CalendarSalt 和现行站一样，已经订阅出去的地址换栈后照样能用。
const CalendarSalt = "sjtu-ow.calendar"

var statusLabels = map[string]string{"pending": "待审核", "approved": "已通过", "rejected": "已驳回", "withdrawn": "已撤回"}

// Item 是一条安排。
type Item struct {
	Kind  string     `json:"kind"` // 内战 / 赛事
	Title string     `json:"title"`
	URL   string     `json:"url"`
	When  *time.Time `json:"when"`
	Note  string     `json:"note"`
}

// Service 是安排的服务。
type Service struct {
	d          *db.DB
	siteURL    string
	signingKey string
	// clock 是日历订阅（没有请求上下文里的时钟）取「现在」用的；测试里换成固定时钟。
	clock clock.Clock
}

// NewService 造安排服务。
func NewService(d *db.DB, siteURL, signingKey string) *Service {
	return &Service{d: d, siteURL: strings.TrimRight(siteURL, "/"), signingKey: signingKey, clock: clock.System{}}
}

// WithClock 换掉日历订阅取「现在」的时钟（测试用）。
func (s *Service) WithClock(c clock.Clock) *Service {
	s.clock = c
	return s
}

// Items 一个人的安排，有时间的按时间、没时间的排后面。limit<=0 不限条数。
func Items(ctx context.Context, q db.DBTX, userID int64, now time.Time, limit int) ([]Item, error) {
	var items []Item

	// 内战：已发布，开始时间不早于「现在 - 6 小时」（正在打的还留着）。
	rows, err := q.QueryContext(ctx, `SELECT sc.id, sc.title, sc.format, sc.starts_at, g.team, g.assigned_role, g.is_selected
		FROM scrim_signups g JOIN scrims sc ON sc.id = g.scrim_id
		WHERE g.user_id = ? AND sc.status = 'published' AND sc.starts_at >= ?`,
		userID, db.FormatUTC(now.Add(-ScrimGrace)))
	if err != nil {
		return nil, err
	}
	type scrimRow struct {
		sc *scrims.Scrim
		g  *scrims.Signup
	}
	var mine []scrimRow
	for rows.Next() {
		var sc scrims.Scrim
		var g scrims.Signup
		var starts sql.NullString
		var selected int
		if err := rows.Scan(&sc.ID, &sc.Title, &sc.Format, &starts, &g.Team, &g.AssignedRole, &selected); err != nil {
			_ = rows.Close()
			return nil, err
		}
		g.IsSelected = selected == 1
		if starts.Valid {
			t, _ := db.ParseUTC(starts.String)
			sc.StartsAt = &t
		}
		mine = append(mine, scrimRow{&sc, &g})
	}
	err = rows.Err()
	_ = rows.Close()
	if err != nil {
		return nil, err
	}
	for _, m := range mine {
		var n int
		if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM scrim_signups WHERE scrim_id = ? AND team <> ''`, m.sc.ID).Scan(&n); err != nil {
			return nil, err
		}
		note := scrims.PlacementText(m.sc, m.g, n > 0)
		if note == "" {
			note = "已报名"
		}
		items = append(items, Item{Kind: "内战", Title: m.sc.Title, URL: "/scrims/" + itoa(m.sc.ID) + "/", When: m.sc.StartsAt, Note: note})
	}

	// 赛事：在有效名单上的，和还在散人池里的。
	trs, err := q.QueryContext(ctx, `SELECT t.id, t.title, t.starts_at, r.id, r.team_name, r.status
		FROM registration_members m
		JOIN registrations r ON r.id = m.registration_id
		JOIN tournaments t ON t.id = m.tournament_id
		WHERE m.user_id = ? AND m.is_active = 1 AND t.status = 'published'`, userID)
	if err != nil {
		return nil, err
	}
	for trs.Next() {
		var tid, rid int64
		var title, team, status string
		var starts sql.NullString
		if err := trs.Scan(&tid, &title, &starts, &rid, &team, &status); err != nil {
			_ = trs.Close()
			return nil, err
		}
		when := parseNull(starts)
		if when != nil && when.Before(now) {
			continue
		}
		items = append(items, Item{Kind: "赛事", Title: title, URL: "/tournaments/" + itoa(tid) + "/registrations/" + itoa(rid) + "/", When: when,
			Note: team + " · " + statusLabels[status]})
	}
	err = trs.Err()
	_ = trs.Close()
	if err != nil {
		return nil, err
	}
	ps, err := q.QueryContext(ctx, `SELECT t.id, t.title, t.starts_at
		FROM individual_signups s JOIN tournaments t ON t.id = s.tournament_id
		WHERE s.user_id = ? AND s.registration_id IS NULL AND t.status = 'published'`, userID)
	if err != nil {
		return nil, err
	}
	for ps.Next() {
		var tid int64
		var title string
		var starts sql.NullString
		if err := ps.Scan(&tid, &title, &starts); err != nil {
			_ = ps.Close()
			return nil, err
		}
		when := parseNull(starts)
		if when != nil && when.Before(now) {
			continue
		}
		items = append(items, Item{Kind: "赛事", Title: title, URL: "/tournaments/" + itoa(tid) + "/", When: when, Note: "等待编队"})
	}
	err = ps.Err()
	_ = ps.Close()
	if err != nil {
		return nil, err
	}

	sort.SliceStable(items, func(i, j int) bool {
		a, b := items[i].When, items[j].When
		switch {
		case a == nil && b == nil:
			return false
		case a == nil:
			return false
		case b == nil:
			return true
		}
		return a.Before(*b)
	})
	if limit > 0 && len(items) > limit {
		items = items[:limit]
	}
	if items == nil {
		items = []Item{}
	}
	return items, nil
}

func parseNull(s sql.NullString) *time.Time {
	if !s.Valid || s.String == "" {
		return nil
	}
	t, err := db.ParseUTC(s.String)
	if err != nil {
		return nil
	}
	return &t
}

func itoa(n int64) string {
	if n == 0 {
		return "0"
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}

// Mine 是首页「我的安排」（登录的人才有）。
func (s *Service) Mine(ctx *app.Ctx) ([]Item, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled || v.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	return Items(ctx.Context, s.d.ReadPool(), v.ID, ctx.Now(), MaxItems)
}

// --- 日历订阅地址 -------------------------------------------------------

// Token 是某人的订阅令牌：只有编号，或「换过一次地址」之后 [编号, 版本]（设计 13.5，v7.20）。
func (s *Service) Token(userID, version int64) string {
	var payload any = userID
	if version > 0 {
		payload = []int64{userID, version}
	}
	t, err := djsign.SignObject(s.signingKey, CalendarSalt, payload)
	if err != nil {
		return ""
	}
	return t
}

// userFor 令牌是谁。被篡改、账号停用、地址已被「换一个」作废都当没有。
func (s *Service) userFor(ctx context.Context, q db.DBTX, raw string) (id int64, nickname string, ok bool) {
	var payload any
	if err := djsign.UnsignObject(s.signingKey, CalendarSalt, raw, &payload); err != nil {
		// 195 轮之前发出去的地址是带时间戳的，照样认。
		if err2 := djsign.Loads(s.signingKey, CalendarSalt, raw, &payload); err2 != nil {
			return 0, "", false
		}
	}
	var pk, version int64
	switch p := payload.(type) {
	case float64:
		pk = int64(p)
	case []any:
		if len(p) != 2 {
			return 0, "", false
		}
		a, ok1 := p[0].(float64)
		b, ok2 := p[1].(float64)
		if !ok1 || !ok2 {
			return 0, "", false
		}
		pk, version = int64(a), int64(b)
	default:
		return 0, "", false
	}
	if pk <= 0 {
		return 0, "", false
	}
	err := q.QueryRowContext(ctx, `SELECT nickname FROM users WHERE id = ? AND is_active = 1 AND calendar_version = ?`, pk, version).Scan(&nickname)
	if err != nil {
		return 0, "", false
	}
	return pk, nickname, true
}

// Address 是我的订阅地址（页面显示和复制用）。
type Address struct {
	URL    string `json:"url"`
	Webcal string `json:"webcal"`
}

func (s *Service) address(userID, version int64) Address {
	u := s.siteURL + "/calendar/" + s.Token(userID, version) + ".ics"
	web := u
	if i := strings.Index(u, "://"); i >= 0 {
		web = "webcal://" + u[i+3:]
	}
	return Address{URL: u, Webcal: web}
}

// MyAddress 我的订阅地址。
func (s *Service) MyAddress(ctx *app.Ctx) (*Address, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled || v.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	var version int64
	if err := s.d.ReadPool().QueryRowContext(ctx.Context, `SELECT calendar_version FROM users WHERE id = ?`, v.ID).Scan(&version); err != nil {
		return nil, err
	}
	a := s.address(v.ID, version)
	return &a, nil
}

// Renew 「换一个订阅地址」：旧地址作废（地址泄露了可以收回，210 复核）。
func (s *Service) Renew(ctx *app.Ctx) (*Address, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled || v.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	var version int64
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		return tx.QueryRowContext(txCtx, `UPDATE users SET calendar_version = calendar_version + 1 WHERE id = ? RETURNING calendar_version`, v.ID).Scan(&version)
	})
	if err != nil {
		return nil, err
	}
	a := s.address(v.ID, version)
	return &a, nil
}

// Serve 是 GET /calendar/{token}.ics：不用登录，签名就是凭证。
func (s *Service) Serve(w http.ResponseWriter, r *http.Request) {
	raw := strings.TrimSuffix(r.PathValue("file"), ".ics")
	if raw == r.PathValue("file") {
		http.NotFound(w, r)
		return
	}
	id, nickname, ok := s.userFor(r.Context(), s.d.ReadPool(), raw)
	if !ok {
		http.NotFound(w, r)
		return
	}
	now := s.clock.Now().UTC()
	items, err := Items(r.Context(), s.d.ReadPool(), id, now, 0)
	if err != nil {
		http.Error(w, "服务器开小差了，稍后再试", http.StatusInternalServerError)
		return
	}
	body := s.ICS(nickname, items, now)
	w.Header().Set("Content-Type", "text/calendar; charset=utf-8")
	w.Header().Set("Cache-Control", "private, max-age=900")
	w.Header().Set("X-Robots-Tag", "noindex")
	_, _ = w.Write([]byte(body))
}
