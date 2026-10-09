// Package members 是成员展示（设计 6）：谁算「已加入」、成员墙、成员主页，以及后台的
// 成员分组（规则 R236、R237）。
package members

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

const (
	// GroupNameMax 分组名字数上限。
	GroupNameMax = 20
	// GroupDescMax 分组简介字数上限。
	GroupDescMax = 200
	// TitleTotalMax 一个人在一个组里的职务，合起来最多 20 字（规则 237）。
	TitleTotalMax = 20
	// TitleEachMax 每个职务最多 10 字（规则 237）。
	TitleEachMax = 10
	// SearchLimit 后台按昵称搜人最多回 10 条（规则 237）。
	SearchLimit = 10
	// ArticlesOnPage 成员主页上最多列几篇文章。
	ArticlesOnPage = 10
)

// joinedWhere 是「已加入」的判定（规则 236）：账号没停用，并且验证过邮箱。
const joinedWhere = `u.is_active = 1 AND u.email_verified_at IS NOT NULL`

// titleSeparators 一个职务框里可以放几个职务：「社长、主播」。
var titleSeparators = regexp.MustCompile(`[、/／,，;；]+`)

// SplitTitles 把职务框拆成一个个职务，去掉空的。
func SplitTitles(value string) []string {
	out := []string{}
	for _, part := range titleSeparators.Split(value, -1) {
		if part = strings.TrimSpace(part); part != "" {
			out = append(out, part)
		}
	}
	return out
}

// Service 是成员展示和分组的业务。
type Service struct {
	d *db.DB
}

// NewService 造成员服务；d 可以是 nil（apigen）。
func NewService(d *db.DB) *Service { return &Service{d: d} }

// TeamRef 是成员所在的战队（名字和编号）。
type TeamRef struct {
	ID   int64  `json:"id"`
	Name string `json:"name"`
}

// Card 是成员墙上的一张卡。
type Card struct {
	UserID   int64                      `json:"user_id"`
	Number   int                        `json:"number"` // 按加入先后排的序号（001…），筛选后也不变
	Nickname string                     `json:"nickname"`
	Motto    string                     `json:"motto"`
	MainRole string                     `json:"main_role"`
	Roles    []string                   `json:"roles"`
	Ranks    accounts.PublicRanksResult `json:"ranks"`
	Teams    []TeamRef                  `json:"teams"`
	Groups   []string                   `json:"groups"`
	Titles   []string                   `json:"titles"`
}

// Tags 是职务；没有职务的人退回到所在分组的名字（设计 4.3）。
func (c Card) Tags() []string {
	if len(c.Titles) > 0 {
		return c.Titles
	}
	return c.Groups
}

// SectionEntry 是一个分组里的一个人，带着他在这个组里的职务。
type SectionEntry struct {
	Titles []string `json:"titles"`
	Member Card     `json:"member"`
}

// Section 是成员墙上的一个分组。
type Section struct {
	ID          int64          `json:"id"`
	Name        string         `json:"name"`
	Description string         `json:"description"`
	Entries     []SectionEntry `json:"entries"`
}

// ShowcaseInput 是成员墙的筛选：按常用位置，或只看还没进任何战队的人（设计 6.3）。
type ShowcaseInput struct {
	Role string
	Free bool
}

// ShowcaseResult 是成员墙要的全部。
type ShowcaseResult struct {
	Sections  []Section `json:"sections"`
	Members   []Card    `json:"members"`
	Total     int       `json:"total"`
	Role      string    `json:"role"`
	Free      bool      `json:"free"`
	Filtering bool      `json:"filtering"`
}

