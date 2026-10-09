package tournaments

import (
	"net/http"
	"strings"
	"testing"
	"time"
)

func (e *env) draft() *Tournament {
	e.t.Helper()
	t, err := e.svc.CreateTournament(e.mgr())
	if err != nil {
		e.t.Fatal(err)
	}
	return t
}

func (e *env) patch(t *Tournament, ch Changes) *SaveResult {
	e.t.Helper()
	var v int64
	if err := e.d.ReadPool().QueryRow(`SELECT version FROM tournaments WHERE id = ?`, t.ID).Scan(&v); err != nil {
		e.t.Fatal(err)
	}
	r, err := e.svc.UpdateTournament(e.mgr(), t.ID, v, ch)
	if err != nil {
		e.t.Fatal(err)
	}
	return r
}

// 契约 R109、R110：发布门槛；已取消不能发布；只有已发布的能标结束；没填好的草稿不能取消；发布过的不能删
func TestPublishCancelFinishDelete(t *testing.T) {
	e := newEnv(t)
	d := e.draft()
	_, err := e.svc.Publish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "标题、报名开始时间、报名截止时间")
	_, err = e.svc.Cancel(e.mgr(), d.ID, "")
	wantErr(t, err, http.StatusConflict, "直接删除")
	_, err = e.svc.Finish(e.mgr(), d.ID)
	wantErr(t, err, http.StatusConflict, "只有已发布")

	res := e.patch(d, Changes{Title: str("春季赛"), RegistrationOpensAt: rfc(t0), RegistrationClosesAt: rfc(t0.Add(-time.Hour))})
	if res.Fields["registration_closes_at"] == nil {
		t.Fatalf("截止不晚于开始应报错：%+v", res)
	}
	res = e.patch(d, Changes{RegistrationOpensAt: rfc(t0), RegistrationClosesAt: rfc(t0.Add(time.Hour))})
	if res.Fields != nil || len(res.Saved) != 2 {
		t.Fatalf("合法的时间应存下：%+v", res)
	}
	pub, err := e.svc.Publish(e.mgr(), d.ID)
	if err != nil || pub.Status != StatusPublished || pub.PublishedAt == nil {
		t.Fatalf("发布失败：%+v %v", pub, err)
	}
	wantErr(t, e.svc.DeleteTournament(e.mgr(), d.ID), http.StatusConflict, "只能取消")
	if _, err := e.svc.Finish(e.mgr(), d.ID); err != nil {
		t.Fatal(err)
	}
	// 已结束的还能再发布吗？现行站允许（只拦已取消的）；已取消的不行
	c := e.draft()
	e.patch(c, Changes{Title: str("要取消的"), RegistrationOpensAt: rfc(t0), RegistrationClosesAt: rfc(t0.Add(time.Hour))})
	if _, err := e.svc.Cancel(e.mgr(), c.ID, "场地没了"); err != nil {
		t.Fatalf("填好的草稿可以取消：%v", err)
	}
	_, err = e.svc.Publish(e.mgr(), c.ID)
	wantErr(t, err, http.StatusConflict, "已取消的赛事不能再发布")
	_, err = e.svc.Cancel(e.mgr(), c.ID, "")
	wantErr(t, err, http.StatusConflict, "已经取消了")

	// 没发布过的草稿可以删
	x := e.draft()
	if err := e.svc.DeleteTournament(e.mgr(), x.ID); err != nil {
		t.Fatalf("草稿可以删：%v", err)
	}
	// 没有能力的人
	_, err = e.svc.CreateTournament(e.ctx(1))
	wantErr(t, err, http.StatusForbidden, "")
}

