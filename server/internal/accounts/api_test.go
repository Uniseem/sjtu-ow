package accounts

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

func TestGetSessionApi(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	store := svc.Store()

	// 准备两个测试用户
	now := time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)
	verified := now
	member := &User{
		Email:               "user@sjtu.edu.cn",
		EmailNorm:           "user@sjtu.edu.cn",
		PasswordHash:        "argon2$...",
		Nickname:            "小明",
		IsSJTU:              true,
		AgreedTermsAt:       now,
		AgreedCrossBorderAt: now,
		EmailVerifiedAt:     &verified,
		Version:             1,
		IsActive:            true,
		IsSuperuser:         false,
		CreatedAt:           now,
		UpdatedAt:           now,
	}
	super := &User{
		Email:               "admin@sjtu.edu.cn",
		EmailNorm:           "admin@sjtu.edu.cn",
		PasswordHash:        "argon2$...",
		Nickname:            "站长",
		IsSJTU:              true,
		AgreedTermsAt:       now,
		AgreedCrossBorderAt: now,
		EmailVerifiedAt:     &verified,
		Version:             1,
		IsActive:            true,
		IsSuperuser:         true,
		CreatedAt:           now,
		UpdatedAt:           now,
	}

	err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		if _, err := store.InsertUser(ctx, tx, member); err != nil {
			return err
		}
		if _, err := store.InsertUser(ctx, tx, super); err != nil {
			return err
		}
		return nil
	})
	if err != nil {
		t.Fatalf("InsertUser: %v", err)
	}

	var currentViewer *app.Viewer
	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer {
		return currentViewer
	})

	// 1. 访客
	currentViewer = nil
	req := httptest.NewRequest(http.MethodGet, "/api/session", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("访客返回状态码=%d，应为 200", rec.Code)
	}
	var out SessionOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化失败: %v", err)
	}
	if out.User != nil {
		t.Fatalf("访客出参 user 应为 nil: %+v", out.User)
	}

	// 2. 普通交大成员（无管理角色，但作为已验证投稿者有 CapAdminEnter）
	vMember, err := svc.BuildViewer(ctx, member.ID)
	if err != nil {
		t.Fatal(err)
	}
	currentViewer = vMember
	req = httptest.NewRequest(http.MethodGet, "/api/session", nil)
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("状态码=%d", rec.Code)
	}
	out = SessionOut{}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化: %v", err)
	}
	if out.User == nil || out.User.Nickname != "小明" || !out.User.IsSJTU || !out.User.EmailVerified {
		t.Fatalf("用户数据不符: %+v", out.User)
	}
	if !out.User.Admin {
		t.Fatalf("投稿者有后台入口，admin 应为 true")
	}

	// 3. 超管
	vSuper, err := svc.BuildViewer(ctx, super.ID)
	if err != nil {
		t.Fatal(err)
	}
	currentViewer = vSuper
	req = httptest.NewRequest(http.MethodGet, "/api/session", nil)
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("状态码=%d", rec.Code)
	}
	out = SessionOut{}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化: %v", err)
	}
	if out.User == nil || !out.User.Admin || out.User.Nickname != "站长" {
		t.Fatalf("超管数据不符: %+v", out.User)
	}

	// 4. 停用用户
	currentViewer = &app.Viewer{ID: member.ID, Disabled: true}
	req = httptest.NewRequest(http.MethodGet, "/api/session", nil)
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("状态码=%d", rec.Code)
	}
	out = SessionOut{}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化: %v", err)
	}
	if out.User != nil {
		t.Fatalf("停用用户应返回 user: nil: %+v", out.User)
	}
}

