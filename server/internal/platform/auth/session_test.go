package auth

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

type testClock struct{ t time.Time }

func (c *testClock) Now() time.Time { return c.t }

func newAuthDB(t *testing.T) *db.DB {
	t.Helper()
	d, err := db.Open(filepath.Join(t.TempDir(), "test.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatalf("Open: %v", err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatalf("Migrate: %v", err)
	}
	t.Cleanup(func() { _ = d.Close() })
	return d
}

func TestSessionCreateLookupAndExpiry(t *testing.T) {
	d := newAuthDB(t)
	clk := &testClock{t: time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)}
	s := NewStore(d, clk)

	token, err := s.Create(context.Background(), 7)
	if err != nil {
		t.Fatal(err)
	}
	sess, err := s.Lookup(context.Background(), token)
	if err != nil || sess == nil || sess.UserID != 7 {
		t.Fatalf("应找到用户 7：%+v err=%v", sess, err)
	}
	if !sess.ExpiresAt.Equal(clk.t.Add(SessionTTL)) {
		t.Fatalf("应 14 天后过期：%s", sess.ExpiresAt)
	}
	if sess.RecentlyReauthed(clk.t) {
		t.Fatal("还没重新认证")
	}

	if got, err := s.Lookup(context.Background(), "@@@"); err != nil || got != nil {
		t.Fatalf("坏令牌应是没有会话：%v %v", got, err)
	}

	clk.t = clk.t.Add(SessionTTL)
	if got, err := s.Lookup(context.Background(), token); err != nil || got != nil {
		t.Fatalf("到期应是没有会话：%v %v", got, err)
	}
}

func TestDeleteOthersKeepsCurrent(t *testing.T) {
	d := newAuthDB(t)
	clk := &testClock{t: time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)}
	s := NewStore(d, clk)
	a, err := s.Create(context.Background(), 7)
	if err != nil {
		t.Fatal(err)
	}
	b, err := s.Create(context.Background(), 7)
	if err != nil {
		t.Fatal(err)
	}
	other, err := s.Create(context.Background(), 8)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.DeleteOthers(context.Background(), 7, a); err != nil {
		t.Fatal(err)
	}
	if got, _ := s.Lookup(context.Background(), a); got == nil {
		t.Fatal("当前这条应还在")
	}
	if got, _ := s.Lookup(context.Background(), b); got != nil {
		t.Fatal("同一个人的另一条应删掉")
	}
	if got, _ := s.Lookup(context.Background(), other); got == nil {
		t.Fatal("别人的会话不应被删")
	}

	if err := s.DeleteAll(context.Background(), 7); err != nil {
		t.Fatal(err)
	}
	if got, _ := s.Lookup(context.Background(), a); got != nil {
		t.Fatal("全部删掉后当前这条也不在了")
	}
	if got, _ := s.Lookup(context.Background(), other); got == nil {
		t.Fatal("别人的还在")
	}
}

func TestReauthWindowAndTouch(t *testing.T) {
	d := newAuthDB(t)
	clk := &testClock{t: time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)}
	s := NewStore(d, clk)
	token, err := s.Create(context.Background(), 7)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.MarkReauth(context.Background(), token); err != nil {
		t.Fatal(err)
	}
	sess, err := s.Lookup(context.Background(), token)
	if err != nil || !sess.RecentlyReauthed(clk.t) {
		t.Fatalf("刚认证应算数：%+v err=%v", sess, err)
	}
	if sess.RecentlyReauthed(clk.t.Add(ReauthWindow + time.Second)) {
		t.Fatal("过了 5 分钟不算")
	}

	// 不到一小时，Touch 不写
	clk.t = clk.t.Add(30 * time.Minute)
	if err := s.Touch(context.Background(), token); err != nil {
		t.Fatal(err)
	}
	sess, _ = s.Lookup(context.Background(), token)
	if !sess.LastSeen.Equal(time.Date(2026, 10, 8, 12, 0, 0, 0, time.UTC)) {
		t.Fatalf("半小时内不应改最后访问：%s", sess.LastSeen)
	}
	clk.t = time.Date(2026, 10, 8, 13, 0, 1, 0, time.UTC)
	if err := s.Touch(context.Background(), token); err != nil {
		t.Fatal(err)
	}
	sess, _ = s.Lookup(context.Background(), token)
	if !sess.LastSeen.Equal(clk.t) {
		t.Fatalf("过了一小时应写下新的最后访问：%s", sess.LastSeen)
	}
}

func TestCookieFlags(t *testing.T) {
	rec := httptest.NewRecorder()
	SetCookie(rec, "tok", true)
	c := rec.Result().Cookies()[0]
	if c.Name != CookieName || !c.HttpOnly || !c.Secure || c.SameSite != http.SameSiteLaxMode {
		t.Fatalf("生产 Cookie 标志不对：%+v", c)
	}
	if c.MaxAge != int(SessionTTL.Seconds()) || c.Path != "/" {
		t.Fatalf("有效期或路径不对：MaxAge=%d Path=%s", c.MaxAge, c.Path)
	}

	rec = httptest.NewRecorder()
	SetCookie(rec, "tok", false)
	if rec.Result().Cookies()[0].Secure {
		t.Fatal("开发环境不加 Secure")
	}

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.AddCookie(&http.Cookie{Name: CookieName, Value: "tok"})
	if TokenFromRequest(req) != "tok" {
		t.Fatal("没读出令牌")
	}

	rec = httptest.NewRecorder()
	ClearCookie(rec, true)
	cleared := rec.Result().Cookies()[0]
	if cleared.MaxAge >= 0 || cleared.Value != "" {
		t.Fatalf("清 Cookie 应是立刻过期：%+v", cleared)
	}
}

// 全 server/ 里只有 session.go 会往 sessions 表插行。登录接口是唯一调用方
// 的断言等 M3 有了 /api/auth/login 再钉。
func TestOnlySessionFileInserts(t *testing.T) {
	_, here, _, _ := runtime.Caller(0)
	root := filepath.Dir(filepath.Dir(filepath.Dir(filepath.Dir(here))))
	needle := "INSERT INTO " + "sessions"
	var hits []string
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() || !strings.HasSuffix(path, ".go") || strings.HasSuffix(path, "_test.go") {
			return err
		}
		body, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if strings.Contains(string(body), needle) {
			hits = append(hits, path)
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 1 || !strings.HasSuffix(hits[0], filepath.Join("auth", "session.go")) {
		t.Fatalf("应只有 session.go 插入会话，找到 %v", hits)
	}
}
