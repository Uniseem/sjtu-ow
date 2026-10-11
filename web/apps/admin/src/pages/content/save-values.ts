import type { SaveCurrent } from "@sjtu-ow/shared/autosave"
import { primitiveValues } from "@sjtu-ow/shared/save-receipt"

export function readContentCurrent<T extends object>(value: unknown, shape: T): SaveCurrent<T> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  if (typeof record.version !== "number" || !Number.isSafeInteger(record.version) || record.version < 0) return null
  if (!record.values || typeof record.values !== "object" || Array.isArray(record.values)) return null
  const raw = record.values as Record<string, unknown>
  const validate = primitiveValues(shape)
  for (const key of Object.keys(shape) as (keyof T & string)[]) {
    if (!Object.hasOwn(raw, key) || !validate(key, raw[key])) return null
  }
  return { version: record.version, values: structuredClone(raw) as T }
}

export type CategoryDraft = {
  name: string
  slug: string
  description: string
  sort_order: number
  allow_submission: boolean
}

export function emptyCategory(): CategoryDraft {
  return { name: "", slug: "", description: "", sort_order: 0, allow_submission: false }
}