func TestRegisterApi(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	// 1. 成功注册
	body := []byte(`{
		"email": "api_user@sjtu.edu.cn",
		"nickname": "接口用户",
		"password": "Password123!@#",
		"confirm_password": "Password123!@#",
		"is_sjtu": true,
		"agree_terms": true,
		"agree_cross_border": true
	}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("成功注册状态码=%d，应为 200: %s", rec.Code, rec.Body.String())
	}
	var out RegisterOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化失败: %v", err)
	}
	if out.Email != "api_user@sjtu.edu.cn" || !strings.Contains(out.Message, "验证码") {
		t.Fatalf("响应出参不符: %+v", out)
	}

	// 2. 字段校验失败 (422)
	badBody := []byte(`{
		"email": "not-an-email",
		"nickname": "X",
		"password": "",
		"confirm_password": "mismatch",
		"agree_terms": false,
		"agree_cross_border": false
	}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader(badBody))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("校验失败状态码=%d，应为 422: %s", rec.Code, rec.Body.String())
	}
	var errResp struct {
		Error struct {
			Code    string `json:"code"`
			Message string `json:"message"`
		} `json:"error"`
		Fields map[string][]string `json:"fields"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &errResp); err != nil {
		t.Fatalf("反序列化失败: %v", err)
	}
	if errResp.Error.Code != "invalid_fields" {
		t.Fatalf("error.code=%q, want invalid_fields", errResp.Error.Code)
	}
	for _, f := range []string{"email", "nickname", "password", "confirm_password", "is_sjtu", "agree_terms", "agree_cross_border"} {
		if len(errResp.Fields[f]) == 0 {
			t.Errorf("fields[%s] 应该有错误信息", f)
		}
	}
}

func TestRegisterApiRateLimit(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, clk)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil },
		api.WithLimiter(enforcer),
	)

	// AuthSignup 限流为 20 次/分钟/IP
	for i := 1; i <= 20; i++ {
		body := []byte(fmt.Sprintf(`{
			"email": "rate_user_%d@sjtu.edu.cn",
			"nickname": "限流测试",
			"password": "Password123!@#",
			"confirm_password": "Password123!@#",
			"is_sjtu": true,
			"agree_terms": true,
			"agree_cross_border": true
		}`, i))
		req := httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = "192.0.2.100:54321"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("第 %d 次请求应成功，得到状态码 %d: %s", i, rec.Code, rec.Body.String())
		}
	}

	// 第 21 次请求触发限流 429
	body := []byte(`{
		"email": "rate_user_exceed@sjtu.edu.cn",
		"nickname": "超限用户",
		"password": "Password123!@#",
		"confirm_password": "Password123!@#",
		"is_sjtu": true,
		"agree_terms": true,
		"agree_cross_border": true
	}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.RemoteAddr = "192.0.2.100:54321"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("第 21 次请求应返回 429，得到 %d: %s", rec.Code, rec.Body.String())
	}
	if rec.Header().Get("Retry-After") == "" {
		t.Fatalf("429 响应应包含 Retry-After 头")
	}
}

