package apigen

import (
	"regexp"
	"strings"
	"testing"

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
		`export function postApiTeamsIdApplications(id: string, body: PostApiTeamsIdApplicationsIn)`,
		`call<PostApiTeamsIdApplicationsOut>("POST", "/api/teams/{id}/applications", { id }, body)`,
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
	if !strings.HasPrefix(index, header) || !strings.Contains(index, "export async function call") {
		t.Fatal(index)
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
