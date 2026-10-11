import type { Router } from "vue-router"
import { flushBeforeLeave } from "@sjtu-ow/shared/leave"

/** Plain links retain the legacy address and work without interception. Only
 * eligible local admin links become SPA transitions; modifiers and exports
 * continue to use the browser's native semantics. */
export function installAdminLinks(router: Router): () => void {
  async function navigate(event: MouseEvent): Promise<void> {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return
    if (!(event.target instanceof Element)) return
    const anchor = event.target.closest<HTMLAnchorElement>("a[href]")
    if (!anchor || anchor.download || anchor.target && anchor.target !== "_self" || anchor.relList.contains("external")) return
    const url = new URL(anchor.href, location.href)
    if (url.origin !== location.origin || !url.pathname.startsWith("/admin/")) return
    if (url.pathname === location.pathname && url.search === location.search && url.hash) return
    if (!router.resolve(url.pathname).matched.length) return
    event.preventDefault()
    if (!await flushBeforeLeave()) return
    await router.push(url.pathname + url.search + url.hash)
  }
  const listener = (event: MouseEvent) => { void navigate(event) }
  document.addEventListener("click", listener)
  return () => document.removeEventListener("click", listener)
}