// 契约 R111、R112：报名方式有任何报名（含散人池）后锁死；自动通过有任何队报名后锁死（散人池不算）
func TestModeAndAutoApproveLocks(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	tid := e.tour(withMode(ModeIndividual))
	tt := &Tournament{ID: tid}
	if _, err := e.svc.SignUpIndividual(e.ctx(a), SignupInput{TournamentID: tid, GameAccountID: e.firstAccount(a), Roles: []string{"tank"}}); err != nil {
		t.Fatal(err)
	}
	res := e.patch(tt, Changes{RegistrationMode: str(ModeTeam)})
	if res.Fields["registration_mode"] == nil {
		t.Fatalf("有个人报名后报名方式应锁死：%+v", res)
	}
	// 自动通过：只有「队」的报名锁；散人池不锁
	res = e.patch(tt, Changes{AutoApprove: flag(true)})
	if res.Fields != nil || len(res.Saved) != 1 {
		t.Fatalf("只有个人报名时自动通过还能改：%+v", res)
	}
	// 整队赛事：有队报名后两个都锁
	t2 := e.tour()
	team := e.team("甲队", a, b)
	e.register(t2, team, a)
	res = e.patch(&Tournament{ID: t2}, Changes{AutoApprove: flag(true), RegistrationMode: str(ModeIndividual)})
	if res.Fields["auto_approve"] == nil || res.Fields["registration_mode"] == nil {
		t.Fatalf("有队报名后两项都锁：%+v", res)
	}
}

func (e *env) firstAccount(uid int64) int64 {
	var id int64
	if err := e.d.ReadPool().QueryRow(`SELECT id FROM game_accounts WHERE user_id = ? ORDER BY id LIMIT 1`, uid).Scan(&id); err != nil {
		e.t.Fatal(err)
	}
	return id
}

// 契约 R113：整队模式的人数下限不能超过全站战队人数上限；下限≥1、上限≤20、下限≤上限；一组里出错整组不存
func TestRosterBounds(t *testing.T) {
	e := newEnv(t)
	tt := &Tournament{ID: e.tour(withMode(ModeTeam))}
	for name, ch := range map[string]Changes{
		"下限 0":   {RosterMin: num(0)},
		"上限 21":  {RosterMax: num(21)},
		"下限>上限":  {RosterMin: num(5), RosterMax: num(3)},
		"超过战队上限": {RosterMin: num(11), RosterMax: num(20)},
	} {
		res := e.patch(tt, ch)
		if res.Fields == nil || len(res.Saved) != 0 {
			t.Fatalf("%s 应整组不存：%+v", name, res)
		}
	}
	// 个人报名不受战队上限约束（临时队伍不受限，119 轮）
	ind := &Tournament{ID: e.tour(withMode(ModeIndividual))}
	if res := e.patch(ind, Changes{RosterMin: num(11), RosterMax: num(20)}); res.Fields != nil {
		t.Fatalf("个人报名不受战队上限约束：%+v", res)
	}
	// 合法的两个一起存
	if res := e.patch(tt, Changes{RosterMin: num(3), RosterMax: num(4)}); len(res.Saved) != 2 {
		t.Fatalf("合法的应存下：%+v", res)
	}
	// 全站上限改小后，整队的下限就超了
	e.exec(`UPDATE site_settings SET team_max_members = 2 WHERE id = 1`)
	if res := e.patch(tt, Changes{RosterMin: num(3)}); res.Fields["roster_min"] == nil {
		t.Fatalf("下限 3 超过全站上限 2 应报错：%+v", res)
	}
}

// 契约 R114：赛事说明非空时每次变更送审
func TestDescriptionGoesToModeration(t *testing.T) {
	e := newEnv(t)
	s := &sink{}
	e.svc.SetModeration(s)
	d := e.draft()
	e.patch(d, Changes{Title: str("只改标题")})
	if len(s.got) != 0 {
		t.Fatalf("没改说明不该送审：%v", s.got)
	}
	e.patch(d, Changes{Description: str("# 说明\n正文")})
	if len(s.got) != 1 || !strings.HasPrefix(s.got[0], "tournament_description#") {
		t.Fatalf("改了说明应送审：%v", s.got)
	}
	e.patch(d, Changes{Description: str("")})
	if len(s.got) != 1 {
		t.Fatalf("说明清空不送审：%v", s.got)
	}
}

