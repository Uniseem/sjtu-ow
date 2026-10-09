package members

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

var t0 = time.Date(2026, 10, 9, 12, 0, 0, 0, time.UTC)

type env struct {
	t   *testing.T
	d   *db.DB
	svc *Service
	n   int64
}

func newEnv(t *testing.T) *env {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "members.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return &env{t: t, d: d, svc: NewService(d)}
}

func (e *env) exec(q string, args ...any) {
	e.t.Helper()
	if err := e.d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		_, err := tx.ExecContext(ctx, q, args...)
		return err
	}); err != nil {
		e.t.Fatalf("exec %q: %v", q, err)
	}
}

func (e *env) count(q string, args ...any) int {
	e.t.Helper()
	var n int
	if err := e.d.ReadPool().QueryRow(q, args...).Scan(&n); err != nil {
		e.t.Fatal(err)
	}
	return n
}

// user 建一个已加入的成员（启用 + 验证过邮箱）；序号决定加入先后。
func (e *env) user(nick string) int64 {
	e.t.Helper()
	e.n++
	ts := db.FormatUTC(t0.Add(time.Duration(e.n) * time.Minute))
	e.exec(`INSERT INTO users (id, email, email_norm, password_hash, nickname, is_sjtu, agreed_terms_at,
		agreed_cross_border_at, email_verified_at, is_active, created_at, updated_at)
		VALUES (?, ?, ?, 'h', ?, 1, ?, ?, ?, 1, ?, ?)`,
		e.n, fmt.Sprintf("m%d@sjtu.example", e.n), fmt.Sprintf("m%d@sjtu.example", e.n), nick, ts, ts, ts, ts, ts)
	return e.n
}

func (e *env) ctx(id int64, super bool, caps ...app.Cap) *app.Ctx {
	cm := map[app.Cap]struct{}{}
	for _, c := range caps {
		cm[c] = struct{}{}
	}
	return &app.Ctx{
		Context: context.Background(),
		Viewer:  &app.Viewer{ID: id, EmailVerified: true, Superuser: super, Caps: cm},
		Clock:   clock.Fixed(t0),
	}
}

func (e *env) editor() *app.Ctx { return e.ctx(e.user("编辑"), false, accounts.CapMemberGroups) }

func wantStatus(t *testing.T, err error, status int, msg string) {
	t.Helper()
	var ae *api.Error
	if !errors.As(err, &ae) || ae.Status != status {
		t.Fatalf("要 %d 的 api 错误，拿到 %v", status, err)
	}
	text := ae.Message
	for _, fs := range ae.Fields {
		text += strings.Join(fs, "")
	}
	if msg != "" && !strings.Contains(text, msg) {
		t.Fatalf("文案 %q 里没有 %q", text, msg)
	}
}

func (e *env) group(ctx *app.Ctx, name string) *Group {
	e.t.Helper()
	g, err := e.svc.CreateGroup(ctx)
	if err != nil {
		e.t.Fatal(err)
	}
	if _, err := e.svc.UpdateGroup(ctx, g.ID, g.Version, GroupChanges{Name: &name}); err != nil {
		e.t.Fatal(err)
	}
	return g
}

// 契约 R236：已加入 = 账号启用且至少一个已验证邮箱；成员墙、主页、分组选人都基于它
func TestJoinedUsersOnly(t *testing.T) {
	e := newEnv(t)
	ok := e.user("正常")
	unverified := e.user("没验证")
	e.exec(`UPDATE users SET email_verified_at = NULL WHERE id = ?`, unverified)
	stopped := e.user("已停用")
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, stopped)

	res, err := e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if err != nil {
		t.Fatal(err)
	}
	if res.Total != 1 || len(res.Members) != 1 || res.Members[0].UserID != ok {
		t.Fatalf("成员墙只该有已加入的人：%+v", res.Members)
	}
	for _, id := range []int64{unverified, stopped} {
		_, err := e.svc.Detail(e.ctx(ok, false), id)
		wantStatus(t, err, http.StatusNotFound, "没有这位成员")
	}
	if _, err := e.svc.Detail(e.ctx(ok, false), ok); err != nil {
		t.Fatal(err)
	}

	// 后台加人也只能加已加入的
	ed := e.editor()
	g := e.group(ed, "干部")
	for _, id := range []int64{unverified, stopped} {
		_, err := e.svc.AddMember(ed, g.ID, id)
		wantStatus(t, err, http.StatusUnprocessableEntity, "只能加已加入的用户")
	}
	if _, err := e.svc.AddMember(ed, g.ID, ok); err != nil {
		t.Fatal(err)
	}
	// 进了组的人之后被停用：不在成员墙分组里，组管理页里标出
	e.exec(`UPDATE users SET is_active = 0 WHERE id = ?`, ok)
	res, _ = e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if len(res.Sections) != 1 || len(res.Sections[0].Entries) != 0 {
		t.Fatalf("停用的人不该出现在分组里：%+v", res.Sections)
	}
	d, _ := e.svc.GetGroup(ed, g.ID)
	if len(d.Members) != 1 || d.Members[0].Joined {
		t.Fatalf("后台应标出这个人已不算加入：%+v", d.Members)
	}
}

