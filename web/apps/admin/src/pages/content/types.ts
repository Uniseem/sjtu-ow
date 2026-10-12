import type {
  GetApiAdminArticlesIdOut,
  GetApiAdminCategoriesOut,
  GetApiAdminImageCollectionsOut,
  GetApiAdminImagesOut,
  GetApiImagesIdOut,
} from "@sjtu-ow/api"

export type Article = NonNullable<GetApiAdminArticlesIdOut["article"]>
export type Category = NonNullable<GetApiAdminCategoriesOut["items"][number]>
export type Image = GetApiAdminImagesOut["items"][number]
export type ImageDetail = GetApiImagesIdOut
export type Collection = GetApiAdminImageCollectionsOut["collections"][number]
export type ArticleDraft = NonNullable<GetApiAdminArticlesIdOut["revision"]>
export type ArticleStatus = "draft" | "live" | "changed" | "scheduled"

export function articleStatus(article: Article): ArticleStatus {
  if (article.live) return article.has_unpublished_changes ? "changed" : "live"
  return article.go_live_at ? "scheduled" : "draft"
}

export const articleStatuses: Record<ArticleStatus, string> = {
  draft: "草稿",
  live: "已发布",
  changed: "已发布·有改动",
  scheduled: "定时上线",
}

export const articleStatusKinds: Record<ArticleStatus, string> = { draft: "done", live: "ok", changed: "warn", scheduled: "info" }

export function emptyArticle(): ArticleDraft {
  return {
    title: "",
    slug: "",
    category_id: null,
    cover_image_id: null,
    summary: "",
    body_md: "",
    author_id: null,
    comments_enabled: true,
    related_tournament_id: null,
    seo_title: "",
    search_description: "",
    go_live_at: null,
    expire_at: null,
  }
}

export function draftFromArticle(article: Article): ArticleDraft {
  return {
    title: article.title,
    slug: article.slug,
    category_id: article.category_id ?? null,
    cover_image_id: article.cover_image_id ?? null,
    summary: article.summary,
    body_md: article.body_md,
    author_id: article.author_id ?? null,
    comments_enabled: article.comments_enabled,
    related_tournament_id: article.related_tournament_id ?? null,
    seo_title: article.seo_title,
    search_description: article.search_description,
    go_live_at: article.go_live_at ?? null,
    expire_at: article.expire_at ?? null,
  }
}

export function positiveID(value: unknown): number | null {
  const parsed = typeof value === "string" || typeof value === "number" ? Number(value) : NaN
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null
}

export function humanBytes(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

/** datetime-local represents Shanghai time, regardless of the editor's OS zone. */
export function localDateTime(value: string | null | undefined): string {
  if (!value) return ""
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ""
  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date)
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? ""
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`
}

export function wireDateTime(value: string, original?: string | null): string | null {
  if (!value) return null
  if (original && localDateTime(original) === value) return original
  return `${value}:00+08:00`
}

export function publicationMissing(draft: ArticleDraft): string[] {
  const missing: string[] = []
  if (!draft.title.trim()) missing.push("标题")
  if (!draft.category_id) missing.push("分类")
  if (!draft.body_md.trim()) missing.push("正文")
  return missing
}

export function formatContentTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return "—"
  const formatter = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
  return formatter.format(date).replaceAll("-", ".")
}
