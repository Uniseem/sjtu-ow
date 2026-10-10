import "@sjtu-ow/styles/dist/site.css"
import { createClient, getApiSession } from "@sjtu-ow/api"
import { reactive } from "vue"
import { API } from "./api"
import { createApp } from "./main"
import { Loadbar, progressFromMatrix } from "./loadbar"
import { flat, statusOf, type PageData } from "./router"
import { styleguideHidden } from "./specimen"
import { toast } from "./toasts"
import { VIEWER, type Viewer } from "./viewer"
import { installDropdowns } from "./dropdowns"
import { PageRedirect, safeNext } from "@sjtu-ow/shared/navigation"

const raw = document.getElementById("ow-state")?.textContent ?? "null"
const state = JSON.parse(raw) as { data: PageData | null; viewer?: Viewer }
const page = reactive<PageData>(state.data ?? { title: "" })
const viewer = reactive<Viewer>(state.viewer ?? { user: null })

// Same-origin calls to Go. After every successful write the session is read
// again (12-architecture 6.4): the nickname, the letters waiting, the caps.
const api = createClient({
  onWrite: () => {
    getApiSession(api, { refresh: true }).then(
      (body) => {
        viewer.user = body.user && typeof body.user.nickname === "string" ? body.user : null
      },
      () => {},
    )
  },
})

const { app, router } = createApp(false)
app.provide("page-data", page)
app.provide(VIEWER, viewer)
app.provide(API, api)
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
// A chunk that is not there any more (a new build went out while this tab was
// open) or a page whose code broke: load the address whole, once
// (12-architecture 10).
router.onError((_err, to) => {
  bar.stop()
  if (!to) return
  // At most once a minute per address, or a chunk that is really broken
  // would reload forever.
  const key = "ow-reload:" + to.fullPath
  try {
    const last = Number(sessionStorage.getItem(key) ?? 0)
    if (Date.now() - last < 60_000) return
    sessionStorage.setItem(key, String(Date.now()))
  } catch {
    return
  }
  window.location.assign(to.fullPath)
})

router.isReady().then(() => {
  // createSSRApp: this hydrates the server's DOM (main.ts).
  app.mount("#app")
  document.documentElement.classList.add("js-ready")
})

// A whole-page load for what only the server paints: the login redirect and
// the error pages, with their real status codes (frontend-migration A2).
function leave(url: string): false {
  bar.stop()
  window.location.assign(url)
  return false
}

router.beforeResolve(async (to, from) => {
  if (styleguideHidden(to.path, viewer.user?.admin === true)) return false
  if (!from.matched.length) return
  if (to.meta.auth === "member" && viewer.user === null) {
    return leave("/accounts/login/?next=" + encodeURIComponent(to.fullPath))
  }
  if (to.meta.guest && viewer.user !== null) return leave(safeNext(to.query.next))
  const load = to.meta.load
  if (!load) return
  let data: PageData
  try {
    data = await load({ params: flat(to.params), query: flat(to.query), url: to.fullPath, api, viewer: async () => viewer, fetch, apiBase: "" })
  } catch (err) {
    if (err instanceof PageRedirect) return leave(err.location)
    const status = statusOf(err)
    // 401: the client has already sent the browser to the login page.
    if (status === 401) return false
    // Not reachable at all: stay on this page and say so.
    if (status === 0) {
      bar.stop()
      toast("网络连不上，请稍后再试", "error")
      return false
    }
    return leave(to.fullPath)
  }
  // Replace, not merge: keys from the previous page must not linger.
  for (const key of Object.keys(page)) {
    if (!(key in data)) delete page[key]
  }
  Object.assign(page, data)
})
