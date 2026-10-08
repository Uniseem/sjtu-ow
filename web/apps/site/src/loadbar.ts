// The route loadbar (design 13.2.4): the bar itself and its rhythm live in
// the stylesheet (.c-loadbar, is-loading, is-arriving); this module only
// moves the classes and notes where the crawl got to. SPA navigation means
// the old cross-page relay (loading.js + arrival.js) is no longer needed.
export type LoadbarRoot = {
  classList: { add(name: string): void; remove(...names: string[]): void }
  style: { setProperty(name: string, value: string): void }
}

export const LOADBAR_DONE = 600 // ms: 300 to fill + 250 to fade, a little air
const STUCK = 15000 // ms: a navigation that never ends stops crawling

// How far the bar has got: the x scale of its transform matrix.
export function progressFromMatrix(matrix: string | null): number {
  const parts = /^matrix\(([^,]+),/.exec(matrix ?? "")
  return parts ? Number(parts[1]) : 0
}

export class Loadbar {
  private timer: ReturnType<typeof setTimeout> | null = null

  constructor(
    private root: LoadbarRoot,
    private progress: () => number,
  ) {}

  // A navigation is on its way. The stylesheet holds the bar back for
  // 150 ms, so a page that is already there never shows one.
  start() {
    this.clear()
    this.root.classList.add("is-loading")
    this.timer = setTimeout(() => this.stop(), STUCK)
  }

  // The new page is in: run on from where the crawl got to, fill, fade.
  arrive() {
    const from = this.progress()
    this.clear()
    this.root.style.setProperty("--loadbar-from", String(from))
    this.root.classList.add("is-arriving")
    this.timer = setTimeout(() => this.stop(), LOADBAR_DONE)
  }

  // The navigation failed or was cancelled: take the bar away at once.
  stop() {
    this.clear()
  }

  private clear() {
    if (this.timer !== null) clearTimeout(this.timer)
    this.timer = null
    this.root.classList.remove("is-loading", "is-arriving")
  }
}
