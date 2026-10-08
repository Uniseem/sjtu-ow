package api

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// ---- 测试用的一组接口：每种门一条，外加一条回显绑定结果的 ----

type pathIn struct {
	ID ID `path:"id"`
}

type bodyIn struct {
	ID      ID     `path:"id"`
	Message string `json:"message"`
	Count   int    `json:"count"`
}

type echoOut struct {
	ID      int64  `json:"id"`
	Message string `json:"message"`
	Count   int    `json:"count"`
}

func ok(context *app.Ctx, _ struct{}) (struct{}, error) { return struct{}{}, nil }

func testRegistry(t *testing.T) (*Registry, http.Handler) {
	t.Helper()
	g := &Registry{}

	Get(g, "/api/page/thing/{id}", Public, func(*app.Ctx, pathIn) (struct{}, error) {
		return struct{}{}, nil
	}, Budget(12))
	Get(g, "/api/member", Member, ok)
	Get(g, "/api/verified", Verified, ok)
	Post(g, "/api/teams/{id}/applications", Feature("team_apply"),
		func(_ *app.Ctx, in bodyIn) (echoOut, error) {
			return echoOut{ID: int64(in.ID), Message: in.Message, Count: in.Count}, nil
		}, Limit(ratelimit.Decl{Name: "test_apply", Kind: ratelimit.PerUser, N: 20, Window: 24 * time.Hour}))
	Patch(g, "/api/admin/thing/{id}", Cap("teams.admin"),
		func(_ *app.Ctx, in bodyIn) (echoOut, error) {
			return echoOut{ID: int64(in.ID), Message: in.Message, Count: in.Count}, nil
		}, Limit(ratelimit.Decl{Name: "test_patch", Kind: ratelimit.PerUser, N: 100, Window: time.Minute}), Nav("members", "teams"))
	Delete(g, "/api/super/thing/{id}", Superuser, ok, Limit(ratelimit.Decl{Name: "test_del", Kind: ratelimit.PerUser, N: 10, Window: time.Hour}))
	return g, g.Handler(testResolve)
}

func testResolve(r *http.Request) *app.Viewer {
	name := r.Header.Get("X-Test-Viewer")
	viewers := map[string]*app.Viewer{
		"anonymous":  nil,
		"disabled":   {ID: 1, Disabled: true},
		"unverified": {ID: 2},
		"member":     {ID: 3, EmailVerified: true},
		"denied":     {ID: 4, EmailVerified: true, FeatureDenied: map[app.Feature]struct{}{"team_apply": {}}},
		"editor":     {ID: 5, EmailVerified: true, Caps: map[app.Cap]struct{}{"teams.admin": {}}},
		"super":      {ID: 6, Superuser: true},
	}
	return viewers[name]
}