// 契约 R136：改期只对已发布、新时间在未来且变了的触发；保留最早的旧时间，改回则清；清提醒标记
func TestTimeChange(t *testing.T) {
	e := newEnv(t)
	tid := e.tour()
	tt := &Tournament{ID: tid}
	e.exec(`UPDATE tournaments SET reminder_sent_at = ? WHERE id = ?`, ts(t0), tid)
	orig := t0.Add(10 * 24 * time.Hour)
	moved := orig.Add(48 * time.Hour)

	e.patch(tt, Changes{StartsAt: rfc(moved)})
	got, _ := GetTournament(e.mgr().Context, e.d.ReadPool(), tid)
	if got.MovedFrom == nil || !got.MovedFrom.Equal(orig) || got.ReminderSentAt != nil {
		t.Fatalf("改期应记旧时间并清提醒标记：%+v", got)
	}
	e.patch(tt, Changes{StartsAt: rfc(moved.Add(24 * time.Hour))})
	got, _ = GetTournament(e.mgr().Context, e.d.ReadPool(), tid)
	if got.MovedFrom == nil || !got.MovedFrom.Equal(orig) {
		t.Fatalf("多次移动保留最早那次：%v", got.MovedFrom)
	}
	e.patch(tt, Changes{StartsAt: rfc(orig)})
	got, _ = GetTournament(e.mgr().Context, e.d.ReadPool(), tid)
	if got.MovedFrom != nil {
		t.Fatalf("改回原时间应清空：%v", got.MovedFrom)
	}
	// 新时间已过：不触发
	e.patch(tt, Changes{StartsAt: rfc(t0.Add(-time.Hour))})
	got, _ = GetTournament(e.mgr().Context, e.d.ReadPool(), tid)
	if got.MovedFrom != nil {
		t.Fatalf("改到过去不触发：%v", got.MovedFrom)
	}
	// 草稿：不触发
	d := e.draft()
	e.patch(d, Changes{StartsAt: rfc(orig)})
	e.patch(d, Changes{StartsAt: rfc(moved)})
	got, _ = GetTournament(e.mgr().Context, e.d.ReadPool(), d.ID)
	if got.MovedFrom != nil {
		t.Fatalf("草稿改期不触发：%v", got.MovedFrom)
	}
}

// 契约 R137：「通知报名的人」写明原来和现在的时间，可附说明，发出后清 moved_from；收件人是有效名单和散人池各一次
func TestNotifyParticipants(t *testing.T) {
	e := newEnv(t)
	a, b, c, outsider := e.user("甲"), e.user("乙"), e.user("丙"), e.user("路人")
	_ = outsider
	tid := e.tour(withMode(ModeTeam))
	team := e.team("甲队", a, b)
	reg := e.register(tid, team, a)
	// 散人池里再加一个（个人报名在整队赛事里不允许，直接插库）
	e.exec(`INSERT INTO individual_signups (tournament_id, user_id, role_tank, created_at, updated_at) VALUES (?, ?, 1, ?, ?)`, tid, c, ts(t0), ts(t0))
	orig := t0.Add(10 * 24 * time.Hour)
	e.patch(&Tournament{ID: tid}, Changes{StartsAt: rfc(orig.Add(24 * time.Hour))})
	e.clearMails()
	n, err := e.svc.NotifyParticipants(e.mgr(), tid, "改到周日")
	if err != nil || n != 3 {
		t.Fatalf("名单 2 人 + 散人池 1 人 = 3：%d %v", n, err)
	}
	mail := e.mailsTo(a)
	if len(mail) != 1 || !strings.Contains(mail[0], "的比赛时间改了：原来") || !strings.Contains(mail[0], "改到周日") {
		t.Fatalf("信的内容：%v", mail)
	}
	if len(e.mailsTo(outsider)) != 0 {
		t.Fatal("没报名的人不该收到")
	}
	got, _ := GetTournament(e.mgr().Context, e.d.ReadPool(), tid)
	if got.MovedFrom != nil {
		t.Fatal("通知后应清 moved_from")
	}
	// 被驳回的队伍不算参赛的人
	_, _ = e.svc.Reject(e.mgr(), reg.ID, "名单有误")
	e.clearMails()
	if n, _ := e.svc.NotifyParticipants(e.mgr(), tid, ""); n != 1 {
		t.Fatalf("驳回后只剩散人池 1 人：%d", n)
	}
	// 说明太长
	_, err = e.svc.NotifyParticipants(e.mgr(), tid, strings.Repeat("长", 501))
	wantErr(t, err, http.StatusUnprocessableEntity, "最多 500")
	// 草稿不能通知
	d := e.draft()
	_, err = e.svc.NotifyParticipants(e.mgr(), d.ID, "")
	wantErr(t, err, http.StatusConflict, "只有已发布")
}

