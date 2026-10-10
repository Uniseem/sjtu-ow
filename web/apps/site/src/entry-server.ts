import { renderSSRHead } from "@unhead/vue/server"
import { createClient, getApiSession, type Requester } from "@sjtu-ow/api"
import { renderToString } from "vue/server-renderer"
import { API } from "./api"
import { createApp } from "./main"
import { flat, statusOf, type Load, type LoadCtx, type PageData } from "./router"
import { styleguideHidden } from "./specimen"
import { VIEWER, type Viewer } from "./viewer"

export type Rendered =
  | { kind: "slash"; location: string }
  | { kind: "login"; next: string }
  | {
      kind: "page"
      status: number
      html: string
      head: string
      state: { data: PageData | null; viewer: Viewer } | null
      viewer: Viewer
    }

export type RenderOpts = {
  apiBase: string
  fetch: typeof fetch
  headers: { get(name: string): string | null }
  load?: Load
}

// Placeholder bodies until the error pages follow templates/errors
// (frontend-migration A12).
const ERROR_HTML: Record<number, string> = {
  403: "<main><h1>没有权限看这个页面</h1></main>",
  404: "<main><h1>找不到这个页面</h1></main>",
  429: "<main><h1>操作太频繁</h1></main>",
  503: "<main><h1>站点暂时连不上</h1></main>",
}

const VISITOR: Viewer = { user: null }

// Go takes 5 seconds at most per call from here (12-architecture 6.2 step 4).
const API_TIMEOUT = 5000

function pathnameOf(url: string): string {
  return new URL(url, "http://site").pathname
}

export async function render(url: string, opts: RenderOpts): Promise<Rendered> {
  const { app, router, head } = createApp(true)
  const parsed = new URL(url, "http://site")
  const pathname = parsed.pathname
  if (pathname !== "/" && !pathname.endsWith("/")) {
    const next = pathname + "/"
    if (router.resolve(next).matched.length > 0) {
      return { kind: "slash", location: next + parsed.search }
    }
  }
  await router.push(url)
  await router.isReady()
  const route = router.currentRoute.value
  if (!route.matched.length) return page(404, VISITOR, head)

  // Every call to Go carries the visitor's cookie, IP and request id.
  const ssrFetch: typeof fetch = (input, init) => {
    const h = forward(opts.headers)
    if (init?.headers) new Headers(init.headers).forEach((v, k) => h.set(k, v))
    return opts.fetch(input, { ...init, headers: h })
  }
  const api = createClient({
    fetch: ssrFetch,
    base: opts.apiBase,
    timeoutMs: API_TIMEOUT,
    location: () => pathname + parsed.search,
    assign: () => {},
  })
  const ctx: LoadCtx = {
    params: flat(route.params),
    query: flat(route.query),
    url,
    api,
    fetch: ssrFetch,
    apiBase: opts.apiBase,
  }

  const [sessionR, loadR] = await Promise.allSettled([fetchSession(api), runLoad(opts.load ?? route.meta.load, ctx)])
  if (sessionR.status === "rejected") return page(503, VISITOR, head)
  const viewer = sessionR.value
  const next = pathname + parsed.search
  if (route.meta.auth === "member" && viewer.user === null) return { kind: "login", next }
  if (loadR.status === "rejected") {
    const status = statusOf(loadR.reason)
    if (status === 401) return { kind: "login", next }
    if (status === 403 || status === 404 || status === 429) return page(status, viewer, head)
    return page(503, viewer, head)
  }
  if (styleguideHidden(pathname, viewer.user?.admin === true)) return page(404, viewer, head)
  app.provide(VIEWER, viewer)
  app.provide(API, api)
  app.provide("page-data", loadR.value)
  const html = await renderToString(app)
  const tags = await renderSSRHead(head)
  return { kind: "page", status: 200, html, head: tags.headTags, state: { data: loadR.value, viewer }, viewer }
}

// Error pages carry no state and no entry script: their HTML is not what
// the app would paint, so hydration would be wrong (12-architecture 6.5,
// error pages stay without script).
async function page(status: number, viewer: Viewer, head: ReturnType<typeof createApp>["head"]): Promise<Rendered> {
  const tags = await renderSSRHead(head)
  return { kind: "page", status, html: ERROR_HTML[status] ?? ERROR_HTML[404], head: tags.headTags, state: null, viewer }
}

async function runLoad(load: Load | undefined, ctx: LoadCtx): Promise<PageData> {
  if (!load) return { title: "" }
  return load(ctx)
}

// The whole session goes to the page (frontend-migration A6): the account
// area, the back office's tabs (superuser, caps) and the pages read it.
async function fetchSession(api: Requester): Promise<Viewer> {
  try {
    const user = (await getApiSession(api)).user
    // Go always sends a nickname; anything else is not a session to trust.
    if (!user || typeof user.nickname !== "string") return VISITOR
    return { user }
  } catch (err) {
    if (statusOf(err) === 401) return VISITOR
    throw err
  }
}

function forward(headers: { get(name: string): string | null }): Headers {
  const out = new Headers()
  for (const name of ["cookie", "x-real-ip", "x-request-id"]) {
    const value = headers.get(name)
    if (value) out.set(name, value)
  }
  return out
}
