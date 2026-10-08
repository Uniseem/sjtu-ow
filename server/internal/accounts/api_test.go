package accounts

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestGetSessionApi(t *testing.T) {
	d := newTestDB(t)
	ctx := context.Background()
	svc := NewService(d, nil)
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
