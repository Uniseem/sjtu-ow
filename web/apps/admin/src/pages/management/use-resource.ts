import { computed, onUnmounted, shallowRef, watch, type WatchSource } from "vue"
import { ApiError } from "@sjtu-ow/api"
/** Latest-route-wins reader. A failed refresh leaves the previous value available. */
export function useResource<T>(source: WatchSource<unknown>, read: (signal: AbortSignal) => Promise<T>, delay = 0) {
  const data = shallowRef<T | null>(null)
  const pending = shallowRef(false)
  const message = shallowRef("")
  const status = shallowRef(0)
  let generation = 0
  let flight: AbortController | undefined
  let disposed = false
  let timer: ReturnType<typeof setTimeout> | undefined
  async function refresh() {
    const current = ++generation
    flight?.abort()
    flight = new AbortController()
    pending.value = true
    message.value = ""
    try {
      const result = await read(flight.signal)
      if (current !== generation || disposed) return
      data.value = result
      status.value = 200
    } catch (error) {
      if (current !== generation || disposed) return
      status.value = error instanceof ApiError ? error.status : 0
      message.value = error instanceof ApiError ? error.message : "暂时无法加载，请稍后再试。"
    } finally {
      if (current === generation && !disposed) pending.value = false
    }
  }
  watch(source, () => {
    if (timer) clearTimeout(timer)
    if (delay === 0) { data.value = null; void refresh(); return }
    flight?.abort()
    generation++
    pending.value = true
    timer = setTimeout(() => { void refresh() }, delay)
  }, { immediate: true })
  onUnmounted(() => { disposed = true; generation++; flight?.abort(); if (timer) clearTimeout(timer) })
  return { data, pending, message, status, refresh, forbidden: computed(() => status.value === 403) }
}
