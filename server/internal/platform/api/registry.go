// Package api 是新栈的接口注册表（12 号文档 5.3/5.4）：所有 HTTP 接口从这里
// 注册，声明门、限流、查询预算；由注册表生成路由、绑定参数、渲染统一错误，
// 守卫测试（守门矩阵、乱填、跨站写）也吃它的路由清单。
package api

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"reflect"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
)

// ViewerResolver 从请求解出「这是谁」。M1 里测试自己注入；会话中间件
// （后续轮次）从 ow_session Cookie 解出真正的 Viewer，解析不出返回 nil。
type ViewerResolver func(*http.Request) *app.Viewer

// Registry 收集路由。零值可用；一个进程一个。
type Registry struct {
	routes []*Route
}

// Route 是一条注册了的接口。守卫测试遍历它做矩阵和乱填。
type Route struct {
	Method  string
	Pattern string
	Gate    Gate

	Budget     int        // 查询数上限（查询预算测试用，5.3）
	Limit      *LimitDecl // 限流声明；写接口必须有（或写 NoLimitReason）
	NoLimitStr string     // NoLimit 的理由
	Nav        string     // 后台位置「大类/标签」（M8 用）
	PathParams []string   // pattern 里声明的参数名（注册时校验用）
	bind       func(ViewerResolver) http.HandlerFunc
}

// LimitDecl 是限流的声明。执行（rate_counters、429）在限流轮；写接口注册时
// 必须声明 Limit 或 NoLimit，数字最终集中到 limits.go 对照设计附录 C（5.9）。
type LimitDecl struct {
	Kind   LimitKind
	N      int
	Window time.Duration
}

// LimitKind 是限流按谁数：按人还是按访客 IP。
type LimitKind string

// 两种限流粒度（5.3 的 api.Limit(ratelimit.PerUser, …)）。
const (
	PerUser LimitKind = "per_user"
	PerIP   LimitKind = "per_ip"
)

// RouteOption 是注册接口时的可选项。
type RouteOption func(*Route)

// Budget 声明这个接口最多跑几条查询（查询预算，3 份和 10 份数据都不得超）。
func Budget(n int) RouteOption { return func(r *Route) { r.Budget = n } }

// Limit 声明限流。写接口必须声明它或 NoLimit，否则注册时 panic。
func Limit(kind LimitKind, n int, window time.Duration) RouteOption {
	return func(r *Route) { r.Limit = &LimitDecl{Kind: kind, N: n, Window: window} }
}

// NoLimit 声明这个写接口为什么不限流（比如幂等的内部动作）。
func NoLimit(reason string) RouteOption { return func(r *Route) { r.NoLimitStr = reason } }

// Nav 声明后台位置（大类、标签），M8 的后台导航和守门用。
func Nav(section, tab string) RouteOption { return func(r *Route) { r.Nav = section + "/" + tab } }

// Routes 返回全部路由，守卫测试用。
func (g *Registry) Routes() []*Route { return g.routes }

// Get 注册一个 GET 接口（只读；GET 不写业务数据，5.4）。
func Get[In, Out any](g *Registry, pattern string, gate Gate,
	h func(*app.Ctx, In) (Out, error), opts ...RouteOption,
) {
	handle[In, Out](g, http.MethodGet, pattern, gate, h, opts...)
}

// Post 注册一个 POST 接口（写；必须声明限流）。
func Post[In, Out any](g *Registry, pattern string, gate Gate,
	h func(*app.Ctx, In) (Out, error), opts ...RouteOption,
) {
	handle[In, Out](g, http.MethodPost, pattern, gate, h, opts...)
}

// Patch 注册一个 PATCH 接口（写字段，自动保存协议 v2 用，5.5）。
func Patch[In, Out any](g *Registry, pattern string, gate Gate,
	h func(*app.Ctx, In) (Out, error), opts ...RouteOption,
) {
	handle[In, Out](g, http.MethodPatch, pattern, gate, h, opts...)
}

// Delete 注册一个 DELETE 接口（写；必须声明限流）。
func Delete[In, Out any](g *Registry, pattern string, gate Gate,
	h func(*app.Ctx, In) (Out, error), opts ...RouteOption,
) {
	handle[In, Out](g, http.MethodDelete, pattern, gate, h, opts...)
}

