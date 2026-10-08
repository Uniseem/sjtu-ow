package apigen

import (
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
