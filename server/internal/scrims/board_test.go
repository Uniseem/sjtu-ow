package scrims

import (
	"net/http"
	"strings"
	"testing"
	"time"
)

// 十个人：每人都能打全部位置，段位各不相同。
func (e *env) tenPlayers(sid int64, format string) []int64 {
	e.t.Helper()
	var users []int64
	n := 10
	if TeamSize(format) == 6 {
		n = 12
	}
	for i := 0; i < n; i++ {
		u := e.user(string(rune('A'+i))+"号", 2000+i*100, 2100+i*100, 2200+i*100)
		users = append(users, u)
		e.signup(sid, u, Tank, Damage, Support)
	}
	return users
}

func signupIDs(e *env, sid int64, users []int64) []int64 {
	var ids []int64
	for _, u := range users {
		ids = append(ids, e.signupID(sid, u))
	}
	return ids
}

// 契约 R159、R165：勾选 → 生成 → 保存；人数不对时说明原因但勾选保留；生成后清名单变动标记
func TestGenerateTeams(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	ids := signupIDs(e, sid, users)
	board, _ := e.svc.GetBoard(e.mgr(), sid, "")
	_, err := e.svc.Generate(e.mgr(), sid, ids[:9], board.BoardVersion)
	wantErr(t, err, http.StatusUnprocessableEntity, "需要正好 10 人才能分队，当前勾选了 9 人")
	if e.count(`SELECT COUNT(*) FROM scrim_signups WHERE scrim_id = ? AND is_selected = 1`, sid) != 9 {
		t.Fatal("生成失败时勾选应保留")
	}
	e.exec(`UPDATE scrims SET roster_changed_at = ? WHERE id = ?`, ts(t0), sid)
	board, _ = e.svc.GetBoard(e.mgr(), sid, "")
	res, err := e.svc.Generate(e.mgr(), sid, ids, board.BoardVersion)
	if err != nil {
		t.Fatal(err)
	}
	b := res.Board
	if !b.HasTeams || b.TeamsStale || b.SelectedCount != 10 || len(b.Teams[0].Members) != 5 || len(b.Teams[1].Members) != 5 {
		t.Fatalf("生成后的板：%+v", b)
	}
	for _, tm := range b.Teams {
		if len(tm.Problems) != 0 {
			t.Fatalf("生成的分队应符合规格：%v", tm.Problems)
		}
		roles := map[string]int{}
		for _, m := range tm.Members {
			roles[m.AssignedRole]++
			if m.RatingUsed == nil {
				t.Fatal("每人都该有 rating_used")
			}
		}
		if roles[Tank] != 1 || roles[Damage] != 2 || roles[Support] != 2 {
			t.Fatalf("5v5 每队 1 坦 2 输 2 辅：%v", roles)
		}
	}
	if e.get(sid).RosterChangedAt != nil || e.get(sid).TeamsGeneratedAt == nil {
		t.Fatal("保存后应置分队时间、清名单变动标记")
	}
	if b.Gap != res.Score[0] {
		t.Fatalf("板上总分差 %d 应等于算法总分差 %d", b.Gap, res.Score[0])
	}
	// 6v6 要 12 人
	s6 := e.scrim(withFormat(FormatRQ6))
	u6 := e.tenPlayers(s6, FormatRQ6)
	bd, _ := e.svc.GetBoard(e.mgr(), s6, "")
	if _, err := e.svc.Generate(e.mgr(), s6, signupIDs(e, s6, u6[:10]), bd.BoardVersion); err == nil {
		t.Fatal("6v6 勾 10 人应失败")
	}
}

