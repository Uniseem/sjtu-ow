package api

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	stdb "github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/idempotency"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// mutClock 是测试里能拨的时钟。
type mutClock struct {
	mu sync.Mutex
	t  time.Time
}

func (c *mutClock) Now() time.Time  { c.mu.Lock(); defer c.mu.Unlock(); return c.t }
func (c *mutClock) Set(t time.Time) { c.mu.Lock(); defer c.mu.Unlock(); c.t = t }

func newTestDB(t *testing.T) *stdb.DB {
	t.Helper()
	d, err := stdb.Open(filepath.Join(t.TempDir(), "test.sqlite"), stdb.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := stdb.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func postJSON(t *testing.T, h http.Handler, target, body string, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("POST", target, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Test-Viewer", "member")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

// ---- 限流 ----

func TestRateLimit429WithRetryAfter(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Date(2026, 10, 8, 12, 0, 30, 0, time.UTC)}
	g := &Registry{}
	Post(g, "/api/ping", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "t_ping", Kind: ratelimit.PerUser, N: 2, Window: time.Minute}))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))

	for i := 1; i <= 2; i++ {
		if rec := postJSON(t, h, "/api/ping", `{}`, nil); rec.Code != 200 {
			t.Fatalf("第 %d 次应 200，得到 %d", i, rec.Code)
		}
	}
	rec := postJSON(t, h, "/api/ping", `{}`, nil)
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("第 3 次应 429，得到 %d（%s）", rec.Code, rec.Body.String())
	}
	if ra := rec.Header().Get("Retry-After"); ra != "30" {
		t.Fatalf("Retry-After 应是到下一分钟的 30 秒，得到 %q", ra)
	}
	if !strings.Contains(rec.Body.String(), "rate_limited") {
		t.Fatalf("错误码不对：%s", rec.Body.String())
	}

	// 过了这一分钟，新的时间片重新计数
	clk.Set(clk.Now().Add(31 * time.Second))
	if rec := postJSON(t, h, "/api/ping", `{}`, nil); rec.Code != 200 {
		t.Fatalf("新时间片应 200，得到 %d", rec.Code)
	}
}

func TestRateLimitSeparateUsersAndIPs(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	g := &Registry{}
	Post(g, "/api/ping", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "t_ping2", Kind: ratelimit.PerIP, N: 1, Window: time.Minute}))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))

	do := func(remote string) int {
		req := httptest.NewRequest("POST", "/api/ping", strings.NewReader("{}"))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Test-Viewer", "member")
		req.RemoteAddr = remote
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code
	}
	if c := do("198.51.100.1:1234"); c != 200 {
		t.Fatalf("第一个 IP 应 200：%d", c)
	}
	if c := do("198.51.100.2:1234"); c != 200 {
		t.Fatalf("第二个 IP 不该被第一个 IP 连累：%d", c)
	}
	if c := do("198.51.100.1:1235"); c != http.StatusTooManyRequests {
		t.Fatalf("同一个 IP 第二次应 429：%d", c)
	}
}

// 不可信来源自带的 X-Real-IP 一律不认：计数落在真实来源上，伪造不了别人。
func TestXRealIPOnlyFromTrustedProxies(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	trusted := []*net.IPNet{mustCIDR(t, "10.0.0.0/8")}
	g := &Registry{}
	Post(g, "/api/ping", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "t_ping3", Kind: ratelimit.PerIP, N: 1, Window: time.Minute}))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)), WithTrustedProxies(trusted))

	do := func(remote string) int {
		req := httptest.NewRequest("POST", "/api/ping", strings.NewReader("{}"))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Test-Viewer", "member")
		req.Header.Set("X-Real-IP", "203.0.113.7") // 想冒充的地址
		req.RemoteAddr = remote
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code
	}

	if c := do("198.51.100.5:1"); c != 200 {
		t.Fatalf("第一次应 200：%d", c)
	}
	if c := do("198.51.100.5:2"); c != 429 {
		t.Fatalf("同一真实来源第二次应 429（说明伪造的 X-Real-IP 没被采信）：%d", c)
	}
	if c := do("198.51.100.6:1"); c != 200 {
		t.Fatalf("换一个来源应重新 200：%d", c)
	}
	// 可信代理带来的 X-Real-IP 要采信：两个不同的代理连接、同一个真实访客，算一个人
	if c := do("10.0.0.1:1"); c != 200 {
		t.Fatalf("可信代理的第一访客应 200：%d", c)
	}
	if c := do("10.0.0.2:1"); c != 429 {
		t.Fatalf("可信代理后面同一个访客（X-Real-IP 相同）应 429：%d", c)
	}
}

