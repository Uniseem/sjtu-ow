// Package api 是新栈的接口注册表（12 号文档 5.3/5.4）：所有 HTTP 接口从这里
// 注册，声明门、限流、查询预算；由注册表生成路由、绑定参数、渲染统一错误，
// 守卫测试（守门矩阵、乱填、跨站写）也吃它的路由清单。
package api

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"reflect"
	"strconv"

	"github.com/Uniseem/sjtu-ow/server/internal/app"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/auth"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/idempotency"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/outbox"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit"
)

// ViewerResolver 从请求解出「这是谁」。会话中间件（后续轮次）从 ow_session
// Cookie 解出真正的 Viewer，解析不出返回 nil；测试自己注入。
type ViewerResolver func(*http.Request) *app.Viewer

// Registry 收集路由。零值可用；一个进程一个。
type Registry struct {
	routes []*Route
	raws   []*rawRoute
}

// rawRoute 是不走 JSON 的接口（日历订阅的 .ics、邮件客户端的一键退订）。
// 它们不在 Routes() 里：没有门、没有 TS 类型，只有限流。
type rawRoute struct {
	method, pattern string
	limits          []ratelimit.Decl
	h               http.HandlerFunc
}

// Raw 注册一个非 JSON 的接口。限流照样数（规则 216），其余自己负责。
func Raw(g *Registry, method, pattern string, limits []ratelimit.Decl, h http.HandlerFunc) {
	g.raws = append(g.raws, &rawRoute{method: method, pattern: pattern, limits: limits, h: h})
}

// Route 是一条注册了的接口。守卫测试遍历它做矩阵和乱填。
type Route struct {
	Method     string
	Pattern    string
	Gate       Gate
	Budget     int              // 查询数上限（查询预算测试用，5.3）
	Limits     []ratelimit.Decl // 限流声明；写接口必须有（或写 NoLimitStr）
	NoLimitStr string           // NoLimit 的理由
	Nav        string           // 后台位置「大类/标签」（M8 用）
	PathParams []string         // pattern 里声明的参数名（注册时校验用）
	InType     reflect.Type     // 请求类型，apigen 用来生成 TS
	OutType    reflect.Type     // 响应类型，apigen 用来生成 TS

	bind func(handlerCfg) http.HandlerFunc
}

// handlerCfg 是 Handler 装配进每条路由的依赖。
type handlerCfg struct {
	resolve       ViewerResolver
	limiter       ratelimit.Limiter  // nil 表示这条链不限流（纯单元测试用）
	idem          *idempotency.Store // nil 表示不管幂等键
	trusted       []*net.IPNet       // 可信代理网段，取访客 IP 用
	secureCookies bool               // 会话 Cookie 是否带 Secure（生产为真）
	db            *db.DB             // 待发信的系统代发用（规则 208）；nil 就不代发
	siteURL       string
}

// RouteOption 是注册接口时的可选项。
type RouteOption func(*Route)

// Budget 声明这个接口最多跑几条查询（查询预算，3 份和 10 份数据都不得超）。
func Budget(n int) RouteOption { return func(r *Route) { r.Budget = n } }

// Limit 声明限流（可以几条一起，比如评论的每分钟和每天）。数字一律来自
// ratelimit/limits.go 的表，不许内联——「一张表」靠这个保证。
func Limit(decls ...ratelimit.Decl) RouteOption {
	return func(r *Route) { r.Limits = append(r.Limits, decls...) }
}

// NoLimit 声明这个写接口为什么不限流（比如幂等的内部动作）。
func NoLimit(reason string) RouteOption { return func(r *Route) { r.NoLimitStr = reason } }

// Nav 声明后台位置（大类、标签），M8 的后台导航和守门用。
func Nav(section, tab string) RouteOption { return func(r *Route) { r.Nav = section + "/" + tab } }

// HandlerOption 配置 Handler。
type HandlerOption func(*handlerCfg)

// WithLimiter 接上限流执行（真实现是 ratelimit.NewEnforcer）。
func WithLimiter(l ratelimit.Limiter) HandlerOption {
	return func(c *handlerCfg) { c.limiter = l }
}

// WithIdempotency 接上幂等键存储。
func WithIdempotency(s *idempotency.Store) HandlerOption {
	return func(c *handlerCfg) { c.idem = s }
}

// WithTrustedProxies 声明可信代理网段（config.TrustedProxies），按它取访客 IP。
func WithTrustedProxies(nets []*net.IPNet) HandlerOption {
	return func(c *handlerCfg) { c.trusted = nets }
}

