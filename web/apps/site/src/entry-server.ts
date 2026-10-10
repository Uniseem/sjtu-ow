import { renderSSRHead } from "@unhead/vue/server"
import { createClient, getApiSession, type Requester } from "@sjtu-ow/api"
import { renderToString } from "vue/server-renderer"
import { API } from "./api"
import { createApp } from "./main"
import { flat, statusOf, type Load, type LoadCtx, type PageData } from "./router"
import type { ErrorStatus } from "./error-page"
import { styleguideHidden } from "./specimen"
import { VIEWER, type Viewer } from "./viewer"

export type Rendered =
  | { kind: "slash"; location: string }
  | { kind: "login"; next: string }
  // Error pages are their own document (error-page.ts), not the app.
  | { kind: "error"; status: ErrorStatus; viewer: Viewer }
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

const VISITOR: Viewer = { user: null }

// Go takes 5 seconds at most per call from here (12-architecture 6.2 step 4).
const API_TIMEOUT = 5000

function pathnameOf(url: string): string {
  return new URL(url, "http://site").pathname
}

export async function render(url: string, opts: RenderOpts): Promise<Rendered> {
  const { app, router, head } = createApp(true)
  const error = (status: ErrorStatus, viewer: Viewer = VISITOR): Rendered => ({ kind: "error", status, viewer })
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
  if (!route.matched.length) return error(404)

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
  if (sessionR.status === "rejected") return error(errorStatusOf(sessionR.reason))
  const viewer = sessionR.value
  const next = pathname + parsed.search
  if (route.meta.auth === "member" && viewer.user === null) return { kind: "login", next }
  if (loadR.status === "rejected") {
    const status = statusOf(loadR.reason)
    if (status === 401) return { kind: "login", next }
    return error(errorStatusOf(loadR.reason), viewer)
  }
  if (styleguideHidden(pathname, viewer.user?.admin === true)) return error(404, viewer)
  app.provide(VIEWER, viewer)
  app.provide(API, api)
  app.provide("page-data", loadR.value)
  const html = await renderToString(app)
  const tags = await renderSSRHead(head)
  return { kind: "page", status: 200, html, head: tags.headTags, state: { data: loadR.value, viewer }, viewer }
}

// Which error page a failed call becomes: 403, 404 and 429 as they are; Go
// not reachable or not answering (0, 502–504) is the maintenance page; any
// other failure (Go's 500, a bug in a load) is the 500 page.
export function errorStatusOf(err: unknown): ErrorStatus {
  const status = statusOf(err)
  if (status === 403 || status === 404 || status === 429) return status
  if (status === 0 || status === 502 || status === 503 || status === 504) return 503
  return 500
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
