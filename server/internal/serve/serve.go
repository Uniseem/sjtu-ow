// Package serve 把 /healthz 和接口注册表挂到同一个 HTTP 服务上。
package serve

import (
	"net/http"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/api"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/health"
)

// Handler 是 sjtuow serve 对外的那一个。超管才看得到 /healthz 的详情。
func Handler(d *db.DB, dataDir string, reg *api.Registry, resolve api.ViewerResolver, opts ...api.HandlerOption) http.Handler {
	mux := http.NewServeMux()
	mux.Handle("GET /healthz", health.Handler(d, dataDir, nil, func(r *http.Request) bool {
		if resolve == nil {
			return false
		}
		v := resolve(r)
		return v != nil && v.Superuser && !v.Disabled
	}))
	mux.Handle("/", reg.Handler(resolve, opts...))
	return mux
}

// Super 给测试看详情用。停用的超管不当超管。
func Super(on bool) api.ViewerResolver {
	return func(*http.Request) *app.Viewer {
		if !on {
			return nil
		}
		return &app.Viewer{ID: 1, Superuser: true}
	}
}
