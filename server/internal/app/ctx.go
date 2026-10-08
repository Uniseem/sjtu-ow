// Package app 放服务层函数的第一个参数（12 号文档 5.2）：Ctx 携带当前用户、
// 时钟、请求编号；后续里程碑会往上面加待发信批次（outbox）和任务入队（jobs）。
// 后台、前台、worker、导入器调的是同一个服务函数，所以这些东西挂在 Ctx 上。
package app

import (
	"context"
	"time"

	"github.com/Uniseem/sjtu-ow/server/internal/platform/clock"
)

// Cap 是后台能力（12 号文档 5.8 的枚举；「角色 → 能力」的对照表 M3 随账号域做）。
type Cap string

// Feature 是功能权限的名字（can_use 的那个 feature，规则 11）。
type Feature string

// Viewer 是「这次请求是谁」的最小口径。M1 里由注册表的 ViewerResolver 注入
// （测试自己造）；会话中间件（后续轮次）从 ow_session 解出来填。nil 是访客。
type Viewer struct {
	ID            int64
	Disabled      bool // 停用：所有需要身份的门都当没登录拒
	EmailVerified bool
	Superuser     bool
	Caps          map[Cap]struct{}
	// FeatureDenied 是单人功能限制（「谁被禁了哪项」）。can_use 的完整判定
	// 顺序（角色级限制、派生角色）M3 随 5.8 一起进，这里是它的子集。
	FeatureDenied map[Feature]struct{}
}

// HasCap 报这个人有没有某项后台能力；超管直接全有。
func (v *Viewer) HasCap(c Cap) bool {
	if v == nil || v.Disabled {
		return false
	}
	if v.Superuser {
		return true
	}
	_, ok := v.Caps[c]
	return ok
}

// CanUse 判定顺序照规则 11 的子集：未登录 / 停用 → 拒；单人规则 → 拒；默认允许。
// 超管也受单人限制吗？不受——现行站超管绕过 can_use（设计 4.2），照旧。
func (v *Viewer) CanUse(f Feature) bool {
	if v == nil || v.Disabled {
		return false
	}
	if v.Superuser {
		return true
	}
	if v.FeatureDenied != nil {
		if _, denied := v.FeatureDenied[f]; denied {
			return false
		}
	}
	return true
}

// Ctx 是服务函数的第一个参数。
type Ctx struct {
	Context context.Context
	Viewer  *Viewer
	Clock   clock.Clock
	// RequestID 由服务器生成（5.15：api 只信可信代理传来的编号，那套接线
	// 在 serve 真正起来的轮次做，现在一律自己生成）。
	RequestID string
	// Letters 是这一次写请求冻住的待发信批次（5.11）。nil 表示没人在场
	// （worker、命令），信直接入队。
	Letters *LetterBatch

	// sessionCookies 是处理函数里要发的会话令牌（登录、验证码核验通过）。
	// 注册表在答复前用 auth.SetCookie 写进响应头；令牌不进 JSON。
	sessionCookies []string
}

// SetSessionCookie 登录这类动作成功后发会话 Cookie（12 号文档 5.7）。
// 多次调用就发多个（正常流程最多一个）。
func (c *Ctx) SetSessionCookie(token string) {
	c.sessionCookies = append(c.sessionCookies, token)
}

// DrainSessionCookies 取走积攒的会话令牌（注册表写响应头用，之后清空）。
func (c *Ctx) DrainSessionCookies() []string {
	toks := c.sessionCookies
	c.sessionCookies = nil
	return toks
}

// LetterBatch 是同一次操作写下的待发信（设计 10.5）。Key 是这批的编号。
type LetterBatch struct {
	Key     string
	ActorID int64
	Held    int
}

// Now 是全站取「现在」的口径，测试里把 Clock 换成 clock.Fixed 冻结时间。
func (c *Ctx) Now() time.Time {
	if c.Clock == nil {
		return time.Now()
	}
	return c.Clock.Now()
}