// Showcase 成员墙（公开）：可见的分组按顺序，再是所有已加入的人，先加入的在前。
func (s *Service) Showcase(ctx context.Context, in ShowcaseInput, now time.Time) (*ShowcaseResult, error) {
	rd := s.d.ReadPool()
	rows, err := rd.QueryContext(ctx, `SELECT u.id, u.nickname, u.motto, u.main_role, u.flex_roles, u.show_rank
		FROM users u WHERE `+joinedWhere+` ORDER BY u.created_at, u.id`)
	if err != nil {
		return nil, err
	}
	type flexShow struct {
		flex string
		show bool
	}
	var order []int64
	cards := map[int64]*Card{}
	extra := map[int64]flexShow{}
	for rows.Next() {
		var c Card
		var flex string
		var show int
		if err := rows.Scan(&c.UserID, &c.Nickname, &c.Motto, &c.MainRole, &flex, &show); err != nil {
			rows.Close()
			return nil, err
		}
		if _, ok := accounts.RoleLabels[c.MainRole]; !ok {
			c.MainRole = ""
		}
		c.Number = len(order) + 1
		c.Teams, c.Groups, c.Titles = []TeamRef{}, []string{}, []string{}
		order = append(order, c.UserID)
		cards[c.UserID] = &c
		extra[c.UserID] = flexShow{flex: flex, show: show == 1}
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}
	gas, err := accounts.LoadGameAccounts(ctx, rd, order)
	if err != nil {
		return nil, err
	}
	for id, c := range cards {
		c.Roles = accounts.PublicPositions(c.MainRole, extra[id].flex)
		c.Ranks = accounts.CalculatePublicRanks(gas[id], extra[id].show, now)
	}

	trows, err := rd.QueryContext(ctx, `SELECT m.user_id, t.id, t.name FROM team_memberships m
		JOIN teams t ON t.id = m.team_id WHERE t.disbanded_at IS NULL ORDER BY t.name, t.id`)
	if err != nil {
		return nil, err
	}
	for trows.Next() {
		var uid int64
		var ref TeamRef
		if err := trows.Scan(&uid, &ref.ID, &ref.Name); err != nil {
			trows.Close()
			return nil, err
		}
		if c, ok := cards[uid]; ok {
			c.Teams = append(c.Teams, ref)
		}
	}
	trows.Close()
	if err := trows.Err(); err != nil {
		return nil, err
	}

	sections := []Section{}
	grows, err := rd.QueryContext(ctx, `SELECT id, name, description FROM member_groups
		WHERE is_visible = 1 AND name <> '' ORDER BY sort_order, name, id`)
	if err != nil {
		return nil, err
	}
	for grows.Next() {
		var sec Section
		if err := grows.Scan(&sec.ID, &sec.Name, &sec.Description); err != nil {
			grows.Close()
			return nil, err
		}
		sec.Entries = []SectionEntry{}
		sections = append(sections, sec)
	}
	grows.Close()
	if err := grows.Err(); err != nil {
		return nil, err
	}
	for i := range sections {
		mrows, err := rd.QueryContext(ctx, `SELECT g.user_id, g.title FROM member_group_memberships g
			JOIN users u ON u.id = g.user_id WHERE g.group_id = ? ORDER BY g.sort_order, u.nickname, g.id`, sections[i].ID)
		if err != nil {
			return nil, err
		}
		for mrows.Next() {
			var uid int64
			var title string
			if err := mrows.Scan(&uid, &title); err != nil {
				mrows.Close()
				return nil, err
			}
			c, ok := cards[uid]
			if !ok {
				continue // 退出、停用或没验证邮箱的人不显示
			}
			titles := SplitTitles(title)
			c.Groups = append(c.Groups, sections[i].Name)
			for _, t := range titles {
				if !contains(c.Titles, t) {
					c.Titles = append(c.Titles, t)
				}
			}
			sections[i].Entries = append(sections[i].Entries, SectionEntry{Titles: titles, Member: Card{UserID: uid}})
		}
		mrows.Close()
		if err := mrows.Err(); err != nil {
			return nil, err
		}
	}
	// 分组里的卡片要带上最终的职务和分组，等所有分组都走完再填。
	for i := range sections {
		for j := range sections[i].Entries {
			sections[i].Entries[j].Member = *cards[sections[i].Entries[j].Member.UserID]
		}
	}

	role := in.Role
	if _, ok := accounts.RoleLabels[role]; !ok {
		role = ""
	}
	res := &ShowcaseResult{Sections: sections, Members: []Card{}, Total: len(order), Role: role, Free: in.Free,
		Filtering: role != "" || in.Free}
	for _, id := range order {
		c := cards[id]
		if role != "" && c.MainRole != role {
			continue
		}
		if in.Free && len(c.Teams) > 0 {
			continue
		}
		res.Members = append(res.Members, *c)
	}
	return res, nil
}

