import type {
  GetApiAdminScrimsIdBoardOut,
  GetApiAdminScrimsIdOut,
  GetApiAdminScrimsOut,
  GetApiAdminTournamentsIdBoardOut,
  GetApiAdminTournamentsIdOut,
  GetApiAdminTournamentsOut,
} from "@sjtu-ow/api"

export type ActivityKind = "tournaments" | "scrims"
export type ActivityAction = "publish" | "finish" | "cancel" | "delete"
export type Tournament = NonNullable<GetApiAdminTournamentsIdOut["tournament"]>
export type Scrim = NonNullable<GetApiAdminScrimsIdOut["scrim"]>
export type TournamentRow = GetApiAdminTournamentsOut["tournaments"][number]
export type ScrimRow = GetApiAdminScrimsOut["scrims"][number]
export type TournamentBoard = GetApiAdminTournamentsIdBoardOut
export type TournamentEntry = TournamentBoard["entries"][number]
export type ScrimBoard = GetApiAdminScrimsIdBoardOut
export type ScrimSignup = ScrimBoard["signups"][number]
export type Role = "tank" | "damage" | "support"
export type Side = "a" | "b" | ""

export const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "draft", label: "草稿" },
  { value: "published", label: "已发布" },
  { value: "finished", label: "已结束" },
  { value: "cancelled", label: "已取消" },
] as const

export const modeOptions = [
  { value: "team", label: "整队报名" },
  { value: "individual", label: "个人报名" },
] as const

export const formatOptions = [
  { value: "rq_5v5", label: "角色限定 5v5" },
  { value: "rq_6v6", label: "角色限定 6v6" },
  { value: "open_5v5", label: "不限位置 5v5" },
  { value: "open_6v6", label: "不限位置 6v6" },
] as const

export const roleOptions = [
  { value: "tank", label: "坦克" },
  { value: "damage", label: "输出" },
  { value: "support", label: "支援" },
] as const

export const orderOptions = [
  { value: "created", label: "按报名时间" },
  { value: "rating", label: "按段位" },
] as const

export function statusLabel(status: string): string {
  return statusOptions.find((option) => option.value === status)?.label ?? status
}

export function modeLabel(mode: string): string {
  return modeOptions.find((option) => option.value === mode)?.label ?? mode
}

export function formatLabel(format: string): string {
  return formatOptions.find((option) => option.value === format)?.label ?? format
}

export function roleLabel(role: string): string {
  return roleOptions.find((option) => option.value === role)?.label ?? "不限位置"
}

export function activityLabel(kind: ActivityKind): string {
  return kind === "tournaments" ? "赛事" : "内战"
}

export function actionLabel(action: ActivityAction, kind: ActivityKind): string {
  if (action === "finish") return "标记为已结束"
  if (action === "publish") return `发布${activityLabel(kind)}`
  if (action === "cancel") return `取消${activityLabel(kind)}`
  return `删除${activityLabel(kind)}`
}

export function activityHref(kind: ActivityKind, id?: number): string {
  return id === undefined ? `/admin/${kind}/` : `/admin/${kind}/edit/${id}/`
}

export function actionHref(kind: ActivityKind, id: number, action: ActivityAction): string {
  if (action === "delete") return `/admin/${kind}/delete/${id}/`
  if (kind === "tournaments" && action !== "cancel") return `/admin/${kind}/${id}/action/${action}/`
  return `/admin/${kind}/${id}/${action}/`
}

export function notifyHref(kind: ActivityKind, id: number, participants = false): string {
  const singular = kind === "tournaments" ? "tournament" : "scrim"
  return `/admin/announce/${singular}/${id}/${participants ? "?to=participants" : ""}`
}

export function timestamp(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return "—"
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date)
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? ""
  return `${part("year")}.${part("month")}.${part("day")} ${part("hour")}:${part("minute")}`
}

/** datetime-local is a Shanghai wall-clock input, regardless of the laptop zone. */
export function localMinute(value: string | null | undefined): string {
  if (!value) return ""
  const text = timestamp(value)
  return text === "—" ? "" : text.replaceAll(".", "-").replace(" ", "T")
}

export function keepSeconds(value: string, committed: string | null): string | null {
  if (!value) return null
  if (localMinute(committed) === value) return committed
  // Explicit offset avoids browser-local interpretation on overseas computers.
  const date = new Date(`${value}:00+08:00`)
  return Number.isFinite(date.getTime()) ? date.toISOString() : null
}

export function teamSize(format: string): number {
  return format.endsWith("6v6") ? 6 : 5
}

export function roleRequirements(format: string): Record<string, number> {
  if (format === "rq_5v5") return { tank: 1, damage: 2, support: 2 }
  if (format === "rq_6v6") return { tank: 2, damage: 2, support: 2 }
  return { "": teamSize(format) }
}

export function queryText(value: unknown): string {
  return typeof value === "string" ? value : ""
}

export function numericId(value: unknown): number {
  const id = Number(value)
  return Number.isSafeInteger(id) && id > 0 ? id : 0
}

export function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

export function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []
}
