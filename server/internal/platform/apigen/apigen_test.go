package apigen

import (
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

type applyIn struct {
	ID      api.ID `path:"id"`
	Message string `json:"message"`
}

type applyOut struct {
	ID int64 `json:"id"`
}

func TestRenderEmitsTypesAndNav(t *testing.T) {
	reg := &api.Registry{}
	api.Post(reg, "/api/teams/{id}/applications", api.Public,
		func(*app.Ctx, applyIn) (applyOut, error) { return applyOut{}, nil },
		api.NoLimit("生成器样例"), api.Nav("members", "teams"))
	index, nav := Render(reg)
	for _, want := range []string{
		"export interface PostApiTeamsIdApplicationsIn",
		"message: string",
		"export interface PostApiTeamsIdApplicationsOut",
		"id: number",
		`export function postApiTeamsIdApplications(r: Requester, id: string | number, body: PostApiTeamsIdApplicationsIn, extras: CallExtras = {}): Promise<PostApiTeamsIdApplicationsOut>`,
		`return r<PostApiTeamsIdApplicationsOut>("POST", "/api/teams/{id}/applications", { ...extras, params: { id }, body })`,
	} {
		if !strings.Contains(index, want) {
			t.Fatalf("缺 %s\n%s", want, index)
		}
	}
	if strings.Contains(index, "ID:") {
		t.Fatal("路径参数不该进请求体类型")
	}
	if !strings.Contains(nav, `section: "members"`) || !strings.Contains(nav, `tab: "teams"`) {
		t.Fatal(nav)
	}
}

func TestEmptyRegistryIsStable(t *testing.T) {
	index, nav := Render(&api.Registry{})
	if !strings.HasPrefix(index, header) || !strings.Contains(index, `import type { CallExtras, Requester } from "../client.ts"`) {
		t.Fatal(index)
	}
	// 生成物不自己发请求：幂等键、401、待发信只在 createClient 里（A3）。
	if strings.Contains(index, "fetch(") {
		t.Fatal("生成物里不该有 fetch")
	}
	if !strings.Contains(nav, "export const nav") || strings.Contains(nav, `section: "`) {
		t.Fatal(nav)
	}
}

type hyphenIn struct {
	Email string `json:"email"`
}

type hyphenOut struct {
	OK bool `json:"ok"`
}

// 生成的 TS 函数名和接口名必须是合法标识符：路径里的连字符要转成驼峰
// （/api/auth/verify-email → postApiAuthVerifyEmail），不然前端一 import 就炸。
func TestHyphenPathMakesValidIdentifiers(t *testing.T) {
	reg := &api.Registry{}
	api.Post(reg, "/api/auth/some-hyphen-action", api.Public,
		func(*app.Ctx, hyphenIn) (hyphenOut, error) { return hyphenOut{}, nil },
		api.NoLimit("测试"))
	index, _ := Render(reg)

	for _, line := range strings.Split(index, "\n") {
		line = strings.TrimSpace(line)
		var prefix string
		switch {
		case strings.HasPrefix(line, "export function "):
			prefix = "export function "
		case strings.HasPrefix(line, "export interface "):
			prefix = "export interface "
		default:
			continue
		}
		rest := line[len(prefix):]
		name := rest
		if i := strings.IndexAny(rest, "(<{ "); i >= 0 {
			name = rest[:i]
		}
		if !regexp.MustCompile(`^[A-Za-z_$][A-Za-z0-9_$]*$`).MatchString(name) {
			t.Fatalf("生成的标识符不合法: %q", name)
		}
	}
	if !strings.Contains(index, "postApiAuthSomeHyphenAction") ||
		!strings.Contains(index, "PostApiAuthSomeHyphenActionIn") {
		t.Fatalf("连字符应转成驼峰:\n%s", index)
	}
}

func TestRenderMarkdown(t *testing.T) {
	reg := &api.Registry{}
	api.Post(reg, "/api/teams/{id}/applications", api.Public,
		func(*app.Ctx, applyIn) (applyOut, error) { return applyOut{}, nil },
		api.NoLimit("生成器样例"), api.Nav("members", "teams"))

	md := RenderMarkdown(reg)
	for _, want := range []string{
		"# SJTU-OW 接口注册表与权限全景手册",
		"## 1. 架构概览与指标",
		"## 2. 全量接口清单与准入门禁",
		"`POST`",
		"`/api/teams/{id}/applications`",
		"Public（公开）",
		"members/teams",
		"## 3. 干部角色能力对照表 (Who Can Do What)",
	} {
		if !strings.Contains(md, want) {
			t.Fatalf("Markdown 手册缺少预期内容: %q\n%s", want, md)
		}
	}
}

type person struct {
	UserID   int64  `json:"user_id"`
	Nickname string `json:"nickname"`
}

type memberRow struct {
	person
	Role string `json:"role"`
}

type rosterOut struct {
	Members []memberRow  `json:"members"`
	Maybe   []*memberRow `json:"maybe"`
	Leader  *memberRow   `json:"leader"`
	Since   time.Time    `json:"since"`
	Note    string       `json:"note,omitempty"`
}

type listQueryIn struct {
	Category string `query:"category"`
	Page     int    `query:"page"`
	Mine     bool   `query:"mine"`
}

// 类型要和 encoding/json 的实际输出一样（A4）：匿名嵌入摊平、`[]*T` 是
// `(T | null)[]`、指针 `| null`、时间是字符串、omitempty 可选。
func TestTypesFollowEncodingJSON(t *testing.T) {
	reg := &api.Registry{}
	api.Get(reg, "/api/roster", api.Public,
		func(*app.Ctx, struct{}) (rosterOut, error) { return rosterOut{}, nil })
	index, _ := Render(reg)
	row := "{   user_id: number;   nickname: string;   role: string; }"
	for _, want := range []string{
		"  members: " + row + "[];\n",
		"  maybe: (" + row + " | null)[];\n",
		"  leader: " + row + " | null;\n",
		"  since: string;\n",
		"  note?: string;\n",
	} {
		if !strings.Contains(index, want) {
			t.Fatalf("缺 %q\n%s", want, index)
		}
	}
	if strings.Contains(index, "person") {
		t.Fatalf("匿名嵌入的结构应摊平，不该出现字段名：\n%s", index)
	}
}

// 查询参数生成成可选的 Query 类型，作为参数传给 Requester；GET 没有请求体。
func TestQueryParamsAreGenerated(t *testing.T) {
	reg := &api.Registry{}
	api.Get(reg, "/api/page/news", api.Public,
		func(*app.Ctx, listQueryIn) (applyOut, error) { return applyOut{}, nil })
	index, _ := Render(reg)
	for _, want := range []string{
		"export interface GetApiPageNewsQuery {\n  category?: string;\n  page?: number;\n  mine?: boolean;\n}",
		"export function getApiPageNews(r: Requester, query: GetApiPageNewsQuery = {}, extras: CallExtras = {}): Promise<GetApiPageNewsOut>",
		`return r<GetApiPageNewsOut>("GET", "/api/page/news", { ...extras, query })`,
	} {
		if !strings.Contains(index, want) {
			t.Fatalf("缺 %q\n%s", want, index)
		}
	}
	if strings.Contains(index, "GetApiPageNewsIn") {
		t.Fatal("只有查询参数的接口不该有请求体类型")
	}
}
