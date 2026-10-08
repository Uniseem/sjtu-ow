package api

import (
	"github.com/Uniseem/sjtu-ow/server/internal/app"
)

// Gate 是接口的门（12 号文档 5.3）。它是第一道：注册表在调处理函数之前查；
// 服务函数里对「这条记录是不是你的」「这个状态能不能做」再判一次（5.2）。
// Token 门（签名地址：日历、退订）等 djsign 轮次加。
type Gate interface {
	// check 返回 nil 放行；返回 *Error 用它的状态码和文案拒绝。
	check(v *app.Viewer) *Error
}

type publicGate struct{}

// Public：谁都能访问。
var Public Gate = publicGate{}

func (publicGate) check(*app.Viewer) *Error { return nil }

type memberGate struct{}

// Member：登录且启用。没登录（含停用、解析不出身份）一律 401，前端跳登录。
var Member Gate = memberGate{}

func (memberGate) check(v *app.Viewer) *Error {
	if v == nil || v.Disabled || v.ID <= 0 {
		return Unauthorized("要先登录")
	}
	return nil
}

type verifiedGate struct{}

// Verified：Member 且邮箱已验证（报名、投稿这类门槛）。
var Verified Gate = verifiedGate{}

func (verifiedGate) check(v *app.Viewer) *Error {
	if err := Member.check(v); err != nil {
		return err
	}
	// 超管的邮箱视为已验证（现行站 createsuperuser 直接算已验证，184 起）
	if !v.EmailVerified && !v.Superuser {
		return Forbidden()
	}
	return nil
}

type featureGate struct{ f app.Feature }

// Feature：登录且 can_use(f)（规则 11 的判定在 app.Viewer.CanUse）。
func Feature(f app.Feature) Gate { return featureGate{f: f} }

func (g featureGate) check(v *app.Viewer) *Error {
	if err := Member.check(v); err != nil {
		return err
	}
	if !v.CanUse(g.f) {
		return Forbidden()
	}
	return nil
}

type capGate struct{ caps []app.Cap }

// Cap：登录且拥有列出的每一项后台能力。
func Cap(c ...app.Cap) Gate { return capGate{caps: c} }

func (g capGate) check(v *app.Viewer) *Error {
	if err := Member.check(v); err != nil {
		return err
	}
	for _, c := range g.caps {
		if !v.HasCap(c) {
			return Forbidden()
		}
	}
	return nil
}

type superuserGate struct{}

// Superuser：超级管理员。
var Superuser Gate = superuserGate{}

func (superuserGate) check(v *app.Viewer) *Error {
	if err := Member.check(v); err != nil {
		return err
	}
	if !v.Superuser {
		return Forbidden()
	}
	return nil
}
