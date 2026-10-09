package teams

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
)

// httpEnv 把战队模块挂到真正的注册表上，用 X-Test-User 头假装登录（X-Test-Super 表示超管）。
func (e *env) handler() http.Handler {
	reg := &api.Registry{}
	NewModule(e.svc).Routes(reg)
	return reg.Handler(func(r *http.Request) *app.Viewer {
		id, _ := strconv.ParseInt(r.Header.Get("X-Test-User"), 10, 64)
		if id == 0 {
			return nil
		}
		return &app.Viewer{ID: id, EmailVerified: true, Superuser: r.Header.Get("X-Test-Super") == "1"}
	})
}

func (e *env) call(h http.Handler, method, path string, user int64, super bool, body string) (int, map[string]any) {
	e.t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	if user > 0 {
		req.Header.Set("X-Test-User", strconv.FormatInt(user, 10))
	}
	if super {
		req.Header.Set("X-Test-Super", "1")
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var out map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &out)
	return rec.Code, out
}

// 战队接口的门：公开读、登录写、队长才有管理页、超管才有后台
func TestRoutesAndGates(t *testing.T) {
	e := newEnv(t)
	h := e.handler()
	cap, applicant, stranger, admin := e.user("队长"), e.user("申请人"), e.user("路人"), e.user("超管")

	// 未登录不能建队
	if code, _ := e.call(h, "POST", "/api/teams", 0, false, `{"name":"接口队"}`); code != http.StatusUnauthorized {
		t.Fatalf("未登录建队应 401，拿到 %d", code)
	}
	code, out := e.call(h, "POST", "/api/teams", cap, false, `{"name":"接口队","description":"测试","recruiting_roles":["tank","bogus"]}`)
	if code != 200 {
		t.Fatalf("建队：%d %v", code, out)
	}
	team := out["team"].(map[string]any)
	id := int64(team["id"].(float64))
	idPath := "/api/teams/" + strconv.FormatInt(id, 10)
	if roles := team["recruiting_roles"].([]any); len(roles) != 1 || roles[0] != "tank" {
		t.Fatalf("不认识的位置该被丢掉：%v", roles)
	}
	// 422 字段错误形状
	code, out = e.call(h, "POST", "/api/teams", stranger, false, `{"name":"接"}`)
	if code != 422 || out["fields"].(map[string]any)["name"] == nil {
		t.Fatalf("太短应 422 带字段：%d %v", code, out)
	}

	// 公开读：访客也能看到详情和列表，看不到联系方式
	code, out = e.call(h, "GET", idPath, 0, false, "")
	if code != 200 || out["viewer"].(map[string]any)["can_apply"] != false {
		t.Fatalf("访客详情：%d %v", code, out)
	}
	if code, out = e.call(h, "GET", "/api/teams?recruiting=1&role=tank", 0, false, ""); code != 200 || len(out["teams"].([]any)) != 1 {
		t.Fatalf("列表：%d %v", code, out)
	}
	if code, _ = e.call(h, "GET", "/api/teams/99999", 0, false, ""); code != 404 {
		t.Fatalf("不存在应 404：%d", code)
	}

	// 申请：只收 JSON，不登录 401
	apply := idPath + "/applications"
	if code, _ = e.call(h, "POST", apply, 0, false, `{"roles":["tank"]}`); code != 401 {
		t.Fatalf("未登录申请应 401：%d", code)
	}
	code, out = e.call(h, "POST", apply, applicant, false, `{"roles":["tank"],"message":"带带我"}`)
	if code != 200 {
		t.Fatalf("申请：%d %v", code, out)
	}
	appID := int64(out["application"].(map[string]any)["id"].(float64))
	if code, _ = e.call(h, "POST", apply, applicant, false, `{"roles":["tank"]}`); code != http.StatusConflict {
		t.Fatalf("重复申请应 409：%d", code)
	}

	// 管理页：队长看得到，路人是 404
	manage := idPath + "/manage"
	if code, out = e.call(h, "GET", manage, cap, false, ""); code != 200 || len(out["pending"].([]any)) != 1 {
		t.Fatalf("队长管理页：%d %v", code, out)
	}
	if code, _ = e.call(h, "GET", manage, stranger, false, ""); code != 404 {
		t.Fatalf("路人看管理页应 404：%d", code)
	}
	// 审批
	approve := "/api/team-applications/" + strconv.FormatInt(appID, 10) + "/approve"
	if code, _ = e.call(h, "POST", approve, stranger, false, ""); code != 403 {
		t.Fatalf("路人审批应 403：%d", code)
	}
	if code, _ = e.call(h, "POST", approve, cap, false, ""); code != 200 {
		t.Fatalf("队长审批：%d", code)
	}
	// 自动保存：落后版本 409，对的版本 200
	patch := `{"base_version":%d,"changes":{"description":"新简介"}}`
	if code, _ = e.call(h, "PATCH", idPath, cap, false, strings.Replace(patch, "%d", "1", 1)); code != http.StatusConflict {
		t.Fatalf("落后版本应 409：%d", code)
	}
	ver := strconv.FormatInt(e.versionOf(id), 10)
	if code, out = e.call(h, "PATCH", idPath, cap, false, strings.Replace(patch, "%d", ver, 1)); code != 200 || out["saved"].([]any)[0] != "description" {
		t.Fatalf("自动保存：%d %v", code, out)
	}
	// 我的战队
	if code, out = e.call(h, "GET", "/api/me/teams", applicant, false, ""); code != 200 || len(out["teams"].([]any)) != 1 {
		t.Fatalf("我的战队：%d %v", code, out)
	}
	if code, _ = e.call(h, "GET", "/api/me/teams", 0, false, ""); code != 401 {
		t.Fatalf("未登录看我的战队应 401：%d", code)
	}
	// 后台：普通人 403，超管 200
	if code, _ = e.call(h, "GET", "/api/admin/teams", cap, false, ""); code != 403 {
		t.Fatalf("队长不是超管，后台列表应 403：%d", code)
	}
	code, out = e.call(h, "GET", "/api/admin/teams", admin, true, "")
	if code != 200 || len(out["teams"].([]any)) != 1 {
		t.Fatalf("超管后台列表：%d %v", code, out)
	}
	assign := "/api/admin/teams/" + strconv.FormatInt(id, 10) + "/assign-captain"
	if code, _ = e.call(h, "POST", assign, cap, false, `{"user_id":`+strconv.FormatInt(applicant, 10)+`}`); code != 403 {
		t.Fatalf("队长不能走指定队长的后台接口：%d", code)
	}
	if code, _ = e.call(h, "POST", assign, admin, true, `{"user_id":`+strconv.FormatInt(applicant, 10)+`}`); code != 200 {
		t.Fatalf("超管指定队长：%d", code)
	}
	if e.role(id, applicant) != RoleCaptain {
		t.Fatal("指定后该是队长")
	}
	// 退队、移除、解散的路径参数（两个编号）
	if code, _ = e.call(h, "POST", idPath+"/members/"+strconv.FormatInt(cap, 10)+"/remove", applicant, false, ""); code != 200 {
		t.Fatalf("新队长移除原队长（现在是队员）：%d", code)
	}
	if code, _ = e.call(h, "POST", idPath+"/disband", applicant, false, ""); code != 200 {
		t.Fatalf("新队长解散：%d", code)
	}
	if code, _ = e.call(h, "GET", "/api/teams/abc", 0, false, ""); code != 404 {
		t.Fatalf("坏编号应 404：%d", code)
	}
}
