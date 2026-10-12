import { ApiError } from "@sjtu-ow/api"
import { errorDocument } from "@sjtu-ow/shared/error-page"
import type { App } from "vue"

export function readErrorDocument(error: unknown): string | null {
  return error instanceof ApiError && (error.status === 403 || error.status === 404)
    ? errorDocument(error.status) : null
}

/** A failed page read has the old standalone error document at the same URL.
 * Dialog reads opt out; writes retain their local field/error feedback. */
export function showReadError(error: unknown): void {
  const html = readErrorDocument(error)
  if (!html || typeof document === "undefined") return
  queueMicrotask(() => {
    const root = document.getElementById("admin-app") as (HTMLElement & { __vue_app__?: App }) | null
    root?.__vue_app__?.unmount()
    document.open()
    document.write(html)
    document.close()
  })
}