func contains(list []string, s string) bool {
	for _, x := range list {
		if x == s {
			return true
		}
	}
	return false
}

// GroupRef 是成员主页上的一个分组和他的职务。
type GroupRef struct {
	ID     int64    `json:"id"`
	Name   string   `json:"name"`
	Titles []string `json:"titles"`
}

// AlumniRef 是成员曾经待过的战队。
type AlumniRef struct {
	TeamID   int64     `json:"team_id"`
	TeamName string    `json:"team_name"`
	Role     string    `json:"role"`
	LeftAt   time.Time `json:"left_at"`
	Reason   string    `json:"reason"`
}

// ArticleRef 是成员发表过的一篇文章。
type ArticleRef struct {
	ID               int64      `json:"id"`
	Slug             string     `json:"slug"`
	Title            string     `json:"title"`
	FirstPublishedAt *time.Time `json:"first_published_at,omitempty"`
}

// TeamEntry 是成员主页上的一支现役战队。
type TeamEntry struct {
	TeamRef
	MemberCount int  `json:"member_count"`
	IsCaptain   bool `json:"is_captain"`
}

// Page 是成员主页要的全部：只放设计 1.8 说公开的东西。
type Page struct {
	Card         Card         `json:"card"`
	Groups       []GroupRef   `json:"groups"`
	Teams        []TeamEntry  `json:"teams"`
	Alumni       []AlumniRef  `json:"alumni"`
	Articles     []ArticleRef `json:"articles"`
	ArticleCount int          `json:"article_count"`
	IsOwner      bool         `json:"is_owner"`
}

