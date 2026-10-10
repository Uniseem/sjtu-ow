import { nextTick, onUnmounted, ref } from "vue"
import { ApiError } from "@sjtu-ow/api"
import { safeNext } from "@sjtu-ow/shared/navigation"

export function useAccountForm() {
  const pending = ref(false)
  const message = ref("")
  const fields = ref<Record<string, string[]>>({})
  async function submit(action: () => Promise<void>) {
    if (pending.value) return
    pending.value = true
    message.value = ""
    fields.value = {}
    try { await action() } catch (error) {
      if (error instanceof ApiError) {
        fields.value = error.fields ?? {}
        message.value = Object.keys(fields.value).length ? "" : error.message || "暂时无法提交，请稍后再试。"
      } else {
        message.value = "暂时无法提交，请稍后再试。"
      }
      await nextTick()
      document.querySelector<HTMLElement>(".is-invalid input, .is-invalid select, .is-invalid textarea, .c-field__error")?.focus()
    } finally { pending.value = false }
  }
  return { pending, message, fields, submit }
}

export function useCodeCooldown() {
  const seconds = ref(0)
  let timer: ReturnType<typeof setInterval> | undefined
  function start() {
    if (timer) clearInterval(timer)
    const until = Date.now() + 10_000
    seconds.value = 10
    timer = setInterval(() => {
      seconds.value = Math.max(0, Math.ceil((until - Date.now()) / 1000))
      if (!seconds.value) { clearInterval(timer); timer = undefined }
    }, 250)
  }
  onUnmounted(() => { if (timer) clearInterval(timer) })
  return { seconds, start }
}

export function finishAccountAction(target: string) {
  window.location.assign(safeNext(target))
}