// 契约 R237：职务合起来 ≤20 字、每个 ≤10 字，多个职务可用多种分隔符
func TestTitleLimits(t *testing.T) {
	e := newEnv(t)
	ed := e.editor()
	g := e.group(ed, "干部")
	u := e.user("甲")
	d, err := e.svc.AddMember(ed, g.ID, u)
	if err != nil {
		t.Fatal(err)
	}
	mid := d.Members[0].ID

	if got := SplitTitles("社长、主播/解说，副社长；  "); strings.Join(got, "|") != "社长|主播|解说|副社长" {
		t.Fatalf("拆分不对：%v", got)
	}
	ok := strings.Repeat("长", 10) + "、" + strings.Repeat("长", 9) // 20 个字符，每个 ≤10
	if _, err := e.svc.SetTitle(ed, mid, ok); err != nil {
		t.Fatalf("20 字且每个 ≤10 应合法：%v", err)
	}
	_, err = e.svc.SetTitle(ed, mid, strings.Repeat("长", 11))
	wantStatus(t, err, http.StatusUnprocessableEntity, "每个职务最多 10 字")
	_, err = e.svc.SetTitle(ed, mid, strings.Repeat("长", 10)+"、"+strings.Repeat("长", 10)) // 21 个字符
	wantStatus(t, err, http.StatusUnprocessableEntity, "合起来最多 20 字")
	if got := e.count(`SELECT COUNT(*) FROM member_group_memberships WHERE title = ?`, ok); got != 1 {
		t.Fatal("被拒的职务不该改掉原来的")
	}
}

// 契约 R237：后台按昵称搜人最多 10 条，排除已在组内的；邮箱只有超管能搜、能看
func TestSearchPeople(t *testing.T) {
	e := newEnv(t)
	ed := e.editor()
	g := e.group(ed, "干部")
	var ids []int64
	for i := 0; i < 14; i++ {
		ids = append(ids, e.user(fmt.Sprintf("选手%02d", i)))
	}
	got, err := e.svc.SearchPeople(ed, g.ID, "选手")
	if err != nil || len(got) != SearchLimit {
		t.Fatalf("最多 10 条：%d %v", len(got), err)
	}
	if _, err := e.svc.AddMember(ed, g.ID, ids[0]); err != nil {
		t.Fatal(err)
	}
	got, _ = e.svc.SearchPeople(ed, g.ID, "选手00")
	if len(got) != 0 {
		t.Fatalf("已在组内的不该再搜出来：%+v", got)
	}
	// 通配符按字面算
	if got, _ := e.svc.SearchPeople(ed, g.ID, "%"); len(got) != 0 {
		t.Fatalf("百分号不该当通配符：%+v", got)
	}
	if got, _ := e.svc.SearchPeople(ed, g.ID, "  "); len(got) != 0 {
		t.Fatal("空查询返回空")
	}
	// 内容编辑搜邮箱特征不到人也看不到邮箱（216 A2）
	if got, _ := e.svc.SearchPeople(ed, g.ID, "@sjtu"); len(got) != 0 {
		t.Fatalf("内容编辑不能按邮箱搜：%+v", got)
	}
	got, _ = e.svc.SearchPeople(ed, g.ID, "选手01")
	if len(got) != 1 || got[0].Email != "" {
		t.Fatalf("内容编辑看不到邮箱：%+v", got)
	}
	super := e.ctx(e.user("超管"), true)
	got, _ = e.svc.SearchPeople(super, g.ID, "@sjtu")
	if len(got) != SearchLimit || got[0].Email == "" {
		t.Fatalf("超管可以按邮箱搜、也看得到：%d %+v", len(got), got)
	}
	// 没有能力的人不能搜
	_, err = e.svc.SearchPeople(e.ctx(ids[1], false), g.ID, "选手")
	wantStatus(t, err, http.StatusForbidden, "")
	_, err = e.svc.SearchPeople(&app.Ctx{Context: context.Background(), Clock: clock.System{}}, g.ID, "选手")
	wantStatus(t, err, http.StatusUnauthorized, "")
}

