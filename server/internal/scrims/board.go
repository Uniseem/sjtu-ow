package scrims

import (
	"context"
	"fmt"
	"math/rand"
	"sort"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// BoardSignup 是分队板上的一个报名。
type BoardSignup struct {
	SignupID     int64             `json:"signup_id"`
	UserID       int64             `json:"user_id"`
	Nickname     string            `json:"nickname"`
	Battletag    string            `json:"battletag"`
	Roles        []string          `json:"roles"`
	Ratings      map[string]int    `json:"ratings"` // 位置 → 分数，只有填了段位的位置
	RankText     map[string]string `json:"rank_text"`
	BestRating   *int              `json:"best_rating"`
	IsSelected   bool              `json:"is_selected"`
	Team         string            `json:"team"`
	AssignedRole string            `json:"assigned_role"`
	RatingUsed   *int              `json:"rating_used"`
	Contacts     []string          `json:"contacts,omitempty"`
	CreatedAt    time.Time         `json:"created_at"`
}

// BoardTeam 是一队：总分、位置人数不符的提示、成员。
type BoardTeam struct {
	Team     string        `json:"team"`
	Label    string        `json:"label"`
	Total    int           `json:"total"`
	Problems []string      `json:"problems"`
	Members  []BoardSignup `json:"members"`
}

// Board 是分队页要的全部。
type Board struct {
	Scrim         *Scrim        `json:"scrim"`
	Order         string        `json:"order"`
	Signups       []BoardSignup `json:"signups"`
	SelectedCount int           `json:"selected_count"`
	Needed        int           `json:"needed"`
	Teams         []BoardTeam   `json:"teams"`
	Bench         []BoardSignup `json:"bench"`
	Gap           int           `json:"gap"`
	HasTeams      bool          `json:"has_teams"`
	TeamsStale    bool          `json:"teams_stale"`
	CopyText      string        `json:"copy_text"`
	BoardVersion  int64         `json:"board_version"`
	Warnings      []string      `json:"warnings,omitempty"`
}

type signupRow struct {
	*Signup
	nickname string
	acct     *Account
}

func (r signupRow) rating(role string) *int { return r.acct.Rank(role) }

func (r signupRow) best() *int {
	var best *int
	for _, role := range r.Roles() {
		if v := r.rating(role); v != nil && (best == nil || *v > *best) {
			best = v
		}
	}
	return best
}

func loadRows(ctx context.Context, q db.DBTX, scrimID int64) ([]signupRow, error) {
	list, err := listSignups(ctx, q, scrimID)
	if err != nil {
		return nil, err
	}
	out := make([]signupRow, 0, len(list))
	for _, g := range list {
		r := signupRow{Signup: g}
		if err := q.QueryRowContext(ctx, `SELECT nickname FROM users WHERE id = ?`, g.UserID).Scan(&r.nickname); err != nil {
			return nil, err
		}
		if g.GameAccountID != nil {
			if r.acct, err = getAccount(ctx, q, *g.GameAccountID); err != nil {
				return nil, err
			}
		}
		out = append(out, r)
	}
	return out, nil
}

const deletedID = "（游戏 ID 已删除）"

func (r signupRow) battletag() string {
	if r.acct == nil {
		return deletedID
	}
	return r.acct.Battletag
}

func (r signupRow) view() BoardSignup {
	v := BoardSignup{SignupID: r.ID, UserID: r.UserID, Nickname: r.nickname, Battletag: r.battletag(), Roles: r.Roles(),
		Ratings: map[string]int{}, RankText: map[string]string{}, BestRating: r.best(), IsSelected: r.IsSelected,
		Team: r.Team, AssignedRole: r.AssignedRole, RatingUsed: r.RatingUsed, CreatedAt: r.CreatedAt}
	for _, role := range r.Roles() {
		if p := r.rating(role); p != nil {
			v.Ratings[role] = *p
			v.RankText[role] = accounts.FormatRank(p)
		} else {
			v.RankText[role] = "未填段位"
		}
	}
	return v
}

func roleCounts(rows []signupRow) map[string]int {
	c := map[string]int{Tank: 0, Damage: 0, Support: 0}
	for _, r := range rows {
		if _, ok := c[r.AssignedRole]; ok {
			c[r.AssignedRole]++
		}
	}
	return c
}

// requirementProblems 分出来的队不符合规格要求时提示，但仍允许保存（规则 164）。
func requirementProblems(sc *Scrim, rows []signupRow) []string {
	if !sc.RoleQueue() {
		return []string{}
	}
	counts := roleCounts(rows)
	out := []string{}
	for _, role := range RoleOrder {
		if need := Requirements(sc.Format)[role]; counts[role] != need {
			out = append(out, fmt.Sprintf("%s %d 人（需要 %d 人）", RoleLabels[role], counts[role], need))
		}
	}
	return out
}

func teamTotal(rows []signupRow) int {
	t := 0
	for _, r := range rows {
		if r.RatingUsed != nil {
			t += *r.RatingUsed
		}
	}
	return t
}

func roleOrderIndex(role string) int {
	for i, r := range RoleOrder {
		if r == role {
			return i
		}
	}
	return 3
}

// teamRows 两队的成员，按位置顺序再按报名编号。
func teamRows(rows []signupRow) map[string][]signupRow {
	out := map[string][]signupRow{"a": nil, "b": nil}
	for _, r := range rows {
		if r.Team == "a" || r.Team == "b" {
			out[r.Team] = append(out[r.Team], r)
		}
	}
	for _, side := range out {
		sort.SliceStable(side, func(i, j int) bool {
			oi, oj := roleOrderIndex(side[i].AssignedRole), roleOrderIndex(side[j].AssignedRole)
			if oi != oj {
				return oi < oj
			}
			return side[i].ID < side[j].ID
		})
	}
	return out
}

// copyText 复制到 QQ 群的文案（规则 170）：按队、按位置分组列「昵称 游戏ID 段位」和每队总分。
func copyText(sc *Scrim, rows []signupRow) string {
	by := teamRows(rows)
	when := "时间未定"
	if sc.StartsAt != nil {
		when = moment(*sc.StartsAt)
	}
	lines := []string{fmt.Sprintf("【%s】%s · %s", sc.Title, when, FormatLabels[sc.Format])}
	for _, t := range []struct{ key, name string }{{"a", "A 队"}, {"b", "B 队"}} {
		side := by[t.key]
		lines = append(lines, "", fmt.Sprintf("%s（总分 %d）", t.name, teamTotal(side)))
		if sc.RoleQueue() {
			for _, role := range RoleOrder {
				var entries []string
				for _, r := range side {
					if r.AssignedRole == role {
						entries = append(entries, fmt.Sprintf("%s %s %s", r.nickname, r.battletag(), accounts.FormatRank(r.RatingUsed)))
					}
				}
				if len(entries) > 0 {
					lines = append(lines, RoleLabels[role]+"："+strings.Join(entries, " / "))
				}
			}
		} else {
			for _, r := range side {
				lines = append(lines, fmt.Sprintf("%s %s %s", r.nickname, r.battletag(), accounts.FormatRank(r.RatingUsed)))
			}
		}
	}
	return strings.Join(lines, "\n")
}

func teamsStale(sc *Scrim) bool {
	return sc.TeamsGeneratedAt != nil && sc.RosterChangedAt != nil && sc.RosterChangedAt.After(*sc.TeamsGeneratedAt)
}

func (s *Service) loadContacts(ctx context.Context, q db.DBTX, rows []signupRow) (map[int64][]string, error) {
	labels := map[string]string{"qq": "QQ", "wechat": "微信", "phone": "手机号", "other": "其他"}
	out := map[int64][]string{}
	for _, r := range rows {
		cr, err := q.QueryContext(ctx, `SELECT type, value FROM contacts WHERE user_id = ? ORDER BY id`, r.UserID)
		if err != nil {
			return nil, err
		}
		for cr.Next() {
			var t, v string
			if err := cr.Scan(&t, &v); err != nil {
				cr.Close()
				return nil, err
			}
			out[r.UserID] = append(out[r.UserID], labels[t]+" "+v)
		}
		cr.Close()
	}
	return out, nil
}

// GetBoard 分队页：全部报名（可按报名时间或段位排）、两队、替补、总分差、过期标记、复制文案。
func (s *Service) GetBoard(ctx *app.Ctx, scrimID int64, order string) (*Board, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	return s.buildBoard(ctx.Context, s.d.ReadPool(), scrimID, order, v.HasCap(accounts.CapContactsView))
}

func (s *Service) buildBoard(ctx context.Context, q db.DBTX, scrimID int64, order string, withContacts bool) (*Board, error) {
	sc, err := GetScrim(ctx, q, scrimID)
	if err != nil {
		return nil, err
	}
	if sc == nil {
		return nil, api.NotFound("内战不存在")
	}
	rows, err := loadRows(ctx, q, scrimID)
	if err != nil {
		return nil, err
	}
	if order != "rating" {
		order = "created"
	}
	display := append([]signupRow(nil), rows...)
	if order == "rating" {
		sort.SliceStable(display, func(i, j int) bool {
			bi, bj := 0, 0
			if b := display[i].best(); b != nil {
				bi = *b
			}
			if b := display[j].best(); b != nil {
				bj = *b
			}
			if bi != bj {
				return bi > bj
			}
			return display[i].CreatedAt.Before(display[j].CreatedAt)
		})
	}
	var contacts map[int64][]string
	if withContacts {
		if contacts, err = s.loadContacts(ctx, q, rows); err != nil {
			return nil, err
		}
	}
	decorate := func(r signupRow) BoardSignup {
		bs := r.view()
		if withContacts {
			bs.Contacts = contacts[r.UserID]
		}
		return bs
	}
	b := &Board{Scrim: sc, Order: order, Needed: sc.PlayersNeeded(), BoardVersion: sc.BoardVersion, Signups: []BoardSignup{},
		Bench: []BoardSignup{}, Teams: []BoardTeam{}}
	for _, r := range display {
		b.Signups = append(b.Signups, decorate(r))
		if r.IsSelected {
			b.SelectedCount++
		}
		if r.Team == "" && r.IsSelected {
			b.Bench = append(b.Bench, decorate(r))
		}
	}
	by := teamRows(rows)
	totals := map[string]int{}
	for _, t := range []struct{ key, label string }{{"a", "A 队"}, {"b", "B 队"}} {
		side := by[t.key]
		bt := BoardTeam{Team: t.key, Label: t.label, Total: teamTotal(side), Problems: requirementProblems(sc, side), Members: []BoardSignup{}}
		for _, r := range side {
			bt.Members = append(bt.Members, decorate(r))
		}
		totals[t.key] = bt.Total
		b.Teams = append(b.Teams, bt)
	}
	b.Gap = abs(totals["a"] - totals["b"])
	b.HasTeams = len(by["a"]) > 0 || len(by["b"]) > 0
	b.TeamsStale = teamsStale(sc)
	if b.HasTeams {
		b.CopyText = copyText(sc, rows)
	}
	return b, nil
}

func checkBoardVersion(sc *Scrim, base int64) error {
	if base != sc.BoardVersion {
		return api.NewErr(409, "stale", "分队板刚被改过，已换成最新内容")
	}
	return nil
}

func setSelection(ctx context.Context, tx *db.Tx, scrimID int64, ids []int64, now time.Time) error {
	want := map[int64]bool{}
	for _, id := range ids {
		want[id] = true
	}
	list, err := listSignups(ctx, tx, scrimID)
	if err != nil {
		return err
	}
	for _, g := range list {
		should := want[g.ID]
		if g.IsSelected == should {
			continue
		}
		if should {
			_, err = tx.ExecContext(ctx, `UPDATE scrim_signups SET is_selected = 1, updated_at = ? WHERE id = ?`, db.FormatUTC(now), g.ID)
		} else {
			_, err = tx.ExecContext(ctx, `UPDATE scrim_signups SET is_selected = 0, team = '', assigned_role = '', rating_used = NULL, updated_at = ? WHERE id = ?`, db.FormatUTC(now), g.ID)
		}
		if err != nil {
			return err
		}
	}
	return nil
}

func bumpBoard(ctx context.Context, tx *db.Tx, scrimID int64) error {
	_, err := tx.ExecContext(ctx, `UPDATE scrims SET board_version = board_version + 1 WHERE id = ?`, scrimID)
	return err
}

// SetSelection 勾出今晚真正来的人（规则 165 的前置）；取消勾选的人同时清掉分队结果。
func (s *Service) SetSelection(ctx *app.Ctx, scrimID int64, ids []int64, baseBoardVersion int64) (*Board, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		sc, err := GetScrim(txCtx, tx, scrimID)
		if err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		if err := checkBoardVersion(sc, baseBoardVersion); err != nil {
			return err
		}
		if err := setSelection(txCtx, tx, scrimID, ids, now); err != nil {
			return err
		}
		return bumpBoard(txCtx, tx, scrimID)
	})
	if err != nil {
		return nil, err
	}
	return s.buildBoard(ctx.Context, s.d.ReadPool(), scrimID, "", v.HasCap(accounts.CapContactsView))
}