// IPv6 折叠成 /64：同一前缀里的地址共用一个计数。
func TestIPv6CollapsedToSlash64(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	g := &Registry{}
	Post(g, "/api/ping", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "t_ping6", Kind: ratelimit.PerIP, N: 1, Window: time.Minute}))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))

	do := func(addr string) int {
		req := httptest.NewRequest("POST", "/api/ping", strings.NewReader("{}"))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Test-Viewer", "member")
		req.RemoteAddr = addr
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code
	}
	if c := do("[2001:db8:aaaa:bbbb::1]:1"); c != 200 {
		t.Fatalf("第一个 v6 地址应 200：%d", c)
	}
	if c := do("[2001:db8:aaaa:bbbb::2]:1"); c != 429 {
		t.Fatalf("同 /64 的第二个地址应被算作同一个访客（429）：%d", c)
	}
	if c := do("[2001:db8:aaaa:cccc::1]:1"); c != 200 {
		t.Fatalf("不同 /64 是另一个访客：%d", c)
	}
}

// ---- 幂等键 ----

// 处理函数每跑一次计数加一并把计数放进回执——重放的话两次回执一样、只跑一次。
func TestIdempotencyReplaysReceipt(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	var calls atomic.Int64
	g := &Registry{}
	Post(g, "/api/actions", Member, func(*app.Ctx, struct{}) (struct {
		Call int64 `json:"call"`
	}, error) {
		return struct {
			Call int64 `json:"call"`
		}{Call: calls.Add(1)}, nil
	}, Limit(ratelimit.Decl{Name: "t_idem", Kind: ratelimit.PerUser, N: 100, Window: time.Minute}))
	h := g.Handler(testResolve, WithIdempotency(idempotency.NewStore(d, clk)))

	hdrs := map[string]string{"Idempotency-Key": "abc"}
	first := postJSON(t, h, "/api/actions", `{}`, hdrs)
	if first.Code != 200 || first.Body.String() != `{"call":1}` {
		t.Fatalf("第一次：%d %q", first.Code, first.Body.String())
	}
	second := postJSON(t, h, "/api/actions", `{}`, hdrs)
	if second.Code != 200 || second.Body.String() != first.Body.String() {
		t.Fatalf("重放应原样回回执：%d %q", second.Code, second.Body.String())
	}
	if calls.Load() != 1 {
		t.Fatalf("处理函数只该跑一次，跑了 %d 次", calls.Load())
	}
}

func TestIdempotencyBusyWhileInFlight(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	store := idempotency.NewStore(d, clk)
	// 直接占住这个键，模拟「上一个同键请求还在处理」
	outcome, _, err := store.Claim(context.Background(), 3, "busy-key", "POST", "/api/actions")
	if err != nil || outcome != idempotency.Created {
		t.Fatalf("预占：outcome=%v err=%v", outcome, err)
	}

	g := &Registry{}
	Post(g, "/api/actions", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "t_idem2", Kind: ratelimit.PerUser, N: 100, Window: time.Minute}))
	h := g.Handler(testResolve, WithIdempotency(store))

	rec := postJSON(t, h, "/api/actions", `{}`, map[string]string{"Idempotency-Key": "busy-key"})
	if rec.Code != http.StatusConflict {
		t.Fatalf("处理中的同键请求应 409，得到 %d（%s）", rec.Code, rec.Body.String())
	}
}