func TestVerifyEmailApi(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	// 注册拿到一条 signup 码
	mustRegister(t, svc, "api-verify@sjtu.edu.cn", "接口验证", "Password123!@#")

	// 1. 错码：422，不带 Cookie
	body := []byte(`{"email": "api-verify@sjtu.edu.cn", "code": "000000"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("错码应 422，得到 %d: %s", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Header().Get("Set-Cookie"), "ow_session") {
		t.Fatalf("错码不应发会话 Cookie")
	}

	// 2. 对的码：200 + ow_session Cookie
	body = []byte(`{"email": "api-verify@sjtu.edu.cn", "code": "123456"}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("对的码应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	sc := rec.Header().Get("Set-Cookie")
	if !strings.Contains(sc, "ow_session=") || !strings.Contains(sc, "HttpOnly") || !strings.Contains(sc, "SameSite=Lax") {
		t.Fatalf("Cookie 属性不符: %q", sc)
	}
	if strings.Contains(sc, "Secure") {
		t.Fatalf("未声明 WithSecureCookies 时不应带 Secure: %q", sc)
	}
	var out VerifyEmailOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out.Result != "ok" || !strings.Contains(out.Message, "游戏 ID") {
		t.Fatalf("出参不符: %+v", out)
	}

	// 3. 响应体里不能出现令牌（只在 HttpOnly Cookie 里）
	if strings.Contains(rec.Body.String(), sc[strings.Index(sc, "ow_session="):strings.Index(sc, ";")]) {
		t.Fatalf("令牌泄露进 JSON")
	}

	// 4. 空体：422 字段报错
	req = httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("空体应 422，得到 %d", rec.Code)
	}
}

func TestVerifyEmailApiSecureCookie(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil }, api.WithSecureCookies(true))

	mustRegister(t, svc, "secure@sjtu.edu.cn", "安全者", "Password123!@#")
	body := []byte(`{"email": "secure@sjtu.edu.cn", "code": "123456"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("应 200，得到 %d", rec.Code)
	}
	if sc := rec.Header().Get("Set-Cookie"); !strings.Contains(sc, "Secure") {
		t.Fatalf("声明 Secure 后 Cookie 应带 Secure: %q", sc)
	}
}

func TestLoginApi(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	newVerifiedUser(t, d, "api-login@sjtu.edu.cn", "接口登录", "Password123!@#", true)

	// 1. 成功登录：result=ok + Cookie
	body := []byte(`{"email": "api-login@sjtu.edu.cn", "password": "Password123!@#"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("登录应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	var out LoginOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out.Result != "ok" {
		t.Fatalf("result 应为 ok: %+v", out)
	}
	if sc := rec.Header().Get("Set-Cookie"); !strings.Contains(sc, "ow_session=") {
		t.Fatalf("应发会话 Cookie: %q", sc)
	}

	// 2. 错密码：401 统一文案，无 Cookie
	body = []byte(`{"email": "api-login@sjtu.edu.cn", "password": "WrongPass!@#1"}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("错密码应 401，得到 %d", rec.Code)
	}
	if strings.Contains(rec.Header().Get("Set-Cookie"), "ow_session") {
		t.Fatalf("错密码不应发会话 Cookie")
	}

	// 3. 未验证用户：result=verify_required，无 Cookie，信已入队
	mustRegister(t, svc, "api-fresh@sjtu.edu.cn", "接口新人", "Password123!@#")
	body = []byte(`{"email": "api-fresh@sjtu.edu.cn", "password": "Password123!@#"}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("未验证登录应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out.Result != "verify_required" {
		t.Fatalf("result 应为 verify_required: %+v", out)
	}
	if strings.Contains(rec.Header().Get("Set-Cookie"), "ow_session") {
		t.Fatalf("未验证登录不应发会话 Cookie")
	}

	// 4. 空体：422
	req = httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("空体应 422，得到 %d", rec.Code)
	}
}

func TestLoginApiRateLimit(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, clk)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil },
		api.WithLimiter(enforcer),
	)

	// AuthLogin 30 次/分/IP：前 30 次 401（邮箱不存在），第 31 次 429
	hit := func() int {
		body := []byte(`{"email": "anyone@sjtu.edu.cn", "password": "Whatever123!@#"}`)
		req := httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = "192.0.2.77:54321"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		return rec.Code
	}
	for i := 1; i <= 30; i++ {
		if c := hit(); c != http.StatusUnauthorized {
			t.Fatalf("第 %d 次应 401，得到 %d", i, c)
		}
	}
	if c := hit(); c != http.StatusTooManyRequests {
		t.Fatalf("第 31 次应 429，得到 %d", c)
	}
}

// TestSessionCookieOnlyFromAuthRoutes 钉住「唯一建会话入口」（12 号文档 5.7）：
// 除 /api/auth/login、/api/auth/verify-email 外，任何接口的任何答复都不带
// ow_session；这两个接口的错误答复也不带。
func TestSessionCookieOnlyFromAuthRoutes(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	seen := map[string]bool{}
	for _, rt := range reg.Routes() {
		var req *http.Request
		switch rt.Method {
		case http.MethodGet:
			req = httptest.NewRequest(http.MethodGet, rt.Pattern, nil)
		default:
			req = httptest.NewRequest(rt.Method, rt.Pattern, bytes.NewReader([]byte(`{}`)))
			req.Header.Set("Content-Type", "application/json")
		}
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		seen[rt.Method+" "+rt.Pattern] = true
		for _, sc := range rec.Header().Values("Set-Cookie") {
			if strings.Contains(sc, "ow_session=") {
				t.Fatalf("%s %s 的答复不该带会话 Cookie: %q", rt.Method, rt.Pattern, sc)
			}
		}
	}
	// 路由清单里确实有这些接口（防止路由改名后这条测试空转）
	if !seen["POST /api/auth/login"] || !seen["POST /api/auth/verify-email"] || !seen["POST /api/auth/resend-code"] || !seen["POST /api/auth/reset-password"] || !seen["POST /api/auth/reset-password/confirm"] || !seen["POST /api/auth/change-password"] || !seen["POST /api/auth/logout"] {
		t.Fatalf("注册表应包含 login、verify-email、resend-code、reset-password、reset-password/confirm、change-password 和 logout: %v", seen)
	}
}

