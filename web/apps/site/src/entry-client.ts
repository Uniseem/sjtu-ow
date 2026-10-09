import "@sjtu-ow/styles/dist/site.css"
import { reactive } from "vue"
import { createApp } from "./main"
import { Loadbar, progressFromMatrix } from "./loadbar"
import type { Load, PageData } from "./router"
import { styleguideHidden } from "./specimen"
import { VIEWER, type Viewer } from "./viewer"
import { installDropdowns } from "./dropdowns"

const raw = document.getElementById("ow-state")?.textContent ?? "null"
const state = JSON.parse(raw) as { data: PageData | null; viewer?: Viewer }
const page = reactive<PageData>(state.data ?? { title: "" })
const viewer = reactive<Viewer>(state.viewer ?? { user: null })
const { app, router } = createApp(false)
app.provide("page-data", page)
app.provide(VIEWER, viewer)
installDropdowns()

// The route loadbar: not on the first (server-rendered) page, only on
// navigations from one page to another.
const bar = new Loadbar(document.documentElement, () =>
  progressFromMatrix(getComputedStyle(document.querySelector(".c-loadbar") ?? document.body).transform),
)
router.beforeEach((_to, from) => {
  if (from.matched.length) bar.start()
})
router.afterEach((_to, from) => {
  if (from.matched.length) bar.arrive()
})
router.onError(() => bar.stop())

router.isReady().then(() => {
  app.mount("#app")
  document.documentElement.classList.add("js-ready")
})

router.beforeResolve(async (to, from) => {
  if (styleguideHidden(to.path, viewer.user?.admin === true)) return false
  if (!from.matched.length) return
  const load = to.meta.load as Load | undefined
  if (!load) return
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(to.params)) params[key] = Array.isArray(value) ? value[0] : value
  Object.assign(page, await load({ params, url: to.fullPath, fetch, apiBase: "" }))
})
