// Sample data for /_styleguide/ (design 13.2.7). Same labels and made-up
// rows as core/styleguide.py. No database.
import type { SampleClock } from "./router"
import { owDate, owDay, owMd, owMonthNum, owTime, owWeekday, shanghaiEvening } from "./time"

export const COLOURS: [string, string, string, string][] = [
  ["页面", "bg", "bg-bg", "#F5F6F8"],
  ["卡片、页头", "surface", "bg-surface", "#FFFFFF"],
  ["表头、占位、日期块", "surface-2", "bg-surface-2", "#EEF0F3"],
  ["描边、分隔线", "line", "bg-line", "#E1E4E8"],
  ["控件边框", "control", "bg-control", "#767D88"],
  ["正文", "fg", "bg-fg", "#111318"],
  ["次要文字", "fg-2", "bg-fg-2", "#4A505B"],
  ["日期、署名", "fg-3", "bg-fg-3", "#5F6671"],
  ["砖红", "primary", "bg-primary", "#9B3A33"],
  ["砖红悬停", "primary-hover", "bg-primary-hover", "#80302A"],
  ["红色文字", "primary-text", "bg-primary-text", "#963830"],
  ["红色标签底", "primary-soft", "bg-primary-soft", "#F1E0DA"],
  ["红色标签字", "on-primary-soft", "bg-on-primary-soft", "#73291F"],
  ["通过", "ok", "bg-ok", "#3B6D4F"],
  ["通过底", "ok-soft", "bg-ok-soft", "#DFE9E0"],
  ["沙杏（守望先锋橙收淡）", "accent", "bg-accent", "#CF9152"],
  ["橙色小字", "accent-text", "bg-accent-text", "#8D5219"],
  ["橙色大字", "accent-display", "bg-accent-display", "#A86C30"],
  ["橙色标签底", "accent-soft", "bg-accent-soft", "#F3E3CD"],
  ["橙色标签字", "on-accent-soft", "bg-on-accent-soft", "#6B3D12"],
  ["提醒", "warn", "bg-warn", "#685513"],
  ["提醒底", "warn-soft", "bg-warn-soft", "#EFE7C7"],
  ["信息", "info", "bg-info", "#3A5F82"],
  ["信息底", "info-soft", "bg-info-soft", "#E0E8EF"],
  ["操作提示底", "toast", "bg-toast", "#1C1F25"],
  ["操作提示字", "on-toast", "bg-on-toast", "#F2F3F5"],
  ["深色条底", "night", "bg-night", "#141A24"],
  ["图片卡深底", "night-2", "bg-night-2", "#222A37"],
  ["深色条里的深红", "night-accent", "bg-night-accent", "#A8463D"],
  ["深色条卡片", "night-surface", "bg-night-surface", "#1A2130"],
  ["深色条分隔线", "night-line", "bg-night-line", "#2D3646"],
  ["深色条控件边框", "night-control", "bg-night-control", "#6E7889"],
  ["深色条正文", "night-fg", "bg-night-fg", "#E8EAEE"],
  ["深色条次要文字", "night-fg-2", "bg-night-fg-2", "#B6BCC7"],
  ["深色条日期", "night-fg-3", "bg-night-fg-3", "#959CAB"],
  ["深色条红字", "night-primary-text", "bg-night-primary-text", "#EE9A90"],
  ["深色条红标签底", "night-primary-soft", "bg-night-primary-soft", "#3A2226"],
  ["深色条红标签字", "night-on-primary-soft", "bg-night-on-primary-soft", "#F5C3BC"],
  ["深色条橙标签底", "night-accent-soft", "bg-night-accent-soft", "#3A2D1C"],
  ["深色条橙标签字", "night-on-accent-soft", "bg-night-on-accent-soft", "#F0CB98"],
]