func TestResendCodeApi(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("654321")

	// 注册一个未验证账号
	mustRegister(t, svc, "unverified@sjtu.edu.cn", "未验用户", "Password123!@#")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	// 1. 未验证账号请求重发：200，无会话 Cookie，返回 message
	body := []byte(`{"email": "unverified@sjtu.edu.cn"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/resend-code", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("重发验证码应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	for _, sc := range rec.Header().Values("Set-Cookie") {
		if strings.Contains(sc, "ow_session=") {
			t.Fatalf("重发验证码绝对不发会话 Cookie: %q", sc)
		}
	}
	var out ResendCodeOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out.Email != "unverified@sjtu.edu.cn" || out.Message == "" {
		t.Fatalf("出参不符: %+v", out)
	}

	// 2. 未注册账号请求重发：静默 200，防止账号枚举（R004）
	body = []byte(`{"email": "nobody@sjtu.edu.cn"}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/resend-code", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("未注册账号应 200（防枚举），得到 %d", rec.Code)
	}

	// 3. 入参非法（空邮箱）：422
	body = []byte(`{"email": ""}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/resend-code", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("邮箱空应 422，得到 %d", rec.Code)
	}
}

func TestResendCodeApiRateLimitIP(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, clk)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil },
		api.WithLimiter(enforcer),
	)

	// AuthResendEmailCode 10 次/分/IP：前 10 次成功，第 11 次 429
	hit := func(idx int) int {
		email := fmt.Sprintf("rl%d@sjtu.edu.cn", idx)
		body := []byte(fmt.Sprintf(`{"email": %q}`, email))
		req := httptest.NewRequest(http.MethodPost, "/api/auth/resend-code", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = "192.0.2.77:54321"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		return rec.Code
	}
	for i := 1; i <= 10; i++ {
		if c := hit(i); c != http.StatusOK {
			t.Fatalf("第 %d 次应 200，得到 %d", i, c)
		}
	}
	if c := hit(11); c != http.StatusTooManyRequests {
		t.Fatalf("第 11 次应 429，得到 %d", c)
	}
}

func TestResendCodeApiRateLimitKey(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	enforcer := ratelimit.NewEnforcer(d, clk)
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, enforcer)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil },
		api.WithLimiter(enforcer),
	)

	hit := func(ip string) int {
		body := []byte(`{"email": "perkey@sjtu.edu.cn"}`)
		req := httptest.NewRequest(http.MethodPost, "/api/auth/resend-code", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = ip
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		return rec.Code
	}

	// 第一次从 IP A：成功
	if c := hit("192.0.2.1:1111"); c != http.StatusOK {
		t.Fatalf("第 1 次应 200，得到 %d", c)
	}
	// 第二次即使从不同 IP B：仍被同一账号的 1/10s 限制挡住（R006）
	if c := hit("192.0.2.2:2222"); c != http.StatusTooManyRequests {
		t.Fatalf("第 2 次换 IP 也应 429，得到 %d", c)
	}
}

func TestVerifyEmailApiRateLimit(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, clk)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil },
		api.WithLimiter(enforcer),
	)

	// AuthVerifyEmail 10 次/分/IP：前 10 次 422（码不对），第 11 次 429
	hit := func() int {
		body := []byte(`{"email": "rl@sjtu.edu.cn", "code": "000000"}`)
		req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = "192.0.2.88:54321"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		return rec.Code
	}
	for i := 1; i <= 10; i++ {
		if c := hit(); c != http.StatusUnprocessableEntity {
			t.Fatalf("第 %d 次应 422，得到 %d", i, c)
		}
	}
	if c := hit(); c != http.StatusTooManyRequests {
		t.Fatalf("第 11 次应 429，得到 %d", c)
	}
}

func TestResetPasswordApi(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("654321")

	newVerifiedUser(t, d, "rp-api@sjtu.edu.cn", "重置接口", "Password123!@#", true)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	// 1. 正常请求重置：200，无会话 Cookie，返回 message
	body := []byte(`{"email": "rp-api@sjtu.edu.cn"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/reset-password", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("找回密码应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	for _, sc := range rec.Header().Values("Set-Cookie") {
		if strings.Contains(sc, "ow_session=") {
			t.Fatalf("找回密码绝对不发会话 Cookie: %q", sc)
		}
	}
	var out ResetPasswordOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化失败: %v", err)
	}
	if out.Email != "rp-api@sjtu.edu.cn" || !strings.Contains(out.Message, "验证码") {
		t.Fatalf("出参不符: %+v", out)
	}

	// 2. 参数非法（邮箱格式错误）：422
	badReq := httptest.NewRequest(http.MethodPost, "/api/auth/reset-password", bytes.NewReader([]byte(`{"email": "bad-email"}`)))
	badReq.Header.Set("Content-Type", "application/json")
	badRec := httptest.NewRecorder()
	handler.ServeHTTP(badRec, badReq)
	if badRec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("非法邮箱应 422，得到 %d: %s", badRec.Code, badRec.Body.String())
	}
}