// Detail 成员主页（公开）。只有成员墙上的人（已加入）才有主页，别人是 404。
func (s *Service) Detail(ctx *app.Ctx, userID int64) (*Page, error) {
	rd := s.d.ReadPool()
	now := ctx.Now().UTC()
	var c Card
	var flex string
	var show int
	err := rd.QueryRowContext(ctx.Context, `SELECT u.id, u.nickname, u.motto, u.main_role, u.flex_roles, u.show_rank
		FROM users u WHERE u.id = ? AND `+joinedWhere, userID).
		Scan(&c.UserID, &c.Nickname, &c.Motto, &c.MainRole, &flex, &show)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, api.NotFound("没有这位成员。")
	}
	if err != nil {
		return nil, err
	}
	if _, ok := accounts.RoleLabels[c.MainRole]; !ok {
		c.MainRole = ""
	}
	gas, err := accounts.LoadGameAccounts(ctx.Context, rd, []int64{userID})
	if err != nil {
		return nil, err
	}
	c.Roles = accounts.PublicPositions(c.MainRole, flex)
	c.Ranks = accounts.CalculatePublicRanks(gas[userID], show == 1, now)
	c.Teams, c.Groups, c.Titles = []TeamRef{}, []string{}, []string{}
	page := &Page{Card: c, Groups: []GroupRef{}, Teams: []TeamEntry{}, Alumni: []AlumniRef{}, Articles: []ArticleRef{}}
	page.IsOwner = ctx.Viewer != nil && ctx.Viewer.ID == userID

	rows, err := rd.QueryContext(ctx.Context, `SELECT g.id, g.name, m.title FROM member_group_memberships m
		JOIN member_groups g ON g.id = m.group_id WHERE m.user_id = ? AND g.is_visible = 1
		ORDER BY g.sort_order, g.name, g.id`, userID)
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var ref GroupRef
		var title string
		if err := rows.Scan(&ref.ID, &ref.Name, &title); err != nil {
			rows.Close()
			return nil, err
		}
		ref.Titles = SplitTitles(title)
		page.Groups = append(page.Groups, ref)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	trows, err := rd.QueryContext(ctx.Context, `SELECT t.id, t.name, m.role,
		(SELECT COUNT(*) FROM team_memberships x WHERE x.team_id = t.id)
		FROM team_memberships m JOIN teams t ON t.id = m.team_id
		WHERE m.user_id = ? AND t.disbanded_at IS NULL ORDER BY t.name, t.id`, userID)
	if err != nil {
		return nil, err
	}
	for trows.Next() {
		var e TeamEntry
		var role string
		if err := trows.Scan(&e.ID, &e.Name, &role, &e.MemberCount); err != nil {
			trows.Close()
			return nil, err
		}
		e.IsCaptain = role == "captain"
		page.Teams = append(page.Teams, e)
	}
	trows.Close()
	if err := trows.Err(); err != nil {
		return nil, err
	}

	arows, err := rd.QueryContext(ctx.Context, `SELECT a.team_id, t.name, a.role, a.left_at, a.reason
		FROM team_alumni a JOIN teams t ON t.id = a.team_id
		WHERE a.user_id = ? AND t.disbanded_at IS NULL ORDER BY a.left_at DESC, a.id DESC`, userID)
	if err != nil {
		return nil, err
	}
	for arows.Next() {
		var a AlumniRef
		var left string
		if err := arows.Scan(&a.TeamID, &a.TeamName, &a.Role, &left, &a.Reason); err != nil {
			arows.Close()
			return nil, err
		}
		a.LeftAt, _ = db.ParseUTC(left)
		page.Alumni = append(page.Alumni, a)
	}
	arows.Close()
	if err := arows.Err(); err != nil {
		return nil, err
	}

	if err := rd.QueryRowContext(ctx.Context, `SELECT COUNT(*) FROM pages p JOIN articles a ON a.page_id = p.id
		WHERE p.kind = 'article' AND p.live = 1 AND a.author_id = ?`, userID).Scan(&page.ArticleCount); err != nil {
		return nil, err
	}
	frows, err := rd.QueryContext(ctx.Context, `SELECT p.id, p.slug, p.title, p.first_published_at
		FROM pages p JOIN articles a ON a.page_id = p.id
		WHERE p.kind = 'article' AND p.live = 1 AND a.author_id = ?
		ORDER BY p.first_published_at DESC, p.id DESC LIMIT ?`, userID, ArticlesOnPage)
	if err != nil {
		return nil, err
	}
	defer frows.Close()
	for frows.Next() {
		var a ArticleRef
		var first sql.NullString
		if err := frows.Scan(&a.ID, &a.Slug, &a.Title, &first); err != nil {
			return nil, err
		}
		if first.Valid && first.String != "" {
			if t, err := db.ParseUTC(first.String); err == nil {
				a.FirstPublishedAt = &t
			}
		}
		page.Articles = append(page.Articles, a)
	}
	return page, frows.Err()
}

// ---------------------------------------------------------------------------
// 后台：成员分组（设计 6.2、docs/admin.md 4.4）
// ---------------------------------------------------------------------------