// 契约 R138、R139、R140：开赛前 24 小时提醒一次；时间后移自我顺延；窗口内刚保存的至少等 10 分钟；没人通过不标记；散人池要有人通过后才收到
func TestReminders(t *testing.T) {
	e := newEnv(t)
	a, b, pool := e.user("甲"), e.user("乙"), e.user("池中")
	start := t0.Add(30 * time.Hour)
	tid := e.tour(withMode(ModeTeam), withStart(start), withContact("QQ 群 777"))
	e.exec(`INSERT INTO individual_signups (tournament_id, user_id, role_tank, created_at, updated_at) VALUES (?, ?, 1, ?, ?)`, tid, pool, ts(t0), ts(t0))
	team := e.team("甲队", a, b)
	reg := e.register(tid, team, a)
	ctx := e.mgr().Context
	e.exec(`UPDATE tournaments SET updated_at = ? WHERE id = ?`, ts(t0.Add(-time.Hour)), tid)

	// 还没到 24 小时前的窗口
	if n, _ := e.svc.SendDueReminders(ctx, t0); n != 0 {
		t.Fatalf("还没到窗口：%d", n)
	}
	// 进窗口，但报名还是待审：没人通过，不标记
	now := t0.Add(7 * time.Hour)
	e.exec(`UPDATE tournaments SET updated_at = ? WHERE id = ?`, ts(t0), tid)
	if n, _ := e.svc.SendDueReminders(ctx, now); n != 0 {
		t.Fatalf("没有已通过的报名，不发：%d", n)
	}
	got, _ := GetTournament(ctx, e.d.ReadPool(), tid)
	if got.ReminderSentAt != nil {
		t.Fatal("没发出去就不能标记已发")
	}
	if _, err := e.svc.Approve(e.mgr(), reg.ID); err != nil {
		t.Fatal(err)
	}
	e.clearMails()
	// 刚保存过：窗口内至少等 10 分钟
	e.exec(`UPDATE tournaments SET updated_at = ? WHERE id = ?`, ts(now.Add(-5*time.Minute)), tid)
	if n, _ := e.svc.SendDueReminders(ctx, now); n != 0 {
		t.Fatalf("刚保存 5 分钟，还要再等：%d", n)
	}
	e.exec(`UPDATE tournaments SET updated_at = ? WHERE id = ?`, ts(now.Add(-11*time.Minute)), tid)
	n, err := e.svc.SendDueReminders(ctx, now)
	if err != nil || n != 3 {
		t.Fatalf("两个队员 + 一个散人池 = 3 封：%d %v", n, err)
	}
	m := e.mailsTo(a)
	if len(m) != 1 || !strings.Contains(m[0], "赛事提醒") || !strings.Contains(m[0], "QQ 群 777") || !strings.Contains(m[0], "P1#1000") {
		t.Fatalf("提醒信：%v", m)
	}
	if len(e.mailsTo(pool)) != 1 {
		t.Fatal("散人池的人应收到提醒")
	}
	// 只发一次
	if n, _ := e.svc.SendDueReminders(ctx, now.Add(time.Minute)); n != 0 {
		t.Fatalf("一场只发一次：%d", n)
	}
	// 开赛时间后移：重新来过（改期清了提醒标记）；还没到新的窗口就不发
	e.patch(&Tournament{ID: tid}, Changes{StartsAt: rfc(start.Add(48 * time.Hour))})
	e.exec(`UPDATE tournaments SET updated_at = ? WHERE id = ?`, ts(now.Add(-time.Hour)), tid)
	if n, _ := e.svc.SendDueReminders(ctx, now.Add(2*time.Minute)); n != 0 {
		t.Fatalf("新的窗口还没到：%d", n)
	}
}

