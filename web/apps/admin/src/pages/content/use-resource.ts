import { computed, onScopeDispose, shallowRef } from "vue"
import { ApiError } from "@sjtu-ow/api"
import { showReadError } from "../../core/read-error"

export function useContentResource<T>(read: (signal: AbortSignal) => Promise<T>, documentErrors = true) {
  const data = shallowRef<T | null>(null)
  const pending = shallowRef(false)
  const error = shallowRef<ApiError | null>(null)
  let controller: AbortController | null = null
  let sequence = 0
  let disposed = false

  async function load(): Promise<T | null> {
    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal
    const current = ++sequence
    pending.value = true
    error.value = null
    try {
      const result = await read(signal)
      if (disposed || current !== sequence) return null
      data.value = result
      return result
    } catch (cause) {
      if (disposed || signal.aborted || current !== sequence) return null
      error.value = cause instanceof ApiError
        ? cause
        : new ApiError(0, "network", "暂时无法加载，请稍后再试。")
      if (documentErrors) showReadError(cause)
      return null
    } finally {
      if (!disposed && current === sequence) pending.value = false
    }
  }

  onScopeDispose(() => {
    disposed = true
    sequence++
    controller?.abort()
  })
  return {
    data,
    pending,
    error,
    message: computed(() => error.value?.message ?? ""),
    status: computed(() => error.value?.status ?? null),
    load,
  }
}