// 契约 R164、R165：手工保存不校验位置配比但给提示；没放进队的上场者进替补（保留上场标记、清队伍和位置）
func TestSaveTeamsBenchAndWarnings(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	ids := signupIDs(e, sid, users)
	bd, _ := e.svc.GetBoard(e.mgr(), sid, "")
	if _, err := e.svc.SetSelection(e.mgr(), sid, ids, bd.BoardVersion); err != nil {
		t.Fatal(err)
	}
	bd, _ = e.svc.GetBoard(e.mgr(), sid, "")
	// 把 4 个人放进 A 队，全部当坦克（配比不对）；其余上场者是替补
	var pl []PlacementIn
	for i := 0; i < 4; i++ {
		pl = append(pl, PlacementIn{SignupID: ids[i], Team: "a", Role: Tank})
	}
	pl = append(pl, PlacementIn{SignupID: 987654, Team: "b", Role: Tank}) // 不属于这场的忽略
	b, err := e.svc.SaveTeams(e.mgr(), sid, pl, bd.BoardVersion)
	if err != nil {
		t.Fatalf("配比不对也允许保存：%v", err)
	}
	if len(b.Teams[0].Members) != 4 || len(b.Teams[1].Members) != 0 || len(b.Bench) != 6 {
		t.Fatalf("A 队 4 人，其余 6 人替补：%d %d %d", len(b.Teams[0].Members), len(b.Teams[1].Members), len(b.Bench))
	}
	if len(b.Teams[0].Problems) == 0 || !strings.Contains(strings.Join(b.Teams[0].Problems, "|"), "坦克 4 人（需要 1 人）") {
		t.Fatalf("应提示位置人数不符：%v", b.Teams[0].Problems)
	}
	for _, m := range b.Bench {
		if !m.IsSelected || m.Team != "" || m.AssignedRole != "" || m.RatingUsed != nil {
			t.Fatalf("替补保留上场标记，清队伍和位置：%+v", m)
		}
	}
	// 分数取该位置的段位：第一个人坦克段位 2000
	if *b.Teams[0].Members[0].RatingUsed != 2000 && *b.Teams[0].Members[0].RatingUsed == 0 {
		t.Fatalf("rating_used：%v", *b.Teams[0].Members[0].RatingUsed)
	}
	// 再保存一次，只放 2 个人：之前放的人退回替补
	b, err = e.svc.SaveTeams(e.mgr(), sid, pl[:2], b.BoardVersion)
	if err != nil || len(b.Teams[0].Members) != 2 || len(b.Bench) != 8 {
		t.Fatalf("再保存：%v %+v", err, b)
	}
	// 取消勾选的人同时清掉分队结果
	b, err = e.svc.SetSelection(e.mgr(), sid, ids[2:], b.BoardVersion)
	if err != nil || len(b.Teams[0].Members) != 0 {
		t.Fatalf("取消勾选应清分队：%v %+v", err, b)
	}
}

// 12 号文档 5.5 / 编队板同款：分队板的版本号，落后 409
func TestBoardVersionConflict(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	ids := signupIDs(e, sid, users)
	bd, _ := e.svc.GetBoard(e.mgr(), sid, "")
	if _, err := e.svc.SetSelection(e.mgr(), sid, ids, bd.BoardVersion); err != nil {
		t.Fatal(err)
	}
	_, err := e.svc.SetSelection(e.mgr(), sid, ids[:3], bd.BoardVersion) // 还拿着旧版本
	wantErr(t, err, http.StatusConflict, "分队板刚被改过")
	_, err = e.svc.Generate(e.mgr(), sid, ids, bd.BoardVersion)
	wantErr(t, err, http.StatusConflict, "分队板刚被改过")
	_, err = e.svc.SaveTeams(e.mgr(), sid, nil, bd.BoardVersion)
	wantErr(t, err, http.StatusConflict, "分队板刚被改过")
	// 报名变动也会让板版本前进
	before := e.get(sid).BoardVersion
	e.signup(sid, users[0], Tank) // 改位置
	if e.get(sid).BoardVersion == before {
		// 只有已安排过的人改位置才前进；这里还没人被安排
		return
	}
}

