import { reactive } from "vue"

// Toasts (design 13.2.6 c-toast): small notes that pop over the page and
// go away on their own. The list lives outside the components so anything
// can call toast(); the container in App.vue paints what is in it.
export type ToastKind = "info" | "success" | "error" | "warning"

export type Toast = { id: number; text: string; kind: ToastKind }

export const toasts = reactive<Toast[]>([])

const LINGER = 4500
let next = 1

export function toast(text: string, kind: ToastKind = "info") {
  const item = { id: next++, text, kind }
  toasts.push(item)
  setTimeout(() => {
    const at = toasts.indexOf(item)
    if (at >= 0) toasts.splice(at, 1)
  }, LINGER)
}
