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
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

func TestGetSessionApi(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")
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
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")

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
	svc := NewService(d, nil, "https://sjtu.ow-shanghaiuniversity.com")

	reg := &api.Registry{}
	mod := NewModule(svc)
	mod.Routes(reg)
	enforcer := ratelimit.NewEnforcer(d, nil)
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