func TestIdempotencyMismatchedPath(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	store := idempotency.NewStore(d, clk)
	if _, _, err := store.Claim(context.Background(), 3, "k", "POST", "/api/other"); err != nil {
		t.Fatal(err)
	}

	g := &Registry{}
	Post(g, "/api/actions", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "t_idem3", Kind: ratelimit.PerUser, N: 100, Window: time.Minute}))
	h := g.Handler(testResolve, WithIdempotency(store))

	rec := postJSON(t, h, "/api/actions", `{}`, map[string]string{"Idempotency-Key": "k"})
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("键用在别的地址应 400，得到 %d", rec.Code)
	}
}

func TestIdempotencyKeyExpiresAfter24h(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	store := idempotency.NewStore(d, clk)
	if _, _, err := store.Claim(context.Background(), 3, "old", "POST", "/api/actions"); err != nil {
		t.Fatal(err)
	}
	if err := store.Complete(context.Background(), 3, "old", 200, []byte(`{}`)); err != nil {
		t.Fatal(err)
	}

	clk.Set(clk.Now().Add(25 * time.Hour))
	outcome, _, err := store.Claim(context.Background(), 3, "old", "POST", "/api/actions")
	if err != nil || outcome != idempotency.Created {
		t.Fatalf("过期的键应能重新认领：outcome=%v err=%v", outcome, err)
	}
}

// 处理出错的请求要释放认领：同一个键的重试真的会再跑一遍。
func TestIdempotencyReleasedOnError(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	var calls atomic.Int64
	fail := true
	g := &Registry{}
	Post(g, "/api/actions", Member, func(*app.Ctx, struct{}) (struct {
		Call int64 `json:"call"`
	}, error) {
		n := calls.Add(1)
		if fail {
			fail = false
			return struct {
				Call int64 `json:"call"`
			}{}, Invalid("第一次故意失败")
		}
		return struct {
			Call int64 `json:"call"`
		}{Call: n}, nil
	}, Limit(ratelimit.Decl{Name: "t_idem4", Kind: ratelimit.PerUser, N: 100, Window: time.Minute}))
	h := g.Handler(testResolve, WithIdempotency(idempotency.NewStore(d, clk)))

	hdrs := map[string]string{"Idempotency-Key": "retry"}
	first := postJSON(t, h, "/api/actions", `{}`, hdrs)
	if first.Code != http.StatusBadRequest {
		t.Fatalf("第一次应 400：%d", first.Code)
	}
	second := postJSON(t, h, "/api/actions", `{}`, hdrs)
	if second.Code != 200 || calls.Load() != 2 {
		t.Fatalf("出错后同键重试应重新处理：%d calls=%d", second.Code, calls.Load())
	}
}

// 幂等只对登录用户生效：访客带同一个键，每次都真处理。
func TestIdempotencyIgnoredForAnonymous(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	var calls atomic.Int64
	g := &Registry{}
	Post(g, "/api/open", Public, func(*app.Ctx, struct{}) (struct {
		Call int64 `json:"call"`
	}, error) {
		return struct {
			Call int64 `json:"call"`
		}{Call: calls.Add(1)}, nil
	}, NoLimit("测试"))
	h := g.Handler(testResolve, WithIdempotency(idempotency.NewStore(d, clk)))

	hdrs := map[string]string{"Idempotency-Key": "anon"}
	for i := 0; i < 2; i++ {
		req := httptest.NewRequest("POST", "/api/open", strings.NewReader("{}"))
		req.Header.Set("Content-Type", "application/json")
		for k, v := range hdrs {
			req.Header.Set(k, v)
		}
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if rec.Code != 200 {
			t.Fatalf("第 %d 次：%d", i+1, rec.Code)
		}
	}
	if calls.Load() != 2 {
		t.Fatalf("访客的幂等键不该挡处理，跑了 %d 次", calls.Load())
	}
}

// 一个接口可以同时挂两条：先撞上的那条决定 429（评论就是每分钟和每天两条）。
func TestTwoLimitsOnOneRoute(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	g := &Registry{}
	Post(g, "/api/ping", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(
		ratelimit.Decl{Name: "loose", Kind: ratelimit.PerUser, N: 10, Window: time.Minute},
		ratelimit.Decl{Name: "tight", Kind: ratelimit.PerUser, N: 1, Window: time.Minute},
	))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))
	if rec := postJSON(t, h, "/api/ping", `{}`, nil); rec.Code != 200 {
		t.Fatalf("第一次应 200：%d", rec.Code)
	}
	if rec := postJSON(t, h, "/api/ping", `{}`, nil); rec.Code != http.StatusTooManyRequests {
		t.Fatalf("紧的那条（1 次）应把第二次拦成 429：%d", rec.Code)
	}
}

