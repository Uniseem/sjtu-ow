package jobs

import "time"

const (
	SchedPublish  = "publish"  // 每 30 秒：定时上线、到期撤下
	SchedPatrol   = "patrol"   // 每 30 秒：AI 巡查是否到点
	SchedBackup   = "backup"   // 每天 03:00
	SchedCleanup  = "cleanup"  // 每天 04:00
	SchedOptimize = "optimize" // 每周日 04:30
	SchedAssets   = "assets"   // 每天 04:40
)

// shanghai 没有夏令时，固定东八区，不依赖机器上有没有 zoneinfo。
var shanghai = time.FixedZone("Asia/Shanghai", 8*3600)

// Due 报告 name 在 now 这一刻该不该跑。last 是上次跑的时间，零值表示从没跑过。
// 错过了只补最近的那一次，不把中间每一次都补上。
func Due(name string, now, last time.Time) bool {
	if now.IsZero() {
		return false
	}
	switch name {
	case SchedPublish, SchedPatrol:
		return last.IsZero() || now.Sub(last) >= 30*time.Second
	case SchedBackup:
		return missed(now, last, dailySlot(now, 3, 0))
	case SchedCleanup:
		return missed(now, last, dailySlot(now, 4, 0))
	case SchedAssets:
		return missed(now, last, dailySlot(now, 4, 40))
	case SchedOptimize:
		return missed(now, last, weeklySlot(now, time.Sunday, 4, 30))
	default:
		return false
	}
}

func missed(now, last, slot time.Time) bool {
	if now.Before(slot) {
		return false
	}
	return last.Before(slot)
}

func dailySlot(now time.Time, hour, minute int) time.Time {
	loc := now.In(shanghai)
	slot := time.Date(loc.Year(), loc.Month(), loc.Day(), hour, minute, 0, 0, shanghai)
	if loc.Before(slot) {
		slot = slot.AddDate(0, 0, -1)
	}
	return slot
}

func weeklySlot(now time.Time, weekday time.Weekday, hour, minute int) time.Time {
	slot := dailySlot(now, hour, minute)
	for slot.Weekday() != weekday {
		slot = slot.AddDate(0, 0, -1)
	}
	// dailySlot 已经落在 now 之前（或正好）。再往回拨到周日时，仍应不晚于 now。
	if now.Before(slot) {
		slot = slot.AddDate(0, 0, -7)
	}
	return slot
}
