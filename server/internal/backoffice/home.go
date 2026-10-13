package backoffice

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

var shanghai = time.FixedZone("Asia/Shanghai", 8*60*60)

type HomeAction struct {
	Label   string `json:"label"`
	URL     string `json:"url"`
	Primary bool   `json:"primary"`
}
type TodoRow struct {
	Text  string `json:"text"`
	Count int    `json:"count"`
	URL   string `json:"url,omitempty"`
}
type MyArticle struct {
	ID     int64  `json:"id"`
	Title  string `json:"title"`
	Status string `json:"status"`
}
type SetupCheck struct {
	Label  string `json:"label"`
	Detail string `json:"detail"`
	URL    string `json:"url,omitempty"`
}
type SetupOut struct {
	Required []SetupCheck `json:"required"`
	Optional []SetupCheck `json:"optional"`
	Done     []SetupCheck `json:"done"`
}
type HomeOut struct {
	Nickname  string       `json:"nickname"`
	Roles     []string     `json:"roles"`
	HasDuties bool         `json:"has_duties"`
	Actions   []HomeAction `json:"actions"`
	Todo      []TodoRow    `json:"todo"`
	Articles  []MyArticle  `json:"articles"`
	Setup     *SetupOut    `json:"setup"`
}

func addTodo(out *HomeOut, count int, text, url string) {
	if count > 0 {
		out.Todo = append(out.Todo, TodoRow{Text: text, URL: url, Count: count})
	}
}
func (s *Service) home(ctx *app.Ctx, _ struct{}) (HomeOut, error) {
	out := HomeOut{Actions: []HomeAction{}, Todo: []TodoRow{}, Articles: []MyArticle{}, Roles: []string{}}
	if err := require(ctx, accounts.CapAdminEnter, false); err != nil {
		return out, err
	}
	viewer := ctx.Viewer
	out.Nickname = viewer.Nickname
	out.Roles = sortedRoles(viewer)
	out.HasDuties = viewer.Superuser || viewer.HasCap(accounts.CapTournamentsManage) || viewer.HasCap(accounts.CapScrimsManage) || viewer.HasCap(accounts.CapModerationReview)
	if viewer.CanUse(accounts.FeatureArticleSubmit) {
		out.Actions = append(out.Actions, HomeAction{Label: "写文章", URL: "/admin/articles/new/", Primary: true})
	}
	if viewer.HasCap(accounts.CapTournamentsManage) {
		out.Actions = append(out.Actions, HomeAction{Label: "新建赛事", URL: "/admin/tournaments/new/", Primary: len(out.Actions) == 0})
	}
	if viewer.HasCap(accounts.CapScrimsManage) {
		out.Actions = append(out.Actions, HomeAction{Label: "新建内战", URL: "/admin/scrims/new/", Primary: len(out.Actions) == 0})
	}
	out.Actions = append(out.Actions, HomeAction{Label: "打开网站", URL: "/"})
	q := s.d.ReadPool()
	now := ctx.Now().UTC()
	var letters int
	if err := q.QueryRowContext(ctx.Context, `SELECT COUNT(DISTINCT batch) FROM held_letters WHERE actor_id = ? AND state = 'waiting' AND created_at >= ?`, viewer.ID, db.FormatUTC(now.Add(-7*24*time.Hour))).Scan(&letters); err != nil {
		return out, err
	}
	if letters > 0 {
		out.HasDuties = true
		addTodo(&out, letters, fmt.Sprintf("有 %d 件事的信还没决定发不发", letters), "/admin/letters/")
	}
	if viewer.HasCap(accounts.CapTournamentsManage) {
		if err := s.tournamentTodos(ctx.Context, q, now, &out); err != nil {
			return out, err
		}
	}
	if viewer.HasCap(accounts.CapScrimsManage) {
		if err := s.scrimTodos(ctx.Context, q, now, &out); err != nil {
			return out, err
		}
	}
	if viewer.Superuser {
		if err := s.siteTodos(ctx.Context, q, now, &out); err != nil {
			return out, err
		}
		setup, err := s.siteSetup(ctx.Context, q)
		if err != nil {
			return out, err
		}
		out.Setup = &setup
	}
	articles, err := recentArticles(ctx.Context, q, viewer.ID, now)
	if err != nil {
		return out, err
	}
	out.Articles = articles
	return out, nil
}
func recentArticles(ctx context.Context, q db.DBTX, actor int64, now time.Time) ([]MyArticle, error) {
	rows, err := q.QueryContext(ctx, `SELECT p.id, COALESCE(json_extract(r.content, '$.title'), p.title), p.live, p.go_live_at, p.has_unpublished_changes FROM pages p LEFT JOIN page_revisions r ON r.id = p.latest_revision_id WHERE p.kind = 'article' AND p.owner_id = ? ORDER BY p.updated_at DESC, p.id DESC LIMIT 5`, actor)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []MyArticle{}
	for rows.Next() {
		var article MyArticle
		var live, changed bool
		var goLive sql.NullString
		if err := rows.Scan(&article.ID, &article.Title, &live, &goLive, &changed); err != nil {
			return nil, err
		}
		article.Status = "draft"
		if live {
			article.Status = "published"
			if changed {
				article.Status = "已发布·有改动"
			}
		}
		if !live && goLive.Valid {
			scheduled, err := db.ParseUTC(goLive.String)
			if err == nil && scheduled.After(now) {
				article.Status = "scheduled"
			}
		}
		out = append(out, article)
	}
	return out, rows.Err()
}
func (s *Service) tournamentTodos(ctx context.Context, q db.DBTX, now time.Time, out *HomeOut) error {
	var pending int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM registrations r JOIN tournaments t ON t.id = r.tournament_id WHERE r.status = 'pending' AND t.status <> 'cancelled'`).Scan(&pending); err != nil {
		return err
	}
	addTodo(out, pending, fmt.Sprintf("%d 份报名等待审核", pending), "/admin/registrations/?status=pending")
	rows, err := q.QueryContext(ctx, `SELECT t.id, t.title, COUNT(i.id) FROM tournaments t JOIN individual_signups i ON i.tournament_id = t.id WHERE t.status = 'published' AND i.registration_id IS NULL GROUP BY t.id ORDER BY t.title, t.id`)
	if err != nil {
		return err
	}
	for rows.Next() {
		var id int64
		var title string
		var count int
		if err := rows.Scan(&id, &title, &count); err != nil {
			rows.Close()
			return err
		}
		addTodo(out, count, fmt.Sprintf("「%s」有 %d 人等待编队", title, count), fmt.Sprintf("/admin/tournaments/%d/teams/", id))
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	rows, err = q.QueryContext(ctx, `SELECT title FROM tournaments WHERE status = 'published' AND starts_at < ? ORDER BY starts_at, id`, db.FormatUTC(now.Add(-3*24*time.Hour)))
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var title string
		if err := rows.Scan(&title); err != nil {
			return err
		}
		addTodo(out, 1, fmt.Sprintf("「%s」开赛已经 3 天以上，打完了的话在赛事列表的「更多」里标记已结束", title), "/admin/tournaments/")
	}
	return rows.Err()
}
func (s *Service) scrimTodos(ctx context.Context, q db.DBTX, now time.Time, out *HomeOut) error {
	rows, err := q.QueryContext(ctx, `SELECT s.id, s.title FROM scrims s WHERE s.status = 'published' AND s.signup_closes_at <= ? AND s.starts_at > ? AND NOT EXISTS (SELECT 1 FROM scrim_signups ss WHERE ss.scrim_id = s.id AND ss.team IN ('a','b')) ORDER BY s.starts_at, s.id`, db.FormatUTC(now), db.FormatUTC(now))
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var id int64
		var title string
		if err := rows.Scan(&id, &title); err != nil {
			return err
		}
		addTodo(out, 1, fmt.Sprintf("「%s」报名已截止，还没分队", title), fmt.Sprintf("/admin/scrims/%d/split/", id))
	}
	return rows.Err()
}
func (s *Service) siteTodos(ctx context.Context, q db.DBTX, now time.Time, out *HomeOut) error {
	var stuck int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM teams t WHERE t.disbanded_at IS NULL AND NOT EXISTS (SELECT 1 FROM team_memberships tm JOIN users u ON u.id = tm.user_id WHERE tm.team_id = t.id AND tm.role = 'captain' AND u.is_active = 1)`).Scan(&stuck); err != nil {
		return err
	}
	addTodo(out, stuck, fmt.Sprintf("%d 支战队的队长账号已停用，没人能审批入队申请、为它报名，去指定新队长", stuck), "/admin/teams/?captain_inactive=1")
	var heartbeat string
	err := q.QueryRowContext(ctx, `SELECT heartbeat_at FROM worker_status WHERE id = 1`).Scan(&heartbeat)
	if err != nil && err != sql.ErrNoRows {
		return err
	}
	beating := false
	if err == nil {
		stamp, parseErr := db.ParseUTC(heartbeat)
		beating = parseErr == nil && now.Sub(stamp) <= 120*time.Second && !stamp.After(now.Add(30*time.Second))
	}
	if !beating {
		addTodo(out, 1, "后台任务（worker）没在运行：心跳缺失。邮件、提醒、静态页都停了，到服务器上看 worker 容器", "/healthz")
	}
	var failures int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM jobs WHERE kind = 'mail.letter' AND status = 'failed' AND finished_at >= ?`, db.FormatUTC(now.Add(-7*24*time.Hour))).Scan(&failures); err != nil {
		return err
	}
	addTodo(out, failures, fmt.Sprintf("最近 7 天有 %d 封邮件重试后仍没发出去，检查全站设置里的 SMTP，先发一封测试邮件", failures), "/admin/settings/site/")
	if s.backupStatus != nil {
		problems, err := s.backupStatus(ctx, now)
		if err != nil {
			addTodo(out, 1, "备份状态暂时无法读取，请检查本站备份目录。", "")
		} else {
			for _, problem := range problems {
				if strings.TrimSpace(problem) != "" {
					addTodo(out, 1, problem, "")
				}
			}
		}
	}
	return nil
}
func (s *Service) siteSetup(ctx context.Context, q db.DBTX) (SetupOut, error) {
	out := SetupOut{Required: []SetupCheck{}, Optional: []SetupCheck{}, Done: []SetupCheck{}}
	add := func(check SetupCheck, required, done bool) {
		if done {
			out.Done = append(out.Done, check)
		} else if required {
			out.Required = append(out.Required, check)
		} else {
			out.Optional = append(out.Optional, check)
		}
	}
	var host, address, description, group, founded string
	var hero sql.NullInt64
	var moderationEnabled, moderationConfigured bool
	err := q.QueryRowContext(ctx, `SELECT smtp_host, from_address, site_description, qq_group_url, founded_on, hero_image_id, moderation_enabled, moderation_configured FROM site_settings WHERE id = 1`).Scan(&host, &address, &description, &group, &founded, &hero, &moderationEnabled, &moderationConfigured)
	if err != nil {
		return out, err
	}
	mailDone := strings.TrimSpace(host) != "" && strings.TrimSpace(address) != ""
	mailDetail := "还没配置。注册要验证邮箱，没有邮件就没有人能注册、找回密码。在全站设置里填 SMTP 服务器和发件地址，再点「发送测试邮件」。"
	if mailDone {
		mailDetail = "已配置。改过之后在全站设置里点「发送测试邮件」确认能发出去。"
	}
	add(SetupCheck{Label: "邮件（SMTP）", Detail: mailDetail, URL: "/admin/settings/site/"}, true, mailDone)
	for _, legal := range []struct{ slug, title string }{{"terms", "用户协议"}, {"privacy", "隐私政策"}} {
		var id int64
		var body string
		err := q.QueryRowContext(ctx, `SELECT p.id, sp.body_md FROM pages p JOIN site_pages sp ON sp.page_id = p.id WHERE p.kind = 'site_page' AND p.slug = ?`, legal.slug).Scan(&id, &body)
		if err != nil && err != sql.ErrNoRows {
			return out, err
		}
		done := err == nil && strings.TrimSpace(body) != "" && strings.Count(body, "【") == 0
		detail := "已填写。"
		if err == sql.ErrNoRows {
			detail = "页面不存在，先初始化网站页面。"
		} else if strings.TrimSpace(body) == "" {
			detail = "还没有正文，请在网站页面里填写。"
		} else if blanks := strings.Count(body, "【"); blanks > 0 {
			detail = fmt.Sprintf("正文里还有 %d 处【】要社团填写（运营方、联系方式、生效日期等）。", blanks)
		}
		href := "/admin/pages/"
		if id > 0 {
			href = fmt.Sprintf("/admin/pages/%d/", id)
		}
		add(SetupCheck{Label: legal.title, Detail: detail, URL: href}, true, done)
	}
	aiDetail := "还没有填接口密钥（自建服务可以只填接口地址），AI 审核不会运行。在全站设置的「AI 审核」里填好，再点「试一下 AI」确认能连上。"
	if moderationConfigured && !moderationEnabled {
		aiDetail = "密钥已设置，但全站设置里「启用 AI 内容审核」关着。"
	}
	if moderationConfigured && moderationEnabled {
		aiDetail = "在运行。可以在全站设置页上点「试一下 AI」确认能连上。"
	}
	add(SetupCheck{Label: "AI 内容审核", Detail: aiDetail, URL: "/admin/settings/site/"}, false, moderationConfigured && moderationEnabled)
	var editors int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(DISTINCT ur.user_id) FROM user_roles ur JOIN users u ON u.id=ur.user_id WHERE ur.role=? AND u.is_active=1`, accounts.RoleContentEditor).Scan(&editors); err != nil {
		return out, err
	}
	editorDetail := "已有人负责。"
	if editors == 0 {
		editorDetail = "还没有人在「内容编辑」组。查看巡查记录、撤下头像、隐藏评论都只有超级管理员能做。在「成员 → 用户与权限」里给社团干部勾上这个角色（赛事、内战管理员同理）。"
	}
	add(SetupCheck{Label: "内容编辑", Detail: editorDetail, URL: "/admin/users/"}, false, editors > 0)
	var aboutID int64
	var aboutBody string
	aboutErr := q.QueryRowContext(ctx, `SELECT p.id, sp.body_md FROM pages p JOIN site_pages sp ON sp.page_id=p.id WHERE p.kind='site_page' AND p.slug='about'`).Scan(&aboutID, &aboutBody)
	if aboutErr != nil && aboutErr != sql.ErrNoRows {
		return out, aboutErr
	}
	aboutURL := ""
	if aboutID > 0 {
		aboutURL = fmt.Sprintf("/admin/pages/%d/", aboutID)
	}
	aboutDone := aboutErr == nil && strings.TrimSpace(aboutBody) != ""
	aboutDetail := "已填写。"
	if !aboutDone {
		aboutDetail = "还是空的。页脚每页都链到它，写几句社团介绍和联系方式。"
	}
	add(SetupCheck{Label: "关于我们", Detail: aboutDetail, URL: aboutURL}, false, aboutDone)
	missing := []string{}
	for _, item := range []struct{ label, value string }{{"站点简介", description}, {"QQ 群链接", group}, {"成立日期", founded}} {
		if strings.TrimSpace(item.value) == "" {
			missing = append(missing, item.label)
		}
	}
	if !hero.Valid {
		missing = append(missing, "首屏图片")
	}
	homeDetail := "已填写。"
	if len(missing) > 0 {
		homeDetail = "还没填：" + strings.Join(missing, "、") + "。站点简介用在搜索结果和链接预览里，QQ 群链接是首页的「加入」按钮。"
	}
	add(SetupCheck{Label: "首页和分享信息", Detail: homeDetail, URL: "/admin/settings/site/"}, false, len(missing) == 0)
	var covers, avatars int
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM images i JOIN image_collections c ON c.id = i.collection_id WHERE c.key = 'default_cover'`).Scan(&covers); err != nil {
		return out, err
	}
	if err := q.QueryRowContext(ctx, `SELECT COUNT(*) FROM images i JOIN image_collections c ON c.id = i.collection_id WHERE c.key = 'default_avatar'`).Scan(&avatars); err != nil {
		return out, err
	}
	pictureMissing := []string{}
	if covers == 0 {
		pictureMissing = append(pictureMissing, "默认封面")
	}
	if avatars == 0 {
		pictureMissing = append(pictureMissing, "默认头像")
	}
	pictureDetail := "图库里有图。"
	if len(pictureMissing) > 0 {
		pictureDetail = "「" + strings.Join(pictureMissing, "」「") + "」图库是空的，没有封面、头像的地方会显示占位图。在「图片」里上传到这两个集合（可以建子文件夹）。"
	}
	add(SetupCheck{Label: "默认封面和默认头像", Detail: pictureDetail, URL: "/admin/images/"}, false, len(pictureMissing) == 0)
	bannerDetail := "已关闭。"
	if s.testEnvironment {
		bannerDetail = "页面顶部有「测试环境」横幅、禁止搜索引擎收录。正式上线前去掉 .env 里的 TEST_ENVIRONMENT 并重启。"
	}
	add(SetupCheck{Label: "测试环境标记", Detail: bannerDetail}, false, !s.testEnvironment)
	return out, nil
}
