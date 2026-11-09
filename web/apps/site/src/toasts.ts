import { reactive } from "vue"

// Toasts (design 13.2.6 c-toast): small notes that pop over the page and
// go away on their own. The list lives outside the components so anything
// can call toast(); the container in App.vue paints what is in it.
export type ToastKind = "info" | "success" | "error" | "warning"

export type ToastPhase = "visible" | "leaving"
export type Toast = { id: number; text: string; kind: ToastKind; phase: ToastPhase }

export const toasts = reactive<Toast[]>([])

const LINGER = 4500
const REMOVE_AFTER = 200 // 180ms exit, plus one paint before removing the node.
let next = 1

export function beginToastLifetime(leave: () => void, remove: () => void): () => void {
  let exiting: ReturnType<typeof setTimeout> | undefined
  const visible = setTimeout(() => { leave(); exiting = setTimeout(remove, REMOVE_AFTER) }, LINGER)
  return () => { clearTimeout(visible); if (exiting !== undefined) clearTimeout(exiting) }
}

export function toast(text: string, kind: ToastKind = "info") {
  const item = reactive<Toast>({ id: next++, text, kind, phase: "visible" })
  toasts.push(item)
  beginToastLifetime(() => { item.phase = "leaving" }, () => {
    const at = toasts.indexOf(item)
    if (at >= 0) toasts.splice(at, 1)
  })
}
