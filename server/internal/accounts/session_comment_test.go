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

func TestSessionCommentAbilityIndependentOfEmail(t *testing.T) {
	for _, tc := range []struct {
		name                  string
		verified, groupDenied bool
		superuser             bool
		userDenied            *bool
		want                  bool
	}{
		{"unverified default", false, false, false, nil, true},
		{"unverified user denied", false, false, false, boolPtr(true), false},
		{"verified user denied", true, false, false, boolPtr(true), false},
		{"unverified group denied", false, true, false, nil, false},
		{"explicit allow overrides group", false, true, false, boolPtr(false), true},
		{"verified default", true, false, false, nil, true},
		{"superuser overrides denial", false, true, true, boolPtr(true), true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			d := newTestDB(t)
			ctx := context.Background()
			svc := NewService(d, nil, "https://example.test", nil, nil)
			now := time.Date(2026, 10, 10, 0, 0, 0, 0, time.UTC)
			u := &User{Email: "member@example.test", EmailNorm: "member@example.test", PasswordHash: "h", Nickname: "成员", IsSJTU: true, IsActive: true, AgreedTermsAt: now, AgreedCrossBorderAt: now, CreatedAt: now, UpdatedAt: now, Version: 1}
			u.IsSuperuser = tc.superuser
			if tc.verified {
				u.EmailVerifiedAt = &now
			}
			if err := d.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
				if _, err := svc.store.InsertUser(ctx, tx, u); err != nil {
					return err
				}
				if tc.groupDenied {
					if err := svc.store.SetFeatureRoleRestriction(ctx, tx, RoleSJTU, FeatureArticleComment, now); err != nil {
						return err
					}
				}
				if tc.userDenied != nil {
					return svc.store.SetFeatureUserRule(ctx, tx, u.ID, FeatureArticleComment, *tc.userDenied, now)
				}
				return nil
			}); err != nil {
				t.Fatal(err)
			}
			viewer, err := svc.BuildViewer(ctx, u.ID)
			if err != nil {
				t.Fatal(err)
			}
			reg := &api.Registry{}
			NewModule(svc).Routes(reg)
			h := reg.Handler(func(*http.Request) *app.Viewer { return viewer })
			rec := httptest.NewRecorder()
			h.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/session?refresh=true", nil))
			if rec.Code != 200 {
				t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
			}
			var raw struct{ User map[string]any }
			if err := json.Unmarshal(rec.Body.Bytes(), &raw); err != nil {
				t.Fatal(err)
			}
			if raw.User["can_comment"] != tc.want || raw.User["email_verified"] != tc.verified {
				t.Fatalf("session=%v", raw.User)
			}
			if !tc.verified && !tc.superuser && viewer.HasCap("articles.publish_own") {
				t.Fatal("fixture should have no publish capability")
			}
		})
	}
}