// 设计 6.2：新分组先是空名（不显示），首次保存名字后才上墙；组名不分大小写唯一；落后版本 409
func TestGroupLifecycle(t *testing.T) {
	e := newEnv(t)
	ed := e.editor()
	g, err := e.svc.CreateGroup(ed)
	if err != nil || g.Name != "" || g.Version != 1 {
		t.Fatalf("新组应是空名：%+v %v", g, err)
	}
	res, _ := e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if len(res.Sections) != 0 {
		t.Fatal("没起名的分组不上墙")
	}
	name := "Staff"
	out, err := e.svc.UpdateGroup(ed, g.ID, 1, GroupChanges{Name: &name})
	if err != nil || out.Version != 2 || len(out.Saved) != 1 {
		t.Fatalf("起名失败：%+v %v", out, err)
	}
	res, _ = e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if len(res.Sections) != 1 || res.Sections[0].Name != "Staff" {
		t.Fatalf("起名后上墙：%+v", res.Sections)
	}
	// 重名（不分大小写）：只报这个字段，别的字段照存
	g2, _ := e.svc.CreateGroup(ed)
	dup, desc := "sTAFF", "第二组"
	out, err = e.svc.UpdateGroup(ed, g2.ID, 1, GroupChanges{Name: &dup, Description: &desc})
	if err != nil || out.Fields["name"] == nil || len(out.Saved) != 1 || out.Saved[0] != "description" {
		t.Fatalf("重名应只拦名字：%+v %v", out, err)
	}
	// 字数
	long := strings.Repeat("长", 21)
	out, _ = e.svc.UpdateGroup(ed, g2.ID, out.Version, GroupChanges{Name: &long})
	if out.Fields["name"] == nil {
		t.Fatal("名称超过 20 字应报错")
	}
	// 落后版本号
	_, err = e.svc.UpdateGroup(ed, g.ID, 1, GroupChanges{Description: &desc})
	wantStatus(t, err, http.StatusConflict, "另一个人刚改过")
	// 隐藏
	hide := false
	if _, err := e.svc.UpdateGroup(ed, g.ID, 2, GroupChanges{IsVisible: &hide}); err != nil {
		t.Fatal(err)
	}
	res, _ = e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if len(res.Sections) != 0 {
		t.Fatal("不显示的分组不上墙")
	}
	// 删除
	if err := e.svc.DeleteGroup(ed, g.ID); err != nil {
		t.Fatal(err)
	}
	wantStatus(t, e.svc.DeleteGroup(ed, g.ID), http.StatusNotFound, "")
	// 没有能力
	_, err = e.svc.CreateGroup(e.ctx(e.user("路人"), false))
	wantStatus(t, err, http.StatusForbidden, "")
}