func (s *Service) players(rows []signupRow) []Player {
	out := make([]Player, 0, len(rows))
	for _, r := range rows {
		p := Player{SignupID: r.ID, Nickname: r.nickname, Roles: r.Roles(), Ratings: map[string]int{}}
		if r.acct != nil {
			p.Battletag = r.acct.Battletag
		}
		for _, role := range r.Roles() {
			if v := r.rating(role); v != nil {
				p.Ratings[role] = *v
			}
		}
		if b := r.best(); b != nil {
			p.Best = *b
		}
		out = append(out, p)
	}
	return out
}

// GenerateResult 是生成分队的结果。
type GenerateResult struct {
	Board   *Board   `json:"board"`
	Score   [2]int   `json:"score"`
	Unrated []string `json:"unrated"`
}

// Generate 勾选 → 生成 → 保存（规则 159–163、165）。勾选先落库；生成失败时勾选保留，错误说明原因。
func (s *Service) Generate(ctx *app.Ctx, scrimID int64, ids []int64, baseBoardVersion int64) (*GenerateResult, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	var sc *Scrim
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		var err error
		if sc, err = GetScrim(txCtx, tx, scrimID); err != nil {
			return err
		}
		if sc == nil {
			return api.NotFound("内战不存在")
		}
		if err := checkBoardVersion(sc, baseBoardVersion); err != nil {
			return err
		}
		if err := setSelection(txCtx, tx, scrimID, ids, now); err != nil {
			return err
		}
		return bumpBoard(txCtx, tx, scrimID)
	})
	if err != nil {
		return nil, err
	}
	rows, err := loadRows(ctx.Context, s.d.ReadPool(), scrimID)
	if err != nil {
		return nil, err
	}
	var selected []signupRow
	for _, r := range rows {
		if r.IsSelected {
			selected = append(selected, r)
		}
	}
	players := s.players(selected)
	rng := s.rng
	if rng == nil {
		rng = rand.New(rand.NewSource(time.Now().UnixNano()))
	}
	split, err := Generate(players, sc.Format, rng)
	if err != nil {
		if IsNoSolution(err) {
			return nil, api.InvalidFields(map[string][]string{"__all__": {err.Error()}})
		}
		return nil, err
	}
	used := RatingsUsed(split, players, sc.Format)
	var placements []Placement
	for _, side := range []struct {
		team string
		a    Assignment
	}{{"a", split.A}, {"b", split.B}} {
		for role, ids := range side.a.ByRole {
			for _, id := range ids {
				u := used[id]
				placements = append(placements, Placement{SignupID: id, Team: side.team, Role: role, Rating: &u})
			}
		}
	}
	if err := s.saveTeams(ctx, scrimID, placements, now); err != nil {
		return nil, err
	}
	board, err := s.buildBoard(ctx.Context, s.d.ReadPool(), scrimID, "", v.HasCap(accounts.CapContactsView))
	if err != nil {
		return nil, err
	}
	unrated := UnratedPlacements(split, players, sc.Format)
	board.Warnings = unrated
	return &GenerateResult{Board: board, Score: split.Score, Unrated: nonNil(unrated)}, nil
}