export const STATUSES: [string, string][] = [
  ["live", "报名中"],
  ["ok", "已通过"],
  ["warn", "待审核"],
  ["info", "即将开始"],
  ["done", "已结束"],
  ["off", "已取消"],
  ["rejected", "已驳回"],
]

export const SPECIMEN_ICONS = [
  "search", "menu", "close", "arrow-right", "arrow-left", "arrow-up-right",
  "chevron-down", "chevron-right", "user", "users", "calendar", "clock",
  "trophy", "shield", "pen", "news", "info", "alert", "check",
  "check-circle", "x-circle", "plus", "lock", "mail", "id", "phone", "heart",
  "reply", "pin", "edit", "trash", "eye", "eye-off", "logout", "download",
  "external", "copy", "settings", "flag", "map", "role-tank", "role-damage",
  "role-support", "chat",
]

export const ROWS: [string, string, string][] = [
  ["暑期内战回顾：48 人、8 支队伍、一个晚上", "战报", "自动分队第一次在大规模内战里使用，分差最大的一场只有 3 分。"],
  ["新赛季辅助位环境：从理解节奏开始", "攻略", "不讲数值，讲什么时候该交技能、什么时候该站出来。"],
]

export const PEOPLE: [string, string, string][] = [
  ["夜航", "社长", "思源"],
  ["白露", "内战负责人", "东川路电竞"],
  ["Kairo", "", ""],
]

const STYLE_ORDER = ["landscape", "skyline", "geometric", "waves", "dunes", "aurora", "arena", "planet", "forest"]
const STYLE_LABELS: Record<string, string> = {
  landscape: "山峦",
  skyline: "夜景",
  geometric: "几何",
  waves: "海面",
  dunes: "沙丘",
  aurora: "极光",
  arena: "舞台",
  planet: "星球",
  forest: "松林",
}

export const PLACEHOLDERS: { src: string; label: string; index: string }[] = []
for (let variant = 0; variant < 4; variant++) {
  for (const style of STYLE_ORDER) {
    const n = PLACEHOLDERS.length + 1
    PLACEHOLDERS.push({
      src: `/static/img/placeholders/cover-${String(n).padStart(2, "0")}.svg`,
      label: STYLE_LABELS[style],
      index: String(n).padStart(2, "0"),
    })
  }
}

const MOST_SEATS = 24

export function seats(taken: number, total: number): boolean[] {
  const got = Math.max(Math.trunc(Number(taken) || 0), 0)
  const need = Math.max(Math.trunc(Number(total) || 0), 0)
  if (need === 0) return []
  const cells = Math.min(need, MOST_SEATS)
  const filled = Math.min(cells, Math.round((got * cells) / need))
  return Array.from({ length: cells }, (_, index) => index < filled)
}

export function rankParts(label: string): [string, string] {
  const text = label.trim()
  const space = text.indexOf(" ")
  if (space < 0) return [text, ""]
  return [text.slice(0, space), text.slice(space + 1)]
}

export function loadStyleguide(): { title: string; clock: SampleClock } {
  return { title: "设计体系样张", clock: sampleClock() }
}

export function sampleClock(now: Date = new Date()): SampleClock {
  const day = shanghaiEvening(3, now)
  const close = shanghaiEvening(12, now)
  const past = shanghaiEvening(-40, now)
  return {
    dayDate: owDate(day),
    dayMd: owMd(day),
    dayTime: owTime(day),
    dayWeekday: owWeekday(day),
    dayMonth: owMonthNum(day),
    dayDom: owDay(day),
    closeDate: owDate(close),
    closeMd: owMd(close),
    closeTime: owTime(close),
    closeWeekday: owWeekday(close),
    pastDate: owDate(past),
    pastMd: owMd(past),
    pastTime: owTime(past),
  }
}

/** The specimen does not advertise itself: anyone who is not staff gets a 404. */
export function styleguideHidden(path: string, admin: boolean): boolean {
  return path.startsWith("/_styleguide/") && !admin
}