// Group 是一个成员分组。名字为空的是还没填完的新组，不显示在成员墙上。
type Group struct {
	ID          int64     `json:"id"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	IsVisible   bool      `json:"is_visible"`
	SortOrder   int       `json:"sort_order"`
	Version     int64     `json:"version"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// GroupMember 是分组里的一个人。
type GroupMember struct {
	ID        int64  `json:"id"`
	UserID    int64  `json:"user_id"`
	Nickname  string `json:"nickname"`
	Email     string `json:"email,omitempty"` // 只给超管看
	Title     string `json:"title"`
	SortOrder int    `json:"sort_order"`
	Joined    bool   `json:"joined"` // 现在还算不算已加入；不算的不会出现在成员墙上
}

// GroupDetail 是一个分组连同组里的人。
type GroupDetail struct {
	Group   Group         `json:"group"`
	Members []GroupMember `json:"members"`
}

// GroupSummary 是分组列表里的一行。
type GroupSummary struct {
	Group
	MemberCount int `json:"member_count"`
}

func requireManager(ctx *app.Ctx) (*app.Viewer, error) {
	v := ctx.Viewer
	if v == nil || v.Disabled || v.ID <= 0 {
		return nil, api.Unauthorized("要先登录")
	}
	if !v.HasCap(accounts.CapMemberGroups) {
		return nil, api.Forbidden()
	}
	return v, nil
}

func scanGroup(row interface{ Scan(...any) error }) (*Group, error) {
	var g Group
	var vis int
	var created, updated string
	if err := row.Scan(&g.ID, &g.Name, &g.Description, &vis, &g.SortOrder, &g.Version, &created, &updated); err != nil {
		return nil, err
	}
	g.IsVisible = vis == 1
	g.CreatedAt, _ = db.ParseUTC(created)
	g.UpdatedAt, _ = db.ParseUTC(updated)
	return &g, nil
}

const groupCols = `id, name, description, is_visible, sort_order, version, created_at, updated_at`

func (s *Service) getGroup(ctx context.Context, q db.DBTX, id int64) (*Group, error) {
	g, err := scanGroup(q.QueryRowContext(ctx, `SELECT `+groupCols+` FROM member_groups WHERE id = ?`, id))
	if errors.Is(err, sql.ErrNoRows) {
		return nil, api.NotFound("分组不存在")
	}
	return g, err
}

// ListGroups 分组列表。
func (s *Service) ListGroups(ctx *app.Ctx) ([]GroupSummary, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT `+groupCols+`,
		(SELECT COUNT(*) FROM member_group_memberships m WHERE m.group_id = member_groups.id)
		FROM member_groups ORDER BY sort_order, name, id`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []GroupSummary{}
	for rows.Next() {
		var g Group
		var vis, n int
		var created, updated string
		if err := rows.Scan(&g.ID, &g.Name, &g.Description, &vis, &g.SortOrder, &g.Version, &created, &updated, &n); err != nil {
			return nil, err
		}
		g.IsVisible = vis == 1
		g.CreatedAt, _ = db.ParseUTC(created)
		g.UpdatedAt, _ = db.ParseUTC(updated)
		out = append(out, GroupSummary{Group: g, MemberCount: n})
	}
	return out, rows.Err()
}

// GetGroup 一个分组连同组里的人，按组内顺序。
func (s *Service) GetGroup(ctx *app.Ctx, id int64) (*GroupDetail, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	return s.groupDetail(ctx.Context, s.d.ReadPool(), id, v.Superuser)
}

func (s *Service) groupDetail(ctx context.Context, q db.DBTX, id int64, withEmail bool) (*GroupDetail, error) {
	g, err := s.getGroup(ctx, q, id)
	if err != nil {
		return nil, err
	}
	rows, err := q.QueryContext(ctx, `SELECT m.id, m.user_id, u.nickname, u.email, m.title, m.sort_order,
		CASE WHEN `+joinedWhere+` THEN 1 ELSE 0 END
		FROM member_group_memberships m JOIN users u ON u.id = m.user_id
		WHERE m.group_id = ? ORDER BY m.sort_order, m.id`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	d := &GroupDetail{Group: *g, Members: []GroupMember{}}
	for rows.Next() {
		var m GroupMember
		var joined int
		if err := rows.Scan(&m.ID, &m.UserID, &m.Nickname, &m.Email, &m.Title, &m.SortOrder, &joined); err != nil {
			return nil, err
		}
		m.Joined = joined == 1
		if !withEmail {
			m.Email = ""
		}
		d.Members = append(d.Members, m)
	}
	return d, rows.Err()
}

// CreateGroup 建一个空白分组。新组名字还空着，不显示在成员墙上，等第一次保存名字（设计 13.17）。
func (s *Service) CreateGroup(ctx *app.Ctx) (*Group, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	now := db.FormatUTC(ctx.Now().UTC())
	var g *Group
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `INSERT INTO member_groups (name, description, is_visible, sort_order, version, created_at, updated_at)
			VALUES ('', '', 1, COALESCE((SELECT MAX(sort_order) + 1 FROM member_groups), 0), 1, ?, ?)`, now, now)
		if err != nil {
			return err
		}
		id, err := res.LastInsertId()
		if err != nil {
			return err
		}
		g, err = s.getGroup(txCtx, tx, id)
		return err
	})
	return g, err
}

// GroupChanges 是这次要改的分组字段，没出现的不动。
type GroupChanges struct {
	Name        *string `json:"name,omitempty"`
	Description *string `json:"description,omitempty"`
	IsVisible   *bool   `json:"is_visible,omitempty"`
	SortOrder   *int    `json:"sort_order,omitempty"`
}

// GroupSaveResult 是分组自动保存的回答。
type GroupSaveResult struct {
	Version int64               `json:"version"`
	Saved   []string            `json:"saved"`
	Fields  map[string][]string `json:"fields,omitempty"`
	SavedAt time.Time           `json:"saved_at"`
}

// UpdateGroup 按字段保存分组：合法的存，不合法的留旧值。组名不分大小写唯一。
func (s *Service) UpdateGroup(ctx *app.Ctx, id, baseVersion int64, ch GroupChanges) (*GroupSaveResult, error) {
	if _, err := requireManager(ctx); err != nil {
		return nil, err
	}
	now := ctx.Now().UTC()
	res := &GroupSaveResult{Fields: map[string][]string{}, SavedAt: now}
	err := s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		g, err := s.getGroup(txCtx, tx, id)
		if err != nil {
			return err
		}
		if baseVersion != g.Version {
			return api.NewErr(409, "stale", "另一个人刚改过，已换成最新内容")
		}
		var sets []string
		var args []any
		set := func(field, col string, val any) {
			sets = append(sets, col+" = ?")
			args = append(args, val)
			res.Saved = append(res.Saved, field)
		}
		if ch.Name != nil {
			name := strings.TrimSpace(*ch.Name)
			switch {
			case utf8.RuneCountInString(name) > GroupNameMax:
				res.Fields["name"] = []string{fmt.Sprintf("名称最多 %d 字。", GroupNameMax)}
			case name != "" && name != g.Name:
				var n int
				if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM member_groups
					WHERE lower(name) = lower(?) AND id <> ?`, name, id).Scan(&n); err != nil {
					return err
				}
				if n > 0 {
					res.Fields["name"] = []string{"已经有同名的分组了。"}
				} else {
					set("name", "name", name)
				}
			case name != g.Name:
				set("name", "name", name)
			}
		}
		if ch.Description != nil {
			d := strings.TrimSpace(*ch.Description)
			switch {
			case utf8.RuneCountInString(d) > GroupDescMax:
				res.Fields["description"] = []string{fmt.Sprintf("简介最多 %d 字。", GroupDescMax)}
			case d != g.Description:
				set("description", "description", d)
			}
		}
		if ch.IsVisible != nil && *ch.IsVisible != g.IsVisible {
			v := 0
			if *ch.IsVisible {
				v = 1
			}
			set("is_visible", "is_visible", v)
		}
		if ch.SortOrder != nil {
			if *ch.SortOrder < 0 || *ch.SortOrder > 32767 {
				res.Fields["sort_order"] = []string{"排序要在 0 到 32767 之间。"}
			} else if *ch.SortOrder != g.SortOrder {
				set("sort_order", "sort_order", *ch.SortOrder)
			}
		}
		res.Version = g.Version
		if len(sets) > 0 {
			sets = append(sets, "version = version + 1", "updated_at = ?")
			args = append(args, db.FormatUTC(now), id)
			if _, err := tx.ExecContext(txCtx, `UPDATE member_groups SET `+strings.Join(sets, ", ")+` WHERE id = ?`, args...); err != nil {
				return err
			}
			res.Version = g.Version + 1
		}
		return nil
	})
	if err != nil && strings.Contains(err.Error(), "UNIQUE constraint failed") {
		return nil, api.InvalidFields(map[string][]string{"name": {"已经有同名的分组了。"}})
	}
	if err != nil {
		return nil, err
	}
	if len(res.Fields) == 0 {
		res.Fields = nil
	}
	return res, nil
}