// 「每小时 5 次」按小时片计：过了一分钟仍在这一小时里，第 6 次还是 429。
func TestHourlyLimitUsesHourSlice(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Date(2026, 10, 8, 12, 0, 30, 0, time.UTC)}
	g := &Registry{}
	Post(g, "/api/export", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.AccountExport))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))
	for i := 1; i <= 5; i++ {
		if rec := postJSON(t, h, "/api/export", `{}`, nil); rec.Code != 200 {
			t.Fatalf("第 %d 次应 200：%d", i, rec.Code)
		}
	}
	clk.Set(clk.Now().Add(time.Minute))
	rec := postJSON(t, h, "/api/export", `{}`, nil)
	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("同一小时里第 6 次应 429：%d", rec.Code)
	}
	if ra := rec.Header().Get("Retry-After"); ra == "" || ra == "30" || ra == "29" {
		t.Fatalf("Retry-After 应到下一小时，得到 %q", ra)
	}
	clk.Set(time.Date(2026, 10, 8, 13, 0, 1, 0, time.UTC))
	if rec := postJSON(t, h, "/api/export", `{}`, nil); rec.Code != 200 {
		t.Fatalf("下一小时应重新 200：%d", rec.Code)
	}
}

// 「每天 3 次」按天片计：过了两小时仍是今天，第 4 次还是 429。
func TestDailyLimitUsesDaySlice(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)}
	g := &Registry{}
	Post(g, "/api/teams", Member, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.TeamCreate))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))
	for i := 1; i <= 3; i++ {
		if rec := postJSON(t, h, "/api/teams", `{}`, nil); rec.Code != 200 {
			t.Fatalf("第 %d 次应 200：%d", i, rec.Code)
		}
	}
	clk.Set(clk.Now().Add(2 * time.Hour))
	if rec := postJSON(t, h, "/api/teams", `{}`, nil); rec.Code != http.StatusTooManyRequests {
		t.Fatalf("同一天里第 4 次应 429：%d", rec.Code)
	}
	clk.Set(time.Date(2026, 10, 9, 0, 0, 1, 0, time.UTC))
	if rec := postJSON(t, h, "/api/teams", `{}`, nil); rec.Code != 200 {
		t.Fatalf("下一天应重新 200：%d", rec.Code)
	}
}

// 没登录的人走 per_user 时按 IP 计（登录、验证码这类匿名接口）。
func TestPerUserFallsBackToIPWhenAnonymous(t *testing.T) {
	d := newTestDB(t)
	clk := &mutClock{t: time.Now()}
	g := &Registry{}
	Post(g, "/api/open", Public, func(*app.Ctx, struct{}) (struct{}, error) {
		return struct{}{}, nil
	}, Limit(ratelimit.Decl{Name: "anon", Kind: ratelimit.PerUser, N: 1, Window: time.Minute}))
	h := g.Handler(testResolve, WithLimiter(ratelimit.NewEnforcer(d, clk)))

	do := func(remote string) int {
		req := httptest.NewRequest("POST", "/api/open", strings.NewReader("{}"))
		req.Header.Set("Content-Type", "application/json")
		req.RemoteAddr = remote
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code
	}
	if c := do("198.51.100.9:1"); c != 200 {
		t.Fatalf("第一次应 200：%d", c)
	}
	if c := do("198.51.100.9:2"); c != http.StatusTooManyRequests {
		t.Fatalf("同一 IP 第二次应 429：%d", c)
	}
	if c := do("198.51.100.10:1"); c != 200 {
		t.Fatalf("另一个 IP 应重新 200：%d", c)
	}
}

func mustCIDR(t *testing.T, s string) *net.IPNet {
	t.Helper()
	_, n, err := net.ParseCIDR(s)
	if err != nil {
		t.Fatal(err)
	}
	return n
}
