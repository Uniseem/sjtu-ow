package backoffice

import (
	"strings"

	"github.com/Uniseem/sjtu-ow/server/internal/accounts"
	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/tournaments"
)

type Service struct {
	d               *db.DB
	registry        *api.Registry
	tournaments     *tournaments.Service
	backupStatus    BackupStatusReader
	testEnvironment bool
}

func NewService(d *db.DB, registry *api.Registry) *Service {
	return &Service{d: d, registry: registry}
}

func (s *Service) WithTestEnvironment(on bool) *Service { s.testEnvironment = on; return s }

type Module struct {
	svc      *Service
	resolver api.ViewerResolver
}

func NewModule(svc *Service) *Module { return &Module{svc: svc} }

type NavigationTab struct {
	Key   string          `json:"key"`
	Label string          `json:"label"`
	URL   string          `json:"url"`
	Count int             `json:"count"`
	Tabs  []NavigationTab `json:"tabs"`
}

type NavigationSection struct {
	Key   string          `json:"key"`
	Label string          `json:"label"`
	URL   string          `json:"url"`
	Tabs  []NavigationTab `json:"tabs"`
}

type NavigationOut struct {
	Sections []NavigationSection `json:"sections"`
}

type navDefinition struct {
	section      string
	sectionLabel string
	tab          string
	label        string
	url          string
	aliases      []string
}

var navDefinitions = []navDefinition{
	{"home", "首页", "home", "首页", "/admin/", []string{"home/todo"}},
	{"content", "内容", "articles", "文章", "/admin/articles/", []string{"articles/list", "articles/edit", "articles/new"}},
	{"content", "内容", "categories", "分类", "/admin/categories/", []string{"articles/categories", "categories/list"}},
	{"content", "内容", "pages", "网站页面", "/admin/pages/", []string{"pages/list", "content/pages", "articles/home-pins"}},
	{"content", "内容", "images", "图片", "/admin/images/", []string{"images/list", "images/upload"}},
	{"activities", "活动", "tournaments", "赛事", "/admin/tournaments/", []string{"tournaments/list", "tournaments/edit", "tournaments/new"}},
	{"activities", "活动", "scrims", "内战", "/admin/scrims/", []string{"scrims/list", "scrims/edit", "scrims/new"}},
	{"members", "成员", "users", "用户与权限", "/admin/users/", []string{"users/list", "users/edit", "users/roles"}},
	{"members", "成员", "teams", "战队", "/admin/teams/", []string{"teams/list", "teams/edit"}},
	{"members", "成员", "groups", "成员分组", "/admin/member-groups/", []string{"member-groups/list", "members/groups"}},
	{"review", "审核", "registrations", "报名", "/admin/registrations/", []string{"registrations/list", "tournaments/review", "tournaments/registrations"}},
	{"review", "审核", "moderation", "内容", "/admin/moderation/", []string{"moderation/list", "moderation/detail"}},
	{"review", "审核", "avatars", "头像", "/admin/avatars/", []string{"users/avatars", "avatars/list"}},
	{"review", "审核", "comments", "评论", "/admin/comments/", []string{"comments/list", "comments/edit"}},
	{"data", "数据", "activity", "活动数据", "/admin/activity/", []string{"activity/list", "data/activity"}},
	{"settings", "设置", "site", "全站设置", "/admin/settings/", []string{"settings/site"}},
	{"settings", "设置", "fonts", "字体库", "/admin/settings/fonts/", []string{"settings/fonts"}},
	{"settings", "设置", "typography", "排版设置", "/admin/settings/typography/", []string{"settings/typography"}},
	{"settings", "设置", "log", "操作记录", "/admin/log/", []string{"audit/list", "settings/log"}},
	{"manual", "手册", "manual", "手册", "/admin/manual/", []string{"manual/index", "manual/list"}},
}

func (m *Module) Routes(registry *api.Registry) {
	m.legacyExportRoutes(registry)
	api.Get(registry, "/api/admin/navigation", api.Cap(accounts.CapAdminEnter), m.navigation, api.Nav("home", "navigation"))
	m.managementRoutes(registry)
}

func navMatches(nav string, definition navDefinition) bool {
	if nav == definition.section+"/"+definition.tab {
		return true
	}
	for _, alias := range definition.aliases {
		if nav == alias {
			return true
		}
	}
	return false
}

func (m *Module) navigation(ctx *app.Ctx, _ struct{}) (NavigationOut, error) {
	out := NavigationOut{Sections: []NavigationSection{}}
	for _, definition := range navDefinitions {
		allowed := definition.section == "home"
		for _, route := range m.svc.registry.Routes() {
			if !strings.HasPrefix(route.Pattern, "/api/admin/") || !navMatches(route.Nav, definition) {
				continue
			}
			if route.Allowed(ctx.Viewer) {
				allowed = true
				break
			}
		}
		if !allowed {
			continue
		}
		position := -1
		for i := range out.Sections {
			if out.Sections[i].Key == definition.section {
				position = i
				break
			}
		}
		if position == -1 {
			out.Sections = append(out.Sections, NavigationSection{
				Key: definition.section, Label: definition.sectionLabel,
				URL: definition.url, Tabs: []NavigationTab{},
			})
			position = len(out.Sections) - 1
		}
		tab := NavigationTab{Key: definition.tab, Label: definition.label, URL: definition.url, Tabs: []NavigationTab{}}
		if definition.tab == "users" {
			tab.Tabs = []NavigationTab{
				{Key: "users", Label: "用户", URL: "/admin/users/", Tabs: []NavigationTab{}},
				{Key: "roles", Label: "角色", URL: "/admin/roles/", Tabs: []NavigationTab{}},
			}
		}
		out.Sections[position].Tabs = append(out.Sections[position].Tabs, tab)
	}
	return out, nil
}

func (s *Service) SetTournamentService(service *tournaments.Service) { s.tournaments = service }
