package comments

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

func TestCommentEditDailyLimit(t *testing.T) {
	d, svc := gateFixture(t)
	now := time.Date(2026, 10, 11, 0, 0, 0, 0, time.UTC)
	limiter := ratelimit.NewEnforcer(d, clock.Fixed(now))
	for range 100 {
		_, ok, err := limiter.Allow(context.Background(), "u:1", ratelimit.CommentCreateDaily)
		if err != nil || !ok {
			t.Fatalf("fixture count err=%v ok=%v", err, ok)
		}
	}
	reg := &api.Registry{}
	NewModule(svc).Routes(reg)
	request := func(limiter ratelimit.Limiter) *httptest.ResponseRecorder {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPatch, "/api/comments/100", bytes.NewBufferString(`{"content":"DAY EDIT"}`))
		req.Header.Set("Content-Type", "application/json")
		reg.Handler(func(*http.Request) *app.Viewer { return &app.Viewer{ID: 1} }, api.WithLimiter(limiter)).ServeHTTP(rec, req)
		return rec
	}
	before := gateSnapshot(t, d)
	denied := request(limiter)
	if denied.Code != 429 || denied.Header().Get("Retry-After") == "" || before != gateSnapshot(t, d) {
		t.Fatalf("daily limit status=%d body=%s", denied.Code, denied.Body.String())
	}
	allowed := request(ratelimit.NewEnforcer(d, clock.Fixed(now.Add(24*time.Hour))))
	if allowed.Code != 200 {
		t.Fatalf("next day status=%d body=%s", allowed.Code, allowed.Body.String())
	}
	saved, err := svc.store.GetCommentByID(context.Background(), 100)
	if err != nil || saved.Content != "DAY EDIT" || saved.EditedAt == nil {
		t.Fatalf("saved=%+v err=%v", saved, err)
	}
}