func TestResetPasswordApiRateLimit(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("654321")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, clk)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil },
		api.WithLimiter(enforcer),
	)

	// AuthResetPassword: 20 次/分/IP
	for i := 1; i <= 20; i++ {
		body := []byte(fmt.Sprintf(`{"email": "user%d@sjtu.edu.cn"}`, i))
		req := httptest.NewRequest(http.MethodPost, "/api/auth/reset-password", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = "192.0.2.77:12345"
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Fatalf("第 %d 次应成功，得到 %d: %s", i, rec.Code, rec.Body.String())
		}
	}

	// 第 21 次应被 IP 限流 429
	req := httptest.NewRequest(http.MethodPost, "/api/auth/reset-password", bytes.NewReader([]byte(`{"email": "user21@sjtu.edu.cn"}`)))
	req.Header.Set("Content-Type", "application/json")
	req.RemoteAddr = "192.0.2.77:12345"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("第 21 次应 429，得到 %d: %s", rec.Code, rec.Body.String())
	}
	if rec.Header().Get("Retry-After") == "" {
		t.Fatalf("429 应包含 Retry-After")
	}
}

func TestResetPasswordConfirmApi(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	svc.codeGen = fixedCode("123456")

	newVerifiedUser(t, d, "confirm-api@sjtu.edu.cn", "确认接口", "OldPass123!@#", true)
	_, _ = svc.RequestPasswordReset(context.Background(), ResetPasswordInput{Email: "confirm-api@sjtu.edu.cn"})

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	handler := reg.Handler(func(*http.Request) *app.Viewer { return nil })

	// 1. 错码：422，无 Cookie
	badBody := []byte(`{"email": "confirm-api@sjtu.edu.cn", "code": "000000", "password": "NewPassword123!@#", "confirm_password": "NewPassword123!@#"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/reset-password/confirm", bytes.NewReader(badBody))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("错码应 422，得到 %d: %s", rec.Code, rec.Body.String())
	}
	for _, sc := range rec.Header().Values("Set-Cookie") {
		if strings.Contains(sc, "ow_session=") {
			t.Fatalf("核验失败不该发会话 Cookie: %q", sc)
		}
	}

	// 2. 正确重置：200，依然绝对不发会话 Cookie（5.7 唯一入口规则）
	okBody := []byte(`{"email": "confirm-api@sjtu.edu.cn", "code": "123456", "password": "NewPassword123!@#", "confirm_password": "NewPassword123!@#"}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/reset-password/confirm", bytes.NewReader(okBody))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("成功重置应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	for _, sc := range rec.Header().Values("Set-Cookie") {
		if strings.Contains(sc, "ow_session=") {
			t.Fatalf("重置密码成功绝对不发会话 Cookie（必须去登录页登录）: %q", sc)
		}
	}
	var out ResetPasswordConfirmOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatalf("反序列化失败: %v", err)
	}
	if out.Result != "ok" || !strings.Contains(out.Message, "成功") {
		t.Fatalf("出参不符: %+v", out)
	}
}