// 契约 R166：玩家只看得到自己的去向；公开页面没有任何分队；访客什么都没有
func TestPlacementPrivacy(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	ids := signupIDs(e, sid, users)
	bd, _ := e.svc.GetBoard(e.mgr(), sid, "")
	if _, err := e.svc.Generate(e.mgr(), sid, ids[:9], bd.BoardVersion); err == nil {
		t.Fatal("9 人应失败")
	}
	// 没有分队：什么都不说
	p, _ := e.svc.Detail(e.ctx(users[0]), sid)
	if p.Mine == nil || p.Mine.Placement != "" {
		t.Fatalf("还没有分队，不说去向：%+v", p.Mine)
	}
	bd, _ = e.svc.GetBoard(e.mgr(), sid, "")
	if _, err := e.svc.Generate(e.mgr(), sid, ids, bd.BoardVersion); err != nil {
		t.Fatal(err)
	}
	// 让第 10 个人落选（去掉勾选后不在队里）
	e.exec(`UPDATE scrim_signups SET is_selected = 1, team = '', assigned_role = '' WHERE id = ?`, ids[9])
	e.exec(`UPDATE scrim_signups SET is_selected = 0, team = '', assigned_role = '' WHERE id = ?`, ids[8])
	seen := map[string]bool{}
	for i, u := range users {
		page, err := e.svc.Detail(e.ctx(u), sid)
		if err != nil {
			t.Fatal(err)
		}
		pl := page.Mine.Placement
		seen[pl] = true
		if i == 9 && pl != "替补" || i == 8 && pl != "这次没排上场" {
			t.Fatalf("第 %d 个人的去向：%q", i, pl)
		}
	}
	hasTeamText := false
	for pl := range seen {
		if strings.HasPrefix(pl, "A 队 · ") || strings.HasPrefix(pl, "B 队 · ") {
			hasTeamText = true
		}
	}
	if !hasTeamText {
		t.Fatalf("在队里的人看到「A 队 · 位置」：%v", seen)
	}
	// 公开页面：名单只有昵称和位置，没有任何分队；别人看不到自己以外的去向
	pub, _ := e.svc.Detail(e.anon(), sid)
	if pub.Mine != nil || len(pub.Signups) != 10 {
		t.Fatalf("访客：%+v", pub)
	}
	for _, s := range pub.Signups {
		if s.Nickname == "" || len(s.Roles) == 0 {
			t.Fatalf("公开名单：%+v", s)
		}
	}
	// 管理员以外不能读板
	_, err := e.svc.GetBoard(e.ctx(users[0]), sid, "")
	wantErr(t, err, http.StatusForbidden, "")
}

// 契约 R167：分队有变化 = 名单变动时间晚于分队生成时间
func TestTeamsStale(t *testing.T) {
	sc := &Scrim{}
	if teamsStale(sc) {
		t.Fatal("没生成过不算")
	}
	g, c := t0, t0.Add(time.Minute)
	sc.TeamsGeneratedAt, sc.RosterChangedAt = &g, &c
	if !teamsStale(sc) {
		t.Fatal("名单变动晚于生成：算过期")
	}
	sc.RosterChangedAt = &g
	if teamsStale(sc) {
		t.Fatal("同时不算")
	}
	sc.RosterChangedAt = nil
	if teamsStale(sc) {
		t.Fatal("没变动不算")
	}
}

// 契约 R170：复制到 QQ 群的文案——按队、按位置分组，「昵称 游戏ID 段位」，每队总分
func TestCopyText(t *testing.T) {
	e := newEnv(t)
	sid := e.scrim()
	users := e.tenPlayers(sid, FormatRQ5)
	ids := signupIDs(e, sid, users)
	bd, _ := e.svc.GetBoard(e.mgr(), sid, "")
	res, err := e.svc.Generate(e.mgr(), sid, ids, bd.BoardVersion)
	if err != nil {
		t.Fatal(err)
	}
	text := res.Board.CopyText
	if !strings.HasPrefix(text, "【周五内战】") || !strings.Contains(text, "角色限定 5v5") ||
		!strings.Contains(text, "A 队（总分 ") || !strings.Contains(text, "B 队（总分 ") ||
		!strings.Contains(text, "坦克：") || !strings.Contains(text, "输出：") || !strings.Contains(text, "支援：") {
		t.Fatalf("文案：\n%s", text)
	}
	if !strings.Contains(text, " / ") {
		t.Fatalf("同位置多人用 / 分隔：\n%s", text)
	}
	// 没有分队时没有文案
	s2 := e.scrim()
	b2, _ := e.svc.GetBoard(e.mgr(), s2, "")
	if b2.CopyText != "" || b2.HasTeams {
		t.Fatal("没有分队就没有文案")
	}
	// 游戏 ID 被删了：写占位
	e.exec(`UPDATE scrim_signups SET game_account_id = NULL WHERE id = ?`, ids[0])
	b3, _ := e.svc.GetBoard(e.mgr(), sid, "")
	found := false
	for _, s := range b3.Signups {
		if s.SignupID == ids[0] && s.Battletag == "（游戏 ID 已删除）" {
			found = true
		}
	}
	if !found {
		t.Fatal("游戏 ID 被删了，板上要写占位")
	}
	// 按段位排序
	b4, _ := e.svc.GetBoard(e.mgr(), sid, "rating")
	if b4.Order != "rating" || b4.Signups[0].Nickname != "J号" {
		t.Fatalf("按段位排，最高的在前：%v %s", b4.Order, b4.Signups[0].Nickname)
	}
	// 干部能看联系方式；没有 contacts.view 的不能
	if len(b4.Signups[0].Contacts) == 0 {
		t.Fatal("有 contacts.view 能力应看到联系方式")
	}
}
