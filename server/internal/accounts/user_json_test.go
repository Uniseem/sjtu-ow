package accounts

import (
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
)

func TestUserDetailJSONOmitsPasswordHash(t *testing.T) {
	u := &User{ID: 7, Nickname: "测试成员", PasswordHash: "never-expose-this-test-hash"}
	raw, err := json.Marshal(UserDetailResult{User: u, Roles: []string{}})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "PasswordHash") || strings.Contains(string(raw), u.PasswordHash) {
		t.Fatal("user detail JSON exposed the password hash")
	}
	var parsed struct {
		User struct {
			ID       int64
			Nickname string
		}
	}
	if err := json.Unmarshal(raw, &parsed); err != nil || parsed.User.ID != 7 || parsed.User.Nickname != u.Nickname {
		t.Fatalf("non-secret user fields must remain compatible: %v", err)
	}
}

func TestUserDetailHTTPNeverExposesPasswordHash(t *testing.T) {
	d := newTestDB(t)
	svc := NewService(d, nil, "https://example.test", nil, nil)
	now := time.Now().UTC()
	u := &User{Email: "projection@example.test", EmailNorm: "projection@example.test", Nickname: "测试成员", PasswordHash: "never-expose-this-http-hash", IsActive: true, AgreedTermsAt: now, AgreedCrossBorderAt: now, CreatedAt: now, UpdatedAt: now}
	if err := d.WriteTx(context.Background(), func(ctx context.Context, tx *db.Tx) error {
		id, err := svc.Store().InsertUser(ctx, tx, u)
		u.ID = id
		return err
	}); err != nil {
		t.Fatal(err)
	}
	r := &api.Registry{}
	NewModule(svc).Routes(r)
	h := r.Handler(func(*http.Request) *app.Viewer { return &app.Viewer{ID: u.ID, Superuser: true, EmailVerified: true} })
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", fmt.Sprintf("/api/admin/users/%d", u.ID), nil))
	if rec.Code != http.StatusOK || strings.Contains(rec.Body.String(), "PasswordHash") || strings.Contains(rec.Body.String(), u.PasswordHash) {
		t.Fatalf("HTTP user detail must return safe public projection: status=%d", rec.Code)
	}
}
