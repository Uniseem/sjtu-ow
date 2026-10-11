import type { SaveCurrent } from '@sjtu-ow/shared/autosave'

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Accept only a complete server projection with the same value kinds as this form. */
export function currentReader<T extends object>(initial: T) {
  function compatible(sample: unknown, value: unknown): boolean {
    if (sample === null) return value === null || typeof value === 'number'
    if (Array.isArray(sample)) {
      if (!Array.isArray(value)) return false
      if (sample.length === 0) return value.every(item => typeof item === 'string')
      return value.every(item => compatible(sample[0], item))
    }
    if (object(sample)) {
      return object(value) && Object.entries(sample).every(([key, item]) => key in value && compatible(item, value[key]))
    }
    if (typeof sample === 'number') return typeof value === 'number' && Number.isFinite(value)
    return typeof value === typeof sample
  }

  return function read(value: unknown): SaveCurrent<T> | null {
    if (!object(value) || !Number.isSafeInteger(value.version) || Number(value.version) < 1) return null
    if (!object(value.values) || !compatible(initial, value.values)) return null
    return { version: Number(value.version), values: value.values as T }
  }
}
