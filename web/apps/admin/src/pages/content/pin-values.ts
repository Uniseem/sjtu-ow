import type { HomePinsDraft } from "./pending"
import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import type { ValueValidator } from "@sjtu-ow/shared/save-receipt"

export function validPinIDs(value: unknown): value is number[] {
  return Array.isArray(value) && value.length <= 3
    && value.every((id: unknown) => typeof id === "number" && Number.isSafeInteger(id) && id > 0)
    && new Set(value).size === value.length
}
export const validatePinValue: ValueValidator<HomePinsDraft> = <K extends keyof HomePinsDraft & string>(name: K, value: unknown): value is HomePinsDraft[K] => {
  return name === "article_ids" && validPinIDs(value)
}
export function readPinCurrent(value: unknown): SaveCurrent<HomePinsDraft> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  if (typeof record.version !== "number" || !Number.isSafeInteger(record.version) || record.version < 0) return null
  if (!record.values || typeof record.values !== "object" || Array.isArray(record.values)) return null
  const values = record.values as Record<string, unknown>
  if (!validPinIDs(values.article_ids)) return null
  return { version: record.version, values: { article_ids: [...values.article_ids] } }
}