// 成员墙：分组按 sort_order，组内按顺序，职务为空时用分组名当标签；加入序号不随筛选变
func TestShowcaseLayout(t *testing.T) {
	e := newEnv(t)
	ed := e.editor() // 这个人也是已加入的成员，序号 1
	a, b, c := e.user("甲"), e.user("乙"), e.user("丙")
	e.exec(`UPDATE users SET main_role = 'tank' WHERE id IN (?, ?)`, a, b)
	e.exec(`UPDATE users SET flex_roles = 'support,damage' WHERE id = ?`, a)

	g1 := e.group(ed, "社团干部")
	g2 := e.group(ed, "解说")
	zero := 5
	e.svc.UpdateGroup(ed, g1.ID, 2, GroupChanges{SortOrder: &zero})
	one := 1
	e.svc.UpdateGroup(ed, g2.ID, 2, GroupChanges{SortOrder: &one})
	for _, id := range []int64{a, b} {
		if _, err := e.svc.AddMember(ed, g1.ID, id); err != nil {
			t.Fatal(err)
		}
	}
	d2, _ := e.svc.AddMember(ed, g2.ID, a)
	if _, err := e.svc.SetTitle(ed, d2.Members[0].ID, "主播、解说"); err != nil {
		t.Fatal(err)
	}

	res, err := e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	if err != nil {
		t.Fatal(err)
	}
	if len(res.Sections) != 2 || res.Sections[0].Name != "解说" || res.Sections[1].Name != "社团干部" {
		t.Fatalf("分组应按排序：%+v", res.Sections)
	}
	if res.Total != 4 || res.Members[0].Number != 1 || res.Members[3].UserID != c {
		t.Fatalf("先加入的在前，序号从 1 起：%+v", res.Members)
	}
	var ca Card
	for _, m := range res.Members {
		if m.UserID == a {
			ca = m
		}
	}
	if strings.Join(ca.Titles, "|") != "主播|解说" || strings.Join(ca.Groups, "|") != "解说|社团干部" {
		t.Fatalf("甲的职务和分组：%+v", ca)
	}
	if got := strings.Join(ca.Tags(), "|"); got != "主播|解说" {
		t.Fatalf("有职务时标签是职务：%s", got)
	}
	var cb Card
	for _, m := range res.Members {
		if m.UserID == b {
			cb = m
		}
	}
	if got := strings.Join(cb.Tags(), "|"); got != "社团干部" {
		t.Fatalf("没有职务时标签退回分组名：%s", got)
	}
	if strings.Join(ca.Roles, ",") != "tank,damage,support" || ca.MainRole != "tank" {
		t.Fatalf("公开位置主位置在前：%+v", ca)
	}
	// 筛选：按常用位置
	tank, _ := e.svc.Showcase(context.Background(), ShowcaseInput{Role: "tank"}, t0)
	if len(tank.Members) != 2 || !tank.Filtering || tank.Members[1].Number != 3 {
		t.Fatalf("缺坦克筛选，序号不变：%+v", tank.Members)
	}
	// 只看没队的人：把甲放进一支队
	e.exec(`INSERT INTO teams (id, name, created_at, updated_at) VALUES (1, '战队', 'x', 'x')`)
	e.exec(`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (1, ?, 'captain', 'x')`, a)
	free, _ := e.svc.Showcase(context.Background(), ShowcaseInput{Free: true}, t0)
	for _, m := range free.Members {
		if m.UserID == a {
			t.Fatal("在队里的人不该出现在「只看没队的」")
		}
	}
	if len(free.Members) != 3 {
		t.Fatalf("应有 3 个没队的人：%d", len(free.Members))
	}
	all, _ := e.svc.Showcase(context.Background(), ShowcaseInput{}, t0)
	for _, m := range all.Members {
		if m.UserID == a && (len(m.Teams) != 1 || m.Teams[0].Name != "战队") {
			t.Fatalf("成员卡应带所在战队：%+v", m)
		}
	}
}

// 组内排序：上移下移，序号重排，到头不动；删人后空档合上
func TestMoveAndRemoveMembers(t *testing.T) {
	e := newEnv(t)
	ed := e.editor()
	g := e.group(ed, "排序组")
	var ids []int64
	for _, n := range []string{"甲", "乙", "丙"} {
		u := e.user(n)
		ids = append(ids, u)
		if _, err := e.svc.AddMember(ed, g.ID, u); err != nil {
			t.Fatal(err)
		}
	}
	_, err := e.svc.AddMember(ed, g.ID, ids[0])
	wantStatus(t, err, http.StatusUnprocessableEntity, "已经在这个分组里")

	order := func() string {
		d, _ := e.svc.GetGroup(ed, g.ID)
		var out []string
		for _, m := range d.Members {
			out = append(out, fmt.Sprintf("%s%d", m.Nickname, m.SortOrder))
		}
		return strings.Join(out, " ")
	}
	d, _ := e.svc.GetGroup(ed, g.ID)
	third := d.Members[2].ID
	if _, err := e.svc.MoveMember(ed, third, -1); err != nil {
		t.Fatal(err)
	}
	if got := order(); got != "甲0 丙1 乙2" {
		t.Fatalf("上移后：%s", got)
	}
	e.svc.MoveMember(ed, third, -1)
	e.svc.MoveMember(ed, third, -1) // 已经在头：不动
	if got := order(); got != "丙0 甲1 乙2" {
		t.Fatalf("到头不动：%s", got)
	}
	_, err = e.svc.MoveMember(ed, third, 2)
	wantStatus(t, err, http.StatusUnprocessableEntity, "")
	if _, err := e.svc.RemoveMember(ed, d.Members[0].ID); err != nil { // 删掉甲
		t.Fatal(err)
	}
	if got := order(); got != "丙0 乙2" { // 删人只删，留下空档，下一次移动时才重新编号
		t.Fatalf("删人后：%s", got)
	}
	e.svc.MoveMember(ed, third, 1)
	if got := order(); got != "乙0 丙1" {
		t.Fatalf("删人后重排并下移：%s", got)
	}
}