func TestChangePasswordApi(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	u := newVerifiedUser(t, d, "cp-api@sjtu.edu.cn", "改密接口", "OldPass123!@#", true)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)

	var currentViewer *app.Viewer
	handler := reg.Handler(func(*http.Request) *app.Viewer {
		return currentViewer
	})

	// 1. 访客访问：401 Unauthorized（Member 门）
	currentViewer = nil
	body := []byte(`{"old_password": "OldPass123!@#", "password": "NewPass123!@#", "confirm_password": "NewPass123!@#"}`)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("访客应 401，得到 %d: %s", rec.Code, rec.Body.String())
	}

	// 2. 停用账号：401
	currentViewer = &app.Viewer{ID: u.ID, Disabled: true}
	req = httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("停用账号应 401，得到 %d", rec.Code)
	}

	// 3. 正常成员当前密码错误：422
	v, err := svc.BuildViewer(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}
	currentViewer = v
	wrongBody := []byte(`{"old_password": "WrongPassword123!@#", "password": "NewPass123!@#", "confirm_password": "NewPass123!@#"}`)
	req = httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(wrongBody))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("密码错误应 422，得到 %d: %s", rec.Code, rec.Body.String())
	}

	// 4. 正常成员成功修改：200
	req = httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("修改成功应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}
	var out ChangePasswordOut
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out.Result != "ok" || !strings.Contains(out.Message, "成功") {
		t.Fatalf("出参不符: %+v", out)
	}
}

func TestChangePasswordApiRateLimit(t *testing.T) {
	d := newTestDB(t)
	clk := clock.Fixed(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC))
	svc := NewService(d, clk, "https://sjtu.ow-shanghaiuniversity.com", nil, nil)
	u1 := newVerifiedUser(t, d, "cp-rl1@sjtu.edu.cn", "限流用户1", "OldPass123!@#", true)
	u2 := newVerifiedUser(t, d, "cp-rl2@sjtu.edu.cn", "限流用户2", "OldPass123!@#", true)

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, clk)

	var currentViewer *app.Viewer
	handler := reg.Handler(func(*http.Request) *app.Viewer { return currentViewer },
		api.WithLimiter(enforcer),
	)

	// AuthChangePassword: 5 次/分/人（PerUser）
	currentViewer = &app.Viewer{ID: u1.ID}
	body := []byte(`{"old_password": "wrong", "password": "NewPass123!@#", "confirm_password": "NewPass123!@#"}`)
	for i := 1; i <= 5; i++ {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		// 校验返回 422，但通过了限流器
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("第 %d 次应 422，得到 %d", i, rec.Code)
		}
	}

	// 第 6 次：429 Too Many Requests
	req := httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("第 6 次应 429，得到 %d: %s", rec.Code, rec.Body.String())
	}
	if rec.Header().Get("Retry-After") == "" {
		t.Fatal("429 应包含 Retry-After")
	}

	// 换成用户 2，不应受用户 1 的限流影响
	currentViewer = &app.Viewer{ID: u2.ID}
	req = httptest.NewRequest(http.MethodPost, "/api/auth/change-password", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("用户 2 首次应 422（通过限流），得到 %d", rec.Code)
	}
}

func TestLogoutApi(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	sessions := auth.NewStore(d, nil)
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com", sessions, nil)
	u := newVerifiedUser(t, d, "logout-api@sjtu.edu.cn", "退出接口", "Pass123!@#", true)
	token, err := sessions.Create(ctx, u.ID)
	if err != nil {
		t.Fatal(err)
	}

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)

	var currentViewer *app.Viewer
	handler := reg.Handler(func(*http.Request) *app.Viewer { return currentViewer })

	// 1. 访客访问：401
	currentViewer = nil
	req := httptest.NewRequest(http.MethodPost, "/api/auth/logout", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("访客应 401，得到 %d", rec.Code)
	}

	// 2. 登录成员调用退出：200，且响应头包含清除 Cookie
	currentViewer = &app.Viewer{ID: u.ID}
	req = httptest.NewRequest(http.MethodPost, "/api/auth/logout", bytes.NewReader([]byte(`{}`)))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(&http.Cookie{Name: auth.CookieName, Value: token})
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("退出应 200，得到 %d: %s", rec.Code, rec.Body.String())
	}

	// 验证 Set-Cookie 包含了清除指令（Max-Age: -1 或 Max-Age: 0，或清空值）
	var cleared bool
	for _, c := range rec.Result().Cookies() {
		if c.Name == auth.CookieName && (c.MaxAge < 0 || c.Value == "") {
			cleared = true
			break
		}
	}
	if !cleared {
		t.Fatalf("响应头应清除会话 Cookie: %+v", rec.Header().Values("Set-Cookie"))
	}

	// 验证库中会话已删除
	if sess, err := sessions.Lookup(ctx, token); err != nil || sess != nil {
		t.Fatalf("库中会话应已删除，得到 %+v", sess)
	}
}
