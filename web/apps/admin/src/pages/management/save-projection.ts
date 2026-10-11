import { readSaveReceipt, primitiveValues, type ValueValidator } from "@sjtu-ow/shared/save-receipt"
import type { SaveReceipt } from "@sjtu-ow/shared/autosave"

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
/** Normalize optional Go pointers and project only this form's owned fields. */
export function formReceipt<T extends object>(
  raw: unknown,
  shape: T,
  validate: ValueValidator<T> = primitiveValues(shape),
): SaveReceipt<T> {
  if (!record(raw)) return readSaveReceipt(raw, shape, validate)
  if (raw.values === undefined || raw.values === null) {
    return readSaveReceipt({ ...raw, values: undefined }, shape, validate)
  }
  if (!record(raw.values)) return readSaveReceipt(raw, shape, validate)
  const values: Record<string, unknown> = {}
  for (const key of Object.keys(shape)) {
    if (Object.hasOwn(raw.values, key)) values[key] = raw.values[key]
  }
  return readSaveReceipt({ ...raw, values }, shape, validate)
}