// 设计 6.4：成员主页只放公开的东西；退出的战队、文章、所在分组
func TestMemberPage(t *testing.T) {
	e := newEnv(t)
	ed := e.editor()
	u := e.user("主角")
	e.exec(`UPDATE users SET motto = '一句话', show_rank = 1, main_role = 'damage' WHERE id = ?`, u)
	e.exec(`INSERT INTO teams (id, name, created_at, updated_at) VALUES (1, '现队', 'x', 'x'), (2, '旧队', 'x', 'x')`)
	e.exec(`INSERT INTO team_memberships (team_id, user_id, role, joined_at) VALUES (1, ?, 'member', 'x')`, u)
	e.exec(`INSERT INTO team_alumni (team_id, user_id, role, joined_at, left_at, reason) VALUES (2, ?, 'member', ?, ?, 'left')`,
		u, db.FormatUTC(t0), db.FormatUTC(t0))
	for i := 0; i < 12; i++ {
		e.exec(`INSERT INTO pages (id, kind, slug, title, live, first_published_at, created_at, updated_at)
			VALUES (?, 'article', ?, ?, 1, ?, 'x', 'x')`, 100+i, fmt.Sprintf("a%d", i), fmt.Sprintf("文章%d", i),
			db.FormatUTC(t0.Add(time.Duration(i)*time.Hour)))
		e.exec(`INSERT INTO articles (page_id, author_id) VALUES (?, ?)`, 100+i, u)
	}
	e.exec(`UPDATE pages SET live = 0 WHERE id = 100`) // 草稿不算
	g := e.group(ed, "解说组")
	d, _ := e.svc.AddMember(ed, g.ID, u)
	e.svc.SetTitle(ed, d.Members[0].ID, "解说")

	page, err := e.svc.Detail(e.ctx(u, false), u)
	if err != nil {
		t.Fatal(err)
	}
	if !page.IsOwner || page.Card.Motto != "一句话" {
		t.Fatalf("本人页：%+v", page.Card)
	}
	if len(page.Teams) != 1 || page.Teams[0].Name != "现队" || len(page.Alumni) != 1 || page.Alumni[0].TeamName != "旧队" {
		t.Fatalf("战队与退役：%+v %+v", page.Teams, page.Alumni)
	}
	if page.ArticleCount != 11 || len(page.Articles) != ArticlesOnPage || page.Articles[0].Title != "文章11" {
		t.Fatalf("文章：%d %d %+v", page.ArticleCount, len(page.Articles), page.Articles)
	}
	if len(page.Groups) != 1 || page.Groups[0].Titles[0] != "解说" {
		t.Fatalf("分组：%+v", page.Groups)
	}
	other, _ := e.svc.Detail(&app.Ctx{Context: context.Background(), Clock: clock.System{}}, u)
	if other.IsOwner {
		t.Fatal("访客不是本人")
	}
	// 隐藏的分组不出现在主页
	hide := false
	e.svc.UpdateGroup(ed, g.ID, 2, GroupChanges{IsVisible: &hide})
	page, _ = e.svc.Detail(e.ctx(u, false), u)
	if len(page.Groups) != 0 {
		t.Fatalf("隐藏的分组不显示：%+v", page.Groups)
	}
}
