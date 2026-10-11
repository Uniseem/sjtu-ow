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
        fields.value = Object.fromEntries(Object.entries(error.fields ?? {}).filter(([, errors]) => errors.length > 0))
        message.value = Object.keys(fields.value).length ? "" : error.message || "暂时无法提交，请稍后再试。"
      } else {
        message.value = "暂时无法提交，请稍后再试。"
      }
      await nextTick()
      const invalid = document.querySelector<HTMLElement>("#main .is-invalid input, #main .is-invalid select, #main .is-invalid textarea")
      const alert = document.querySelector<HTMLElement>("#main .c-field__error")
      if (invalid) invalid.focus()
      else if (alert) { alert.tabIndex = -1; alert.focus() }
    } finally { pending.value = false }
  }
  return { pending, message, fields, submit }
}

export function useCodeCooldown() {
  const seconds = ref(0)
  let timer: ReturnType<typeof setInterval> | undefined
  function start(waitSeconds = 10) {
    if (timer) clearInterval(timer)
    const wait = Number.isFinite(waitSeconds) ? Math.max(0, Math.ceil(waitSeconds)) : 10
    const until = Date.now() + wait * 1000
    seconds.value = wait
    if (!wait) { timer = undefined; return }
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
