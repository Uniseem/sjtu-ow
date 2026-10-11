import { ApiError } from "@sjtu-ow/api"
import type { SaveReceipt } from "./autosave"

function record(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

function invalid(): never {
  throw new ApiError(0, "invalid_receipt", "保存回执无效，请稍后重试。")
}

export type ValueValidator<T extends object> = <K extends keyof T & string>(name: K, value: unknown) => value is T[K]

/** Parse a real receipt. The old `{result: 'ok'}` response cannot pass. */
export function readSaveReceipt<T extends object>(
  value: unknown,
  shape: T,
  validate: ValueValidator<T>,
): SaveReceipt<T> {
  const result = record(value)
  if (!result || typeof result.version !== "number" || !Number.isSafeInteger(result.version) || result.version < 0) invalid()
  if (!Array.isArray(result.saved) || result.saved.some((name: unknown) => typeof name !== "string" || !Object.hasOwn(shape, name))) invalid()
  const saved = result.saved as string[]
  if (new Set(saved).size !== saved.length) invalid()
  const fields: Record<string, string[]> = {}
  if (result.fields !== undefined) {
    const errors = record(result.fields)
    if (!errors) invalid()
    for (const [name, errorsForField] of Object.entries(errors)) {
      if (!Array.isArray(errorsForField) || errorsForField.some((message: unknown) => typeof message !== "string")) invalid()
      fields[name] = [...errorsForField] as string[]
    }
  }
  if (saved.some((name) => fields[name]?.length)) invalid()
  const values: Partial<T> = {}
  if (result.values !== undefined) {
    const normalized = record(result.values)
    if (!normalized) invalid()
    for (const [key, normalizedValue] of Object.entries(normalized)) {
      if (!Object.hasOwn(shape, key)) invalid()
      const name = key as keyof T & string
      if (!validate(name, normalizedValue)) invalid()
      values[name] = normalizedValue
    }
  }
  if (result.saved_at !== undefined && (typeof result.saved_at !== "string" || !Number.isFinite(Date.parse(result.saved_at)))) invalid()
  return {
    version: result.version,
    saved: [...saved],
    fields,
    values,
    saved_at: result.saved_at as string | undefined,
  }
}

/** Validators follow the initial domain shape without coercing booleans/null. */
export function primitiveValues<T extends object>(shape: T): ValueValidator<T> {
  return <K extends keyof T & string>(name: K, value: unknown): value is T[K] => {
    const original = shape[name]
    if (original === null || typeof original === "number") {
      return value === null || typeof value === "number" && Number.isFinite(value)
    }
    if (typeof original === "boolean") return typeof value === "boolean"
    if (typeof original === "string") return typeof value === "string"
    if (Array.isArray(original)) {
      return Array.isArray(value) && value.every((entry: unknown) => typeof entry === "string")
    }
    return false
  }
}
