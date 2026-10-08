// Package clock 提供可注入的时钟：业务代码不直接调 time.Now，测试里换成一个
// 固定的时钟就能冻结时间（12 号文档 5.1 的 platform/clock）。
package clock

import "time"

// Clock 是全站取「现在」的唯一口径。
type Clock interface {
	Now() time.Time
}

// System 是生产用的真时钟。
type System struct{}

func (System) Now() time.Time { return time.Now() }

// Fixed 永远返回同一个时间；测试里要推进时间就换一个新的 Fixed。
type Fixed time.Time

func (f Fixed) Now() time.Time { return time.Time(f) }
