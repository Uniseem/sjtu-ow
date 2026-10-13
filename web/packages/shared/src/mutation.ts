import { computed, nextTick, onMounted, onUnmounted, shallowRef } from "vue"
import { ApiError } from "@sjtu-ow/api"
import type { CallExtras } from "@sjtu-ow/api"
import { registerUnsaved } from "./leave"

type Attempt<T> = {
  body: T
  key: string
  controller: AbortController
}

export function hasHeldLetters(value: unknown): boolean {
  if (typeof value !== "object" || value === null || !("letters" in value)) return false
  const letters = value.letters
  return typeof letters === "object" && letters !== null && "batch" in letters
    && typeof letters.batch === "string" && letters.batch.length > 0
}

/**
 * Explicit actions (add, delete, send) retain an uncertain request exactly.
 * A manual retry cannot accidentally send edited inputs with the old key.
 */
export function useMutation<T, R>(
  transport: (body: T, extras: CallExtras) => Promise<R>,
  success: (result: R) => void | Promise<void>,
) {
  const pending = shallowRef(false)
  const message = shallowRef("")
  const fields = shallowRef<Record<string, string[]>>({})
  const retryAt = shallowRef<number | null>(null)
  const uncertain = shallowRef(false)
  let attempt: Attempt<T> | null = null
  let disposed = false
  let running: Promise<boolean> | null = null
  let unregister: (() => void) | undefined
  const canStart = computed(() => !pending.value && !uncertain.value)

  async function send(): Promise<boolean> {
    if (!attempt || disposed) return false
    if (retryAt.value !== null && Date.now() < retryAt.value) {
      message.value = "提交太频繁，请稍后再试。"
      return false
    }
    pending.value = true
    uncertain.value = false
    message.value = ""
    fields.value = {}
    const current = attempt
    try {
      const result = await transport(current.body, {
        key: current.key,
        signal: current.controller.signal,
        unauthorized: "throw",
      })
      if (disposed) return false
      // The write has succeeded even if refreshing its surrounding list fails.
      attempt = null
      uncertain.value = false
      retryAt.value = null
      // createClient has already started the mandatory confirmation-page
      // navigation. A page-specific success callback must not race it.
      if (!hasHeldLetters(result)) await success(result)
      return true
    } catch (error) {
      if (disposed) return false
      const apiError = error instanceof ApiError ? error : null
      const retryable = apiError === null || apiError.status === 0
        || apiError.status === 429 || apiError.status >= 500
      // Only retain a flight if the transport has not already succeeded.
      if (attempt === current) {
        uncertain.value = retryable
        if (!retryable) attempt = null
      }
      retryAt.value = apiError?.status === 429
        ? Date.now() + (apiError.retryAfter ?? 5) * 1000
        : null
      fields.value = apiError?.fields ?? {}
      message.value = apiError?.message || "暂时无法提交，请稍后再试。"
      if (apiError?.status === 401) message.value = "登录已失效，请重新登录后再试。"
      await nextTick()
      const field = document.querySelector<HTMLElement>("#main .is-invalid input, #main .is-invalid select, #main .is-invalid textarea")
      if (field) field.focus()
      else {
        const alert = document.querySelector<HTMLElement>("#main [role=alert]")
        if (alert) { alert.tabIndex = -1; alert.focus() }
      }
      return false
    } finally {
      pending.value = false
    }
  }

  function submit(body: T): Promise<boolean> {
    if (running) return running
    if (uncertain.value) {
      message.value = "上次提交尚未确认，请先重试那次提交。"
      return Promise.resolve(false)
    }
    attempt = {
      body: structuredClone(body),
      key: crypto.randomUUID(),
      controller: new AbortController(),
    }
    return start()
  }

  function start(): Promise<boolean> {
    const task = send()
    running = task
    void task.finally(() => { if (running === task) running = null })
    return task
  }

  function retry(): Promise<boolean> {
    if (running) return running
    if (!attempt) return Promise.resolve(false)
    return start()
  }

  function clear(): void {
    if (pending.value || uncertain.value) return
    fields.value = {}
    message.value = ""
    retryAt.value = null
  }

  onMounted(() => {
    unregister = registerUnsaved({
      dirty: () => uncertain.value,
      flush: async () => {
        if (running) await running
        return !pending.value && !uncertain.value
      },
      failed: () => {
        message.value = "上次提交还没有确认，请先重试那次提交。"
      },
    })
  })
  onUnmounted(() => {
    unregister?.()
    disposed = true
    attempt?.controller.abort()
  })

  return { pending, fields, message, uncertain, retryAt, canStart, submit, retry, clear }
}