func nonNil(l []string) []string {
	if l == nil {
		return []string{}
	}
	return l
}

// PlacementIn 是保存分队时一个人的去向（接口入参）。
type PlacementIn struct {
	SignupID int64  `json:"signup_id"`
	Team     string `json:"team"`
	Role     string `json:"role"`
}

// Placement 是落库的去向：队、位置、分队时按多少分算。
type Placement struct {
	SignupID int64
	Team     string
	Role     string
	Rating   *int
}

// saveTeams 存分队（规则 164、165）：每个报名一条去向；没放进任何队的上场者进替补——
// is_selected 保留（还在板上），但队和位置清空；保存后置分队时间、清名单变动标记。不校验位置配比。
func (s *Service) saveTeams(ctx *app.Ctx, scrimID int64, placements []Placement, now time.Time) error {
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		list, err := listSignups(txCtx, tx, scrimID)
		if err != nil {
			return err
		}
		rows := map[int64]*Signup{}
		for _, g := range list {
			rows[g.ID] = g
		}
		placed := map[int64]bool{}
		for _, p := range placements {
			if rows[p.SignupID] == nil {
				continue // 不属于这场内战的忽略
			}
			placed[p.SignupID] = true
			var rating any
			if p.Rating != nil {
				rating = *p.Rating
			}
			if _, err := tx.ExecContext(txCtx, `UPDATE scrim_signups SET team = ?, assigned_role = ?, rating_used = ?,
				is_selected = ?, updated_at = ? WHERE id = ?`, p.Team, p.Role, rating, b2i(p.Team != ""), db.FormatUTC(now), p.SignupID); err != nil {
				return err
			}
		}
		for _, g := range list {
			if placed[g.ID] || (g.Team == "" && g.AssignedRole == "") {
				continue
			}
			if _, err := tx.ExecContext(txCtx, `UPDATE scrim_signups SET team = '', assigned_role = '', rating_used = NULL, updated_at = ? WHERE id = ?`,
				db.FormatUTC(now), g.ID); err != nil {
				return err
			}
		}
		_, err = tx.ExecContext(txCtx, `UPDATE scrims SET teams_generated_at = ?, roster_changed_at = NULL, board_version = board_version + 1 WHERE id = ?`,
			db.FormatUTC(now), scrimID)
		return err
	})
}

