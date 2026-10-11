import { owDate, owTime } from "@sjtu-ow/shared/time"
export function date(value: string | null | undefined) {
  if (!value) return "—"
  const parsed = new Date(value)
  return Number.isFinite(parsed.getTime()) ? `${owDate(parsed)} ${owTime(parsed)}` : "—"
}
export function positive(value: unknown, fallback = 1): number {
  const n = Number(value)
  return Number.isSafeInteger(n) && n > 0 ? n : fallback
}
export function text(value: unknown): string { return typeof value === "string" ? value : "" }
export function state(value: string): string {
  const labels: Record<string, string> = {
    pending: "待审核", approved: "已通过", rejected: "已驳回", withdrawn: "已撤回",
    dissolved: "已撤销", draft: "草稿", published: "已发布", scheduled: "定时上线",
    finished: "已结束", ended: "已结束", cancelled: "已取消", waiting: "等待巡查", failed: "巡查失败",
    unreviewed: "未处理", reviewed: "已处理", taken_down: "已撤下", active: "正常",
    low: "低", medium: "中", high: "高", safe: "正常", unknown: "未判断",
  }
  return labels[value] ?? value
}
export function localHref(value: string): string | undefined {
  return value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : undefined
}
