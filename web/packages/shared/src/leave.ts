export type LeaveParticipant = {
  dirty: () => boolean
  flush: () => Promise<boolean>
  failed: () => void
}

/** One coordinator per browser document; no listeners are installed in SSR. */
const participants = new Set<LeaveParticipant>()
let installed = false
let leaving: Promise<boolean> | null = null
let programmatic = false

/** The API has received a successful write and is leaving for its mandatory
 * held-letter confirmation page. Suppress only this synchronous unload. */
export function permitProgrammaticLeave(): void {
  programmatic = true
  setTimeout(() => { programmatic = false }, 0)
}

export function programmaticLeavePermitted(): boolean { return programmatic }

export function flushBeforeLeave(): Promise<boolean> {
  if (leaving) return leaving
  const task = (async () => {
    for (const participant of [...participants]) {
      if (!participant.dirty()) continue
      if (!await participant.flush()) {
        participant.failed()
        return false
      }
    }
    return true
  })()
  leaving = task
  void task.finally(() => { if (leaving === task) leaving = null })
  return task
}

function beforeUnload(event: BeforeUnloadEvent): void {
  if (programmatic) return
  if (![...participants].some((participant) => participant.dirty())) return
  event.preventDefault()
  event.returnValue = ""
}

function eligibleLink(event: MouseEvent): HTMLAnchorElement | null {
  if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return null
  if (!(event.target instanceof Element)) return null
  const anchor = event.target.closest<HTMLAnchorElement>("a[href]")
  if (!anchor || anchor.hasAttribute("download") || anchor.target && anchor.target !== "_self") return null
  if (anchor.relList.contains("external")) return null
  const href = new URL(anchor.href, location.href)
  if (href.protocol !== "http:" && href.protocol !== "https:") return null
  if (href.origin === location.origin && href.pathname === location.pathname && href.search === location.search && href.hash) return null
  return anchor
}

function click(event: MouseEvent): void {
  if (![...participants].some((participant) => participant.dirty())) return
  const anchor = eligibleLink(event)
  if (!anchor) return
  // Capture also covers ordinary hrefs in the old-template navigation.
  // Prevent the link's own Vue Router handler from running before the flush.
  const destination = anchor.href
  event.preventDefault()
  event.stopImmediatePropagation()
  void flushBeforeLeave().then((saved) => {
    if (saved) window.location.assign(destination)
  })
}

function install(): void {
  if (installed) return
  installed = true
  document.addEventListener("click", click, true)
  window.addEventListener("beforeunload", beforeUnload)
}

function uninstall(): void {
  if (!installed || participants.size) return
  installed = false
  document.removeEventListener("click", click, true)
  window.removeEventListener("beforeunload", beforeUnload)
}

export function registerUnsaved(participant: LeaveParticipant): () => void {
  participants.add(participant)
  install()
  return () => {
    participants.delete(participant)
    uninstall()
  }
}