// WithLetters 接上待发信的代发：做事的人在这次请求里把账号注销了（会话被清掉），
// 这批信没人可问，由系统照发（规则 208）。
func WithLetters(d *db.DB, siteURL string) HandlerOption {
	return func(c *handlerCfg) { c.db = d; c.siteURL = siteURL }
}

// WithSecureCookies 声明会话 Cookie 要不要带 Secure（生产为真；开发走 http，
// 带 Secure 浏览器不会把 Cookie 送回来）。
func WithSecureCookies(on bool) HandlerOption {
	return func(c *handlerCfg) { c.secureCookies = on }
}

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

// Put 注册一个 PUT 接口（写；必须声明限流）。
func Put[In, Out any](g *Registry, pattern string, gate Gate,
	h func(*app.Ctx, In) (Out, error), opts ...RouteOption,
) {
	handle[In, Out](g, http.MethodPut, pattern, gate, h, opts...)
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
	rt := &Route{
		Method: method, Pattern: pattern, Gate: gate,
		InType: reflect.TypeOf(*new(In)), OutType: reflect.TypeOf(*new(Out)),
	}
	rt.PathParams = pathParamsOf(pattern)
	validateIn[In](rt)
	for _, opt := range opts {
		opt(rt)
	}
	if method != http.MethodGet && len(rt.Limits) == 0 && rt.NoLimitStr == "" {
		panic("写接口没声明限流（api.Limit 或 api.NoLimit）：" + method + " " + pattern)
	}
	rt.bind = func(cfg handlerCfg) http.HandlerFunc {
		return func(w http.ResponseWriter, req *http.Request) {
			viewer := cfg.resolve(req)
			ctx := &app.Ctx{
				Context:      req.Context(),
				Viewer:       viewer,
				Clock:        clock.System{},
				RequestID:    newRequestID(),
				SessionToken: auth.TokenFromRequest(req),
			}
			if err := gate.check(viewer); err != nil {
				writeError(w, err)
				return
			}
			// 登录的人做写动作，动作带出来的信先冻住等他点头（规则 206）。
			if method != http.MethodGet && viewer != nil && viewer.ID > 0 && !viewer.Disabled {
				ctx.Letters = outbox.Open(viewer.ID)
			}

			// 限流：声明的每条都数一遍，最先超的那条决定答复（429 + Retry-After）。
			if cfg.limiter != nil {
				var userID int64
				if viewer != nil {
					userID = viewer.ID
				}
				for _, d := range rt.Limits {
					key := ratelimit.ClientKey(req, cfg.trusted, userID, d.Kind)
					retry, ok, err := cfg.limiter.Allow(ctx.Context, key, d)
					if err != nil {
						writeError(w, asAPIError(err))
						return
					}
					if !ok {
						writeError(w, TooManyRequests(retry))
						return
					}
				}
			}

			// 幂等键（只对登录用户的写请求生效）：先认领，重放直接回回执。
			claimed := false
			var idemKey string
			if cfg.idem != nil && rt.Method != http.MethodGet && viewer != nil {
				if idemKey = req.Header.Get("Idempotency-Key"); idemKey != "" {
					outcome, receipt, err := cfg.idem.Claim(ctx.Context, viewer.ID, idemKey, rt.Method, req.URL.Path)
					if err != nil {
						writeError(w, asAPIError(err))
						return
					}
					switch outcome {
					case idempotency.Replay:
						w.Header().Set("Content-Type", "application/json")
						w.WriteHeader(receipt.Status)
						_, _ = w.Write(receipt.Body)
						return
					case idempotency.Busy:
						writeError(w, NewErr(http.StatusConflict, "duplicate", "同样的请求还在处理，等它一下"))
						return
					case idempotency.Mismatch:
						writeError(w, Invalid("这个幂等键用过别的地址"))
						return
					}
					claimed = true
				}
			}

			var in In
			if err := bindRequest(w, req, rt, &in); err != nil {
				releaseIdempotency(cfg, ctx, viewer, claimed, idemKey)
				writeError(w, asAPIError(err))
				return
			}
			out, err := h(ctx, in)
			if err != nil {
				releaseIdempotency(cfg, ctx, viewer, claimed, idemKey)
				writeError(w, asAPIError(err))
				return
			}
			body, err := json.Marshal(out)
			if err != nil {
				releaseIdempotency(cfg, ctx, viewer, claimed, idemKey)
				writeError(w, asAPIError(err))
				return
			}
			if ctx.Letters != nil && ctx.Letters.Held > 0 {
				body = settleLetters(cfg, ctx, body)
			}
			if claimed {
				if err := cfg.idem.Complete(ctx.Context, viewer.ID, idemKey, http.StatusOK, body); err != nil {
					slog.Error("幂等回执没存上", "err", err.Error())
				}
			}
			if ctx.ShouldClearSessionCookie() {
				auth.ClearCookie(w, cfg.secureCookies)
			}
			// 登录这类动作发的会话 Cookie（成功路径才有；令牌只进 HttpOnly 头）
			for _, tok := range ctx.DrainSessionCookies() {
				auth.SetCookie(w, tok, cfg.secureCookies)
			}
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write(body)
		}
	}
	g.routes = append(g.routes, rt)
}