func doReq(t *testing.T, h http.Handler, method, target, body, viewer string) *httptest.ResponseRecorder {
	t.Helper()
	var rd io.Reader
	if body != "" {
		rd = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, target, rd)
	if body != "" {
		req.Header.Set("Content-Type", "application/json")
	}
	if viewer != "" {
		req.Header.Set("X-Test-Viewer", viewer)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// ---- 守门矩阵：每种门 × 七种身份，断言和声明一致 ----

func TestGateMatrix(t *testing.T) {
	_, h := testRegistry(t)
	const body = `{"message":"hi","count":1}`

	cases := []struct {
		name   string
		method string
		path   string
		want   map[string]int
	}{
		{"Public", "GET", "/api/page/thing/12", map[string]int{
			"anonymous": 200, "disabled": 200, "unverified": 200, "member": 200, "denied": 200, "editor": 200, "super": 200}},
		{"Member", "GET", "/api/member", map[string]int{
			"anonymous": 401, "disabled": 401, "unverified": 200, "member": 200, "denied": 200, "editor": 200, "super": 200}},
		{"Verified", "GET", "/api/verified", map[string]int{
			"anonymous": 401, "disabled": 401, "unverified": 403, "member": 200, "denied": 200, "editor": 200, "super": 200}},
		{"Feature", "POST", "/api/teams/12/applications", map[string]int{
			"anonymous": 401, "disabled": 401, "unverified": 200, "member": 200, "denied": 403, "editor": 200, "super": 200}},
		{"Cap", "PATCH", "/api/admin/thing/7", map[string]int{
			"anonymous": 401, "disabled": 401, "unverified": 403, "member": 403, "denied": 403, "editor": 200, "super": 200}},
		{"Superuser", "DELETE", "/api/super/thing/3", map[string]int{
			"anonymous": 401, "disabled": 401, "unverified": 403, "member": 403, "denied": 403, "editor": 403, "super": 200}},
	}
	for _, tc := range cases {
		for viewer, want := range tc.want {
			rec := doReq(t, h, tc.method, tc.path, body, viewer)
			if rec.Code != want {
				t.Errorf("%s × %s：状态 %d，应为 %d（body=%s）", tc.name, viewer, rec.Code, want, rec.Body.String())
			}
		}
	}
}

// 注册表清单和门都登记在案（守卫测试吃的就是它）。
func TestRoutesAreRegistered(t *testing.T) {
	g, _ := testRegistry(t)
	if len(g.Routes()) != 6 {
		t.Fatalf("应注册 6 条，得到 %d", len(g.Routes()))
	}
	var seenPatch bool
	for _, rt := range g.Routes() {
		if rt.Method == http.MethodPatch {
			seenPatch = true
			if rt.Nav != "members/teams" || len(rt.Limits) == 0 || rt.Limits[0].N != 100 {
				t.Errorf("PATCH 路由的声明没记全：%+v", rt)
			}
		}
	}
	if !seenPatch {
		t.Fatal("没找到 PATCH 路由")
	}
}

// ---- 乱填：路径参数和请求体灌垃圾，一律 404/400，不准 500 ----

func TestGarbagePathParams(t *testing.T) {
	_, h := testRegistry(t)
	for _, bad := range []string{"abc", "12345678901234567890", "-1", "²", "12x", "1.5", "%20"} {
		rec := doReq(t, h, "GET", "/api/page/thing/"+bad, "", "member")
		if rec.Code != http.StatusNotFound {
			t.Errorf("路径参数 %q：状态 %d，应 404", bad, rec.Code)
		}
	}
	// 合法的最长（18 位）要过
	if rec := doReq(t, h, "GET", "/api/page/thing/123456789012456789", "", "member"); rec.Code != 200 {
		t.Errorf("18 位编号应 200，得到 %d", rec.Code)
	}
}

func TestGarbageBodies(t *testing.T) {
	_, h := testRegistry(t)
	path := "/api/teams/12/applications"
	cases := []struct {
		name string
		body string
	}{
		{"错的类型", `{"message": 123, "count": 1}`},
		{"未知字段", `{"message": "hi", "count": 1, "surprise": true}`},
		{"坏 JSON", `{"message":`},
		{"空体", ``},
		{"超限", `{"message": "` + strings.Repeat("a", maxBody) + `", "count": 1}`},
	}
	for _, tc := range cases {
		rec := doReq(t, h, "POST", path, tc.body, "member")
		if rec.Code != http.StatusBadRequest {
			t.Errorf("%s：状态 %d，应 400（body=%s）", tc.name, rec.Code, truncate(rec.Body.String(), 120))
		}
	}
	// Content-Type 不对也拒（写动作只收 JSON）
	req := httptest.NewRequest("POST", path, strings.NewReader(`{"message":"hi","count":1}`))
	req.Header.Set("Content-Type", "text/plain")
	req.Header.Set("X-Test-Viewer", "member")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("错的 Content-Type：状态 %d，应 400", rec.Code)
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "…"
}

// 绑定的基本盘：路径参数、JSON 字段都进去了；JSON 里塞 ID 改不了路径的值。
func TestBinding(t *testing.T) {
	_, h := testRegistry(t)
	rec := doReq(t, h, "POST", "/api/teams/5/applications",
		`{"message":"想入队","count":2,"ID":999,"id":888}`, "member")
	if rec.Code != 200 {
		t.Fatalf("状态 %d（body=%s）", rec.Code, rec.Body.String())
	}
	var got echoOut
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatalf("解析响应：%v", err)
	}
	if got.ID != 5 {
		t.Fatalf("路径的 ID 被请求体改了：%d", got.ID)
	}
	if got.Message != "想入队" || got.Count != 2 {
		t.Fatalf("请求体字段没绑上：%+v", got)
	}
}

// ---- 跨站写：CrossOriginProtection ----

func TestCrossSiteWritesRejected(t *testing.T) {
	_, h := testRegistry(t)
	path := "/api/teams/12/applications"
	body := `{"message":"hi","count":1}`

	req := httptest.NewRequest("POST", path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Sec-Fetch-Site", "cross-site")
	req.Header.Set("X-Test-Viewer", "member")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Errorf("跨站写：状态 %d，应 403", rec.Code)
	}

	req = httptest.NewRequest("POST", path, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Sec-Fetch-Site", "same-origin")
	req.Header.Set("X-Test-Viewer", "member")
	rec = httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != 200 {
		t.Errorf("同站写：状态 %d，应 200", rec.Code)
	}
}

// ---- 错误形状 ----

func TestErrorShape(t *testing.T) {
	g := &Registry{}
	Post(g, "/api/echo", Member,
		func(*app.Ctx, struct{}) (struct{}, error) {
			return struct{}{}, InvalidFields(map[string][]string{
				"name":    {"队名已被使用"},
				"__all__": {"报名已截止"},
			})
		}, Limit(ratelimit.Decl{Name: "test_echo", Kind: ratelimit.PerUser, N: 5, Window: time.Minute}))

	// 服务层冒出的普通 error 一律 500、固定文案、不漏内部信息
	Post(g, "/api/boom", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, errors.New("内部炸了：数据库连接串是 postgres://secret")
	}, Limit(ratelimit.Decl{Name: "test_echo", Kind: ratelimit.PerUser, N: 5, Window: time.Minute}))
	h := g.Handler(testResolve)

	rec := doReq(t, h, "POST", "/api/echo", `{}`, "member")
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("状态 %d，应 422", rec.Code)
	}
	var body struct {
		Error  struct{ Code, Message string } `json:"error"`
		Fields map[string][]string            `json:"fields"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("解析：%v（%s）", err, rec.Body.String())
	}
	if body.Error.Code != "invalid_fields" || body.Fields["name"][0] != "队名已被使用" || body.Fields["__all__"][0] != "报名已截止" {
		t.Fatalf("错误形状不对：%s", rec.Body.String())
	}

	rec = doReq(t, h, "POST", "/api/boom", `{}`, "member")
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("状态 %d，应 500", rec.Code)
	}
	if strings.Contains(rec.Body.String(), "secret") || strings.Contains(rec.Body.String(), "postgres") {
		t.Fatalf("500 把内部信息漏给了客户端：%s", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "internal") {
		t.Fatalf("500 的错误码不对：%s", rec.Body.String())
	}

	rec = doReq(t, h, "GET", "/api/echo", "", "member") // GET 打 POST 地址
	if rec.Code != http.StatusMethodNotAllowed {
		t.Errorf("方法不对：状态 %d，应 405", rec.Code)
	}
}

// ---- 注册时的 panic 规则（防「忘了声明」）----

func TestRegistrationPanics(t *testing.T) {
	expectPanic := func(t *testing.T, want string, fn func()) {
		t.Helper()
		defer func() {
			r := recover()
			if r == nil {
				t.Fatalf("应 panic（%s）", want)
			}
			if msg, ok := r.(string); !ok || !strings.Contains(msg, want) {
				t.Fatalf("panic 内容 %v 应包含 %q", r, want)
			}
		}()
		fn()
	}

	expectPanic(t, "没声明门", func() { Get(&Registry{}, "/api/x", nil, ok) })
	expectPanic(t, "没声明限流", func() { Post(&Registry{}, "/api/x", Public, ok) })
	expectPanic(t, "参数不在地址里", func() {
		Get(&Registry{}, "/api/x", Public, func(*app.Ctx, pathIn) (struct{}, error) { return struct{}{}, nil })
	})
	expectPanic(t, "GET 的 In 不许有 json 字段", func() {
		Get(&Registry{}, "/api/x/{id}", Public, func(*app.Ctx, bodyIn) (struct{}, error) { return struct{}{}, nil })
	})
	expectPanic(t, "类型必须是 api.ID", func() {
		type wrongIn struct {
			ID int64 `path:"id"`
		}
		Get(&Registry{}, "/api/x/{id}", Public, func(*app.Ctx, wrongIn) (struct{}, error) { return struct{}{}, nil })
	})
}