// SaveTeams 管理员手工保存分队（规则 164、165）：只校验报名属于这场内战；队是 a/b 以外的当没放。
// 角色限定的位置分数取该位置的段位（没有按 0 算，216 S5）；不限位置取最高段位。
func (s *Service) SaveTeams(ctx *app.Ctx, scrimID int64, in []PlacementIn, baseBoardVersion int64) (*Board, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	sc, err := GetScrim(ctx.Context, s.d.ReadPool(), scrimID)
	if err != nil {
		return nil, err
	}
	if sc == nil {
		return nil, api.NotFound("内战不存在")
	}
	if err := checkBoardVersion(sc, baseBoardVersion); err != nil {
		return nil, err
	}
	rows, err := loadRows(ctx.Context, s.d.ReadPool(), scrimID)
	if err != nil {
		return nil, err
	}
	byID := map[int64]signupRow{}
	for _, r := range rows {
		byID[r.ID] = r
	}
	var placements []Placement
	for _, p := range in {
		r, ok := byID[p.SignupID]
		if !ok || (p.Team != "a" && p.Team != "b") {
			continue
		}
		role := p.Role
		switch {
		case !sc.RoleQueue():
			role = ""
		case role != Tank && role != Damage && role != Support:
			role = r.AssignedRole
		}
		var rating *int
		if sc.RoleQueue() && role != "" {
			x := 0
			if got := r.rating(role); got != nil {
				x = *got
			}
			rating = &x
		} else {
			rating = r.best()
		}
		placements = append(placements, Placement{SignupID: p.SignupID, Team: p.Team, Role: role, Rating: rating})
	}
	if err := s.saveTeamsChecked(ctx, scrimID, placements, now, baseBoardVersion); err != nil {
		return nil, err
	}
	return s.buildBoard(ctx.Context, s.d.ReadPool(), scrimID, "", v.HasCap(accounts.CapContactsView))
}

// saveTeamsChecked 和 saveTeams 一样，但在同一个事务里再核对一次板版本，防止两个管理员同时保存互相覆盖。
func (s *Service) saveTeamsChecked(ctx *app.Ctx, scrimID int64, placements []Placement, now time.Time, base int64) error {
	var cur int64
	if err := s.d.ReadPool().QueryRowContext(ctx.Context, `SELECT board_version FROM scrims WHERE id = ?`, scrimID).Scan(&cur); err != nil {
		return err
	}
	if cur != base {
		return api.NewErr(409, "stale", "分队板刚被改过，已换成最新内容")
	}
	return s.saveTeams(ctx, scrimID, placements, now)
}
