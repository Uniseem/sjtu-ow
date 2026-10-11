import type { ValueValidator } from "@sjtu-ow/shared/save-receipt"
import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import type { ArticleDraft } from "./types"

const idFields = new Set(["category_id", "cover_image_id", "author_id", "related_tournament_id"])
const timeFields = new Set(["go_live_at", "expire_at"])
export const validateArticleValue: ValueValidator<ArticleDraft> = <K extends keyof ArticleDraft & string>(name: K, value: unknown): value is ArticleDraft[K] => {
  if (idFields.has(name)) return value === null || typeof value === "number" && Number.isSafeInteger(value) && value > 0
  if (timeFields.has(name)) return value === null || typeof value === "string" && Number.isFinite(Date.parse(value))
  if (name === "comments_enabled") return typeof value === "boolean"
  return typeof value === "string"
}
export function readArticleCurrent(value: unknown, shape: ArticleDraft): SaveCurrent<ArticleDraft> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  if (typeof record.version !== "number" || !Number.isSafeInteger(record.version) || record.version < 0) return null
  if (!record.values || typeof record.values !== "object" || Array.isArray(record.values)) return null
  const values = record.values as Record<string, unknown>
  for (const name of Object.keys(shape) as (keyof ArticleDraft & string)[]) {
    if (!Object.hasOwn(values, name) || !validateArticleValue(name, values[name])) return null
  }
  return { version: record.version, values: structuredClone(values) as ArticleDraft }
}
