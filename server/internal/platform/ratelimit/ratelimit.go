// Package ratelimit 是限流的执行（12 号文档 5.9）：原子计数、时间片桶、
// 按可信代理取访客 IP。数字集中在 limits.go 一张表，和设计附录 C 对照。
package ratelimit

import (
	"context"
	"database/sql"
	"errors"
	"net"
	"net/http"
	"strconv"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
	"github.com/Uniseem/sjtu-ow/server/internal/platform/db"
)

// Kind 按谁数：按登录的人还是按访客 IP。
type Kind string

// 三种粒度（12 号文档 5.3）。PerKey 的 key 由服务层自己拼好传进来
// （比如登录失败按 "email:"+规范化邮箱 数）；注册表层算不出这种 key，
// ClientKey 对它按 IP 兜底——声明了 PerKey 的接口别忘了在服务层计数。
const (
	PerUser Kind = "per_user"
	PerIP   Kind = "per_ip"
	PerKey  Kind = "per_key"
)

// Decl 是一条限流的声明。数字一律来自 limits.go 的表，不许在注册处内联。
type Decl struct {
	Name   string // 表里的名字（也用作计数桶前缀）
	Kind   Kind
	N      int
	Window time.Duration
}

// Limiter 被注册表调用；*Enforcer 是真实现，测试可以换成假的。
type Limiter interface {
	// Allow 数一次。ok=false 时返回的 retryAfter 是到下一个时间片的时长。
	Allow(ctx context.Context, key string, d Decl) (retryAfter time.Duration, ok bool, err error)
}

// Enforcer 用数据库原子计数执行限流。
type Enforcer struct {
	db    *db.DB
	clock clock.Clock
}

// NewEnforcer 造一个执行器；clock 注入让测试冻结时间。
func NewEnforcer(d *db.DB, c clock.Clock) *Enforcer {
	if c == nil {
		c = clock.System{}
	}
	return &Enforcer{db: d, clock: c}
}

// Allow 数一次并判断放不放行。
func (e *Enforcer) Allow(ctx context.Context, key string, d Decl) (time.Duration, bool, error) {
	now := e.clock.Now().UTC()
	bucket := d.Name + "|" + sliceOf(now, d.Window)
	var count int64
	err := e.db.WriteTx(ctx, func(ctx context.Context, tx *db.Tx) error {
		row := tx.QueryRowContext(ctx, `INSERT INTO rate_counters (key, bucket, count)
			VALUES (?, ?, 1)
			ON CONFLICT (key, bucket) DO UPDATE SET count = count + 1
			RETURNING count`, key, bucket)
		return row.Scan(&count)
	})
	if err != nil {
		return 0, false, err
	}
	if count > int64(d.N) {
		return untilNextSlice(now, d.Window), false, nil
	}
	return 0, true, nil
}

// Count 只读当前时间片的计数（不数），顺带返回到下一片还有多久。给「先查后数」
// 的失败锁用（登录按账号，R006）：进入时先看是不是已经锁了，密码错了才数一次——
// 不然爆破者可以一直试到撞对的那一次。
func (e *Enforcer) Count(ctx context.Context, key string, d Decl) (count int64, retryAfter time.Duration, err error) {
	now := e.clock.Now().UTC()
	bucket := d.Name + "|" + sliceOf(now, d.Window)
	err = e.db.ReadPool().QueryRowContext(ctx,
		`SELECT count FROM rate_counters WHERE key = ? AND bucket = ?`, key, bucket).Scan(&count)
	if errors.Is(err, sql.ErrNoRows) {
		return 0, untilNextSlice(now, d.Window), nil
	}
	if err != nil {
		return 0, 0, err
	}
	return count, untilNextSlice(now, d.Window), nil
}

// sliceOf 取时间片（UTC，固定窗口，不是滑动窗口）。
// 表里实际就三种窗口：≤1 分钟按分钟、不满 24 小时按小时、≥24 小时按天。
// 「≤1 小时按分钟」会把「每小时 5 次」算成每分钟 5 次，所以小时级走小时片。
func sliceOf(t time.Time, window time.Duration) string {
	switch {
	case window <= time.Minute:
		return t.Format("20060102T1504")
	case window < 24*time.Hour:
		return t.Format("20060102T15")
	default:
		return t.Format("20060102")
	}
}

func untilNextSlice(t time.Time, window time.Duration) time.Duration {
	var next time.Time
	switch {
	case window <= time.Minute:
		next = t.Truncate(time.Minute).Add(time.Minute)
	case window < 24*time.Hour:
		next = t.Truncate(time.Hour).Add(time.Hour)
	default:
		next = t.Truncate(24 * time.Hour).Add(24 * time.Hour)
	}
	d := next.Sub(t)
	if d <= 0 {
		return time.Second
	}
	return d
}

// ClientKey 算限流的键：按人用编号；按 IP 用访客地址（IPv6 折叠 /64）。
// 没登录的人走 per_user 也会落到按 IP（登录、验证码这类匿名接口就是如此）。
func ClientKey(r *http.Request, trusted []*net.IPNet, userID int64, kind Kind) string {
	if kind == PerUser && userID > 0 {
		return "u:" + strconv.FormatInt(userID, 10)
	}
	return "ip:" + normalizeIP(clientIP(r, trusted))
}

// clientIP 只信可信代理带来的 X-Real-IP：直连或不可信来源的一律用 RemoteAddr，
// 不然谁都能伪造别人的计数（5.9）。
func clientIP(r *http.Request, trusted []*net.IPNet) net.IP {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		host = r.RemoteAddr
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return nil
	}
	if inAny(trusted, ip) {
		if real := net.ParseIP(r.Header.Get("X-Real-IP")); real != nil {
			return real
		}
	}
	return ip
}

func inAny(nets []*net.IPNet, ip net.IP) bool {
	for _, n := range nets {
		if n.Contains(ip) {
			return true
		}
	}
	return false
}

// normalizeIP 把 IPv6 折叠成 /64：同一前缀里的地址共用一个计数（5.9），
// 不然家宽重拨一次就绕过按 IP 的限流。
func normalizeIP(ip net.IP) string {
	if ip == nil {
		return "unknown"
	}
	if v4 := ip.To4(); v4 != nil {
		return v4.String()
	}
	v6 := ip.To16()
	if v6 == nil {
		return "unknown"
	}
	// 折叠 /64：后 64 位清零，同一前缀共用一个计数（5.9）。
	masked := make(net.IP, net.IPv6len)
	copy(masked, v6[:8])
	return masked.String()
}
