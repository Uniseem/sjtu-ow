package serve

import (
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

func TestHealthzHidesDetailUnlessSuperuser(t *testing.T) {
	d, err := db.Open(filepath.Join(t.TempDir(), "test.sqlite"), db.WithWatchdog(10*time.Second, 0))
	if err != nil {
		t.Fatal(err)
	}
	if err := db.Migrate(context.Background(), d); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = d.Close() })
	dir := t.TempDir()

	public := httptest.NewRecorder()
	Handler(d, dir, &api.Registry{}, Super(false)).ServeHTTP(public, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if strings.Contains(public.Body.String(), "detail") {
		t.Fatalf("访客不该看到详情：%s", public.Body.String())
	}
	admin := httptest.NewRecorder()
	Handler(d, dir, &api.Registry{}, Super(true)).ServeHTTP(admin, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if !strings.Contains(admin.Body.String(), `"detail"`) {
		t.Fatalf("超管该看到详情：%s", admin.Body.String())
	}
	if public.Code != admin.Code {
		t.Fatalf("状态码应对访客和超管一样：%d %d", public.Code, admin.Code)
	}
}