// Handler 生成最终的路由：标准库 ServeMux（方法 + 路径参数），外面套
// CrossOriginProtection 拒跨站写（无 Origin 无 Sec-Fetch-Site 的非浏览器
// 请求放行——微信内置浏览器的情形，13 号文档风险表）。
func (g *Registry) Handler(resolve ViewerResolver, opts ...HandlerOption) http.Handler {
	cfg := handlerCfg{resolve: resolve}
	for _, opt := range opts {
		opt(&cfg)
	}
	mux := http.NewServeMux()
	for _, rt := range g.routes {
		mux.HandleFunc(rt.Method+" "+rt.Pattern, rt.bind(cfg))
	}
	for _, rr := range g.raws {
		mux.HandleFunc(rr.method+" "+rr.pattern, rr.serve(cfg))
	}
	return http.NewCrossOriginProtection().Handler(mux)
}

// releaseIdempotency：处理出错的请求把认领放掉，让同一个键的重试还能进行。
func releaseIdempotency(cfg handlerCfg, ctx *app.Ctx, viewer *app.Viewer, claimed bool, key string) {
	if !claimed {
		return
	}
	if err := cfg.idem.Release(ctx.Context, viewer.ID, key); err != nil {
		slog.Error("幂等认领没释放掉", "err", err.Error())
	}
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
			if f.Type != reflect.TypeOf(ID(0)) && f.Type.Kind() != reflect.String {
				panic("path 字段的类型必须是 api.ID 或 string：" + rt.Method + " " + rt.Pattern + " 字段 " + f.Name)
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

// serve 给非 JSON 接口套上限流：最先超的那条答 429 + Retry-After。
func (rr *rawRoute) serve(cfg handlerCfg) http.HandlerFunc {
	return func(w http.ResponseWriter, req *http.Request) {
		if cfg.limiter != nil {
			for _, d := range rr.limits {
				key := ratelimit.ClientKey(req, cfg.trusted, 0, d.Kind)
				retry, ok, err := cfg.limiter.Allow(req.Context(), key, d)
				if err != nil {
					slog.Error("限流出错", "err", err.Error())
					http.Error(w, "服务器开小差了，稍后再试", http.StatusInternalServerError)
					return
				}
				if !ok {
					secs := int(retry.Seconds())
					if secs < 1 {
						secs = 1
					}
					w.Header().Set("Retry-After", strconv.Itoa(secs))
					http.Error(w, "请求太频繁，稍后再试", http.StatusTooManyRequests)
					return
				}
			}
		}
		rr.h(w, req)
	}
}

// settleLetters 在答复里加上 letters 一项，前端据此跳到「发信」页（规则 207）。
// 做事的人在这次请求里注销了账号（会话被清）就没人可问，由系统代发（规则 208）。
// 答复不是 JSON 对象就原样放过（没有地方放；现在的接口都返回对象）。
func settleLetters(cfg handlerCfg, ctx *app.Ctx, body []byte) []byte {
	batch := ctx.Letters
	if ctx.ShouldClearSessionCookie() {
		if cfg.db == nil {
			return body
		}
		err := cfg.db.WriteTx(ctx.Context, func(txCtx context.Context, tx *db.Tx) error {
			_, _, err := outbox.SendAll(txCtx, tx, batch.Key, cfg.siteURL, ctx.Now())
			return err
		})
		if err != nil {
			slog.Error("待发信没有代发出去", "err", err.Error())
		}
		return body
	}
	var obj map[string]json.RawMessage
	if err := json.Unmarshal(body, &obj); err != nil || obj == nil {
		return body
	}
	info, _ := json.Marshal(map[string]any{"batch": batch.Key, "count": batch.Held})
	obj["letters"] = info
	merged, err := json.Marshal(obj)
	if err != nil {
		return body
	}
	return merged
}