// 契约 R141：取消赛事：每个活跃报名的队长收到取消邮件，临时队伍通知全员，已驳回的不通知
func TestCancelNotifies(t *testing.T) {
	e := newEnv(t)
	a, b, c, d, f := e.user("甲"), e.user("乙"), e.user("丙"), e.user("丁"), e.user("戊")
	tid := e.tour()
	e.register(tid, e.team("甲队", a, b), a)
	rejected := e.register(tid, e.team("丙队", c, d), c)
	if _, err := e.svc.Reject(e.mgr(), rejected.ID, "不合格"); err != nil {
		t.Fatal(err)
	}
	// 临时队伍：直接插一支，成员是戊
	e.exec(`INSERT INTO registrations (tournament_id, team_id, status, team_name, submitted_at, created_at, updated_at) VALUES (?, NULL, 'approved', '临时队', ?, ?, ?)`, tid, ts(t0), ts(t0), ts(t0))
	var rid int64
	e.d.ReadPool().QueryRow(`SELECT MAX(id) FROM registrations`).Scan(&rid)
	e.exec(`INSERT INTO registration_members (registration_id, tournament_id, user_id, nickname, battletag, is_active) VALUES (?, ?, ?, '戊', 'x#1', 1)`, rid, tid, f)
	e.clearMails()
	if _, err := e.svc.Cancel(e.mgr(), tid, "天气原因"); err != nil {
		t.Fatal(err)
	}
	if got := e.mailsTo(a); len(got) != 1 || !strings.Contains(got[0], "赛事已取消") || !strings.Contains(got[0], "天气原因") {
		t.Fatalf("队长应收到取消信：%v", got)
	}
	if len(e.mailsTo(b)) != 0 {
		t.Fatal("整队报名只通知队长，不通知队员")
	}
	if len(e.mailsTo(c)) != 0 {
		t.Fatal("已驳回的报名不再通知")
	}
	if len(e.mailsTo(f)) != 1 {
		t.Fatal("临时队伍通知全员")
	}
}

// 契约 R143：复制只抄指定字段，状态/报名/提醒不带，三个时间整体平移整周且最早的落在未来（至少一周）
func TestCopy(t *testing.T) {
	e := newEnv(t)
	a, b := e.user("甲"), e.user("乙")
	start := t0.Add(-60 * 24 * time.Hour) // 去年的赛事，早已过去
	tid := e.tour(withStart(start), withWindow(start.Add(-14*24*time.Hour), start.Add(-3*24*time.Hour)), withContact("QQ 群 1"), withAuto())
	e.exec(`UPDATE tournaments SET reminder_sent_at = ?, moved_from = ? WHERE id = ?`, ts(t0), ts(t0), tid)
	_ = a
	_ = b
	c, err := e.svc.Copy(e.mgr(), tid)
	if err != nil {
		t.Fatal(err)
	}
	if c.Status != StatusDraft || c.PublishedAt != nil || c.ReminderSentAt != nil || c.MovedFrom != nil {
		t.Fatalf("状态、提醒不带：%+v", c)
	}
	if c.Title != "春季赛" || c.RegistrationMode != ModeTeam || !c.AutoApprove || c.ParticipantContact != "QQ 群 1" || c.RosterMax != 3 {
		t.Fatalf("字段没抄全：%+v", c)
	}
	shift := c.StartsAt.Sub(start)
	if shift%(7*24*time.Hour) != 0 || shift <= 0 {
		t.Fatalf("要平移整周：%v", shift)
	}
	earliest := *c.RegistrationOpensAt
	if !earliest.After(t0) {
		t.Fatalf("最早的时间要落在未来：%v", earliest)
	}
	if c.RegistrationClosesAt.Sub(*c.RegistrationOpensAt) != 11*24*time.Hour {
		t.Fatal("三个时间要整体平移，相对间隔不变")
	}
	// 未来的赛事复制：至少 +1 周
	fut := e.tour()
	c2, _ := e.svc.Copy(e.mgr(), fut)
	if got := c2.StartsAt.Sub(t0.Add(10 * 24 * time.Hour)); got != 7*24*time.Hour {
		t.Fatalf("未来的赛事复制至少 +1 周：%v", got)
	}
	if e.count(`SELECT COUNT(*) FROM registrations WHERE tournament_id = ?`, c.ID) != 0 {
		t.Fatal("报名不带")
	}
}