func handle[In, Out any](g *Registry, method, pattern string, gate Gate,
	h func(*app.Ctx, In) (Out, error), opts ...RouteOption,
) {
	if gate == nil {
		panic("接口没声明门：" + method + " " + pattern)
	}
	rt := &Route{Method: method, Pattern: pattern, Gate: gate}
	rt.PathParams = pathParamsOf(pattern)
	validateIn[In](rt)
	for _, opt := range opts {
		opt(rt)
	}
	if method != http.MethodGet && rt.Limit == nil && rt.NoLimitStr == "" {
		panic("写接口没声明限流（api.Limit 或 api.NoLimit）：" + method + " " + pattern)
	}
	rt.bind = func(resolve ViewerResolver) http.HandlerFunc {
		return func(w http.ResponseWriter, req *http.Request) {
			viewer := resolve(req)
			ctx := &app.Ctx{
				Context:   req.Context(),
				Viewer:    viewer,
				Clock:     clock.System{},
				RequestID: newRequestID(),
			}
			if err := gate.check(viewer); err != nil {
				writeError(w, err)
				return
			}
			var in In
			if err := bindRequest(w, req, rt, &in); err != nil {
				writeError(w, asAPIError(err))
				return
			}
			out, err := h(ctx, in)
			if err != nil {
				writeError(w, asAPIError(err))
				return
			}
			writeJSON(w, out)
		}
	}
	g.routes = append(g.routes, rt)
}

// Handler 生成最终的路由：标准库 ServeMux（方法 + 路径参数），外面套
// CrossOriginProtection 拒跨站写（无 Origin 无 Sec-Fetch-Site 的非浏览器
// 请求放行——微信内置浏览器的情形，13 号文档风险表）。
func (g *Registry) Handler(resolve ViewerResolver) http.Handler {
	mux := http.NewServeMux()
	for _, rt := range g.routes {
		rt.mount(mux, resolve)
	}
	return http.NewCrossOriginProtection().Handler(mux)
}

func (rt *Route) mount(mux *http.ServeMux, resolve ViewerResolver) {
	mux.HandleFunc(rt.Method+" "+rt.Pattern, rt.bind(resolve))
}

// asAPIError：服务层返回的 error 是 *Error 就用；不是的按 500 记日志再包一层
// 固定文案（不把内部错误漏给客户端）。
func asAPIError(err error) *Error {
	var e *Error
	if errors.As(err, &e) {
		return e
	}
	slog.Error("接口内部错误", "err", err.Error())
	return NewErr(http.StatusInternalServerError, "internal", "服务器开小差了，稍后再试")
}

func writeJSON(w http.ResponseWriter, out any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(out)
}

func newRequestID() string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "x"
	}
	return hex.EncodeToString(b[:])
}

// pathParamsOf 抽出 pattern 里的 {参数} 名字。
func pathParamsOf(pattern string) []string {
	var names []string
	rest := pattern
	for {
		i := indexOf(rest, '{')
		if i < 0 {
			return names
		}
		j := indexOf(rest[i:], '}')
		if j < 0 {
			return names
		}
		names = append(names, rest[i+1:i+j])
		rest = rest[i+j+1:]
	}
}

func indexOf(s string, c byte) int {
	for i := 0; i < len(s); i++ {
		if s[i] == c {
			return i
		}
	}
	return -1
}

// validateIn 在注册时把 In 类型的毛病挑出来（panic），别等运行时才发现：
// path 标签的参数必须在 pattern 里；GET 的 In 不许有 json 字段。
func validateIn[In any](rt *Route) {
	t := reflect.TypeOf(*new(In))
	if t.Kind() != reflect.Struct {
		panic("In 必须是结构体：" + rt.Method + " " + rt.Pattern)
	}
	for i := range t.NumField() {
		f := t.Field(i)
		if p, ok := f.Tag.Lookup("path"); ok {
			if f.Type != reflect.TypeOf(ID(0)) {
				panic("path 字段的类型必须是 api.ID：" + rt.Method + " " + rt.Pattern + " 字段 " + f.Name)
			}
			if !contains(rt.PathParams, p) {
				panic("path 标签的参数不在地址里：" + rt.Method + " " + rt.Pattern + " 字段 " + f.Name)
			}
		} else if _, hasJSON := f.Tag.Lookup("json"); hasJSON {
			if rt.Method == http.MethodGet {
				panic("GET 的 In 不许有 json 字段（GET 不收请求体）：" + rt.Pattern + " 字段 " + f.Name)
			}
		}
	}
}

func contains(list []string, s string) bool {
	for _, item := range list {
		if item == s {
			return true
		}
	}
	return false
}