// DeleteGroup 删分组（组里的人随之移出，人本身不受影响）。
func (s *Service) DeleteGroup(ctx *app.Ctx, id int64) error {
	if _, err := requireManager(ctx); err != nil {
		return err
	}
	return s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		res, err := tx.ExecContext(txCtx, `DELETE FROM member_groups WHERE id = ?`, id)
		if err != nil {
			return err
		}
		if n, _ := res.RowsAffected(); n == 0 {
			return api.NotFound("分组不存在")
		}
		return nil
	})
}

// Person 是后台搜人的一条结果。
type Person struct {
	UserID   int64  `json:"user_id"`
	Nickname string `json:"nickname"`
	Email    string `json:"email,omitempty"`
}

// SearchPeople 按昵称搜已加入的人，排除已经在组里的，最多 10 条（规则 237）。
// 邮箱只有超管能当搜索条件、也只有超管看得到：内容编辑搜「@」会一次读走所有人的邮箱（216 A2）。
func (s *Service) SearchPeople(ctx *app.Ctx, groupID int64, query string) ([]Person, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	out := []Person{}
	query = strings.TrimSpace(query)
	if query == "" {
		return out, nil
	}
	like := "%" + escapeLike(query) + "%"
	cond := `u.nickname LIKE ? ESCAPE '\'`
	args := []any{like}
	if v.Superuser {
		cond = `(u.nickname LIKE ? ESCAPE '\' OR u.email LIKE ? ESCAPE '\')`
		args = append(args, like)
	}
	args = append(args, groupID, SearchLimit)
	rows, err := s.d.ReadPool().QueryContext(ctx.Context, `SELECT u.id, u.nickname, u.email FROM users u
		WHERE `+joinedWhere+` AND `+cond+`
		AND u.id NOT IN (SELECT user_id FROM member_group_memberships WHERE group_id = ?)
		ORDER BY u.nickname, u.id LIMIT ?`, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var p Person
		if err := rows.Scan(&p.UserID, &p.Nickname, &p.Email); err != nil {
			return nil, err
		}
		if !v.Superuser {
			p.Email = ""
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func escapeLike(s string) string {
	r := strings.NewReplacer(`\`, `\\`, `%`, `\%`, `_`, `\_`)
	return r.Replace(s)
}

// AddMember 把一个人加到组的末尾：只能加已加入的人，每人在每组只一次。
func (s *Service) AddMember(ctx *app.Ctx, groupID, userID int64) (*GroupDetail, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	var d *GroupDetail
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		if _, err := s.getGroup(txCtx, tx, groupID); err != nil {
			return err
		}
		var nick string
		if err := tx.QueryRowContext(txCtx, `SELECT nickname FROM users u WHERE u.id = ? AND `+joinedWhere, userID).Scan(&nick); err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return api.InvalidFields(map[string][]string{"user_id": {"只能加已加入的用户：账号没有停用，并且验证过邮箱。"}})
			}
			return err
		}
		var n int
		if err := tx.QueryRowContext(txCtx, `SELECT COUNT(*) FROM member_group_memberships WHERE group_id = ? AND user_id = ?`,
			groupID, userID).Scan(&n); err != nil {
			return err
		}
		if n > 0 {
			return api.InvalidFields(map[string][]string{"user_id": {fmt.Sprintf("「%s」已经在这个分组里了。", nick)}})
		}
		if _, err := tx.ExecContext(txCtx, `INSERT INTO member_group_memberships (group_id, user_id, title, sort_order)
			VALUES (?, ?, '', COALESCE((SELECT MAX(sort_order) + 1 FROM member_group_memberships WHERE group_id = ?), 0))`,
			groupID, userID, groupID); err != nil {
			return err
		}
		d, err = s.groupDetail(txCtx, tx, groupID, v.Superuser)
		return err
	})
	return d, err
}

func (s *Service) membershipGroup(ctx context.Context, q db.DBTX, membershipID int64) (int64, string, error) {
	var gid int64
	var title string
	err := q.QueryRowContext(ctx, `SELECT group_id, title FROM member_group_memberships WHERE id = ?`, membershipID).Scan(&gid, &title)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, "", api.NotFound("分组成员不存在")
	}
	return gid, title, err
}

// RemoveMember 把一个人移出分组。
func (s *Service) RemoveMember(ctx *app.Ctx, membershipID int64) (*GroupDetail, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	var d *GroupDetail
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		gid, _, err := s.membershipGroup(txCtx, tx, membershipID)
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `DELETE FROM member_group_memberships WHERE id = ?`, membershipID); err != nil {
			return err
		}
		d, err = s.groupDetail(txCtx, tx, gid, v.Superuser)
		return err
	})
	return d, err
}

// MoveMember 组内上移（-1）或下移（+1）一位；组内顺序重新从 0 编号，删人留下的空档就合上了。
// 已经在头或尾就不动。
func (s *Service) MoveMember(ctx *app.Ctx, membershipID int64, step int) (*GroupDetail, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	if step != -1 && step != 1 {
		return nil, api.InvalidFields(map[string][]string{"step": {"只能上移或下移一位。"}})
	}
	var d *GroupDetail
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		gid, _, err := s.membershipGroup(txCtx, tx, membershipID)
		if err != nil {
			return err
		}
		rows, err := tx.QueryContext(txCtx, `SELECT id FROM member_group_memberships WHERE group_id = ? ORDER BY sort_order, id`, gid)
		if err != nil {
			return err
		}
		var ids []int64
		for rows.Next() {
			var id int64
			if err := rows.Scan(&id); err != nil {
				rows.Close()
				return err
			}
			ids = append(ids, id)
		}
		rows.Close()
		idx := -1
		for i, id := range ids {
			if id == membershipID {
				idx = i
			}
		}
		other := idx + step
		if other >= 0 && other < len(ids) {
			ids[idx], ids[other] = ids[other], ids[idx]
		}
		for n, id := range ids {
			if _, err := tx.ExecContext(txCtx, `UPDATE member_group_memberships SET sort_order = ? WHERE id = ?`, n, id); err != nil {
				return err
			}
		}
		d, err = s.groupDetail(txCtx, tx, gid, v.Superuser)
		return err
	})
	return d, err
}

// ValidateTitle 职务：合起来最多 20 字，每个最多 10 字（规则 237）。
func ValidateTitle(title string) (string, string) {
	title = strings.TrimSpace(title)
	if utf8.RuneCountInString(title) > TitleTotalMax {
		return title, "每个职务最多 10 字，多个职务用顿号分开，合起来最多 20 字。"
	}
	for _, p := range SplitTitles(title) {
		if utf8.RuneCountInString(p) > TitleEachMax {
			return title, "每个职务最多 10 字，多个职务用顿号分开，合起来最多 20 字。"
		}
	}
	return title, ""
}

// SetTitle 改一个人在组里的职务。
func (s *Service) SetTitle(ctx *app.Ctx, membershipID int64, title string) (*GroupDetail, error) {
	v, err := requireManager(ctx)
	if err != nil {
		return nil, err
	}
	title, msg := ValidateTitle(title)
	if msg != "" {
		return nil, api.InvalidFields(map[string][]string{"title": {msg}})
	}
	var d *GroupDetail
	err = s.d.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
		gid, _, err := s.membershipGroup(txCtx, tx, membershipID)
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(txCtx, `UPDATE member_group_memberships SET title = ? WHERE id = ?`, title, membershipID); err != nil {
			return err
		}
		d, err = s.groupDetail(txCtx, tx, gid, v.Superuser)
		return err
	})
	return d, err
}
