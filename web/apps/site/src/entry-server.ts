import { renderSSRHead } from "@unhead/vue/server"
import { renderToString } from "vue/server-renderer"
import { createApp } from "./main"
import { httpError, type Load, type PageData } from "./router"
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

const ERROR_HTML: Record<number, string> = {
  403: "<main><h1>没有权限看这个页面</h1></main>",
  404: "<main><h1>找不到这个页面</h1></main>",
  503: "<main><h1>站点暂时连不上</h1></main>",
}

const VISITOR: Viewer = { user: null }

function statusOf(err: unknown): number | undefined {
  return typeof err === "object" && err !== null && "status" in err ? Number((err as { status: number }).status) : undefined
}

function pathnameOf(url: string): string {
  return new URL(url, "http://site").pathname
}

export async function render(url: string, opts: RenderOpts): Promise<Rendered> {
  const { app, router, head } = createApp(true)
  const pathname = pathnameOf(url)
  if (pathname !== "/" && !pathname.endsWith("/")) {
    const next = pathname + "/"
    if (router.resolve(next).matched.length > 0) {
      const search = new URL(url, "http://site").search
      return { kind: "slash", location: next + search }
    }
  }
  await router.push(url)
  await router.isReady()
  const route = router.currentRoute.value
  if (!route.matched.length) return page(404, VISITOR, head)

  const [sessionR, loadR] = await Promise.allSettled([fetchSession(opts), runLoad(route, url, opts)])
  if (sessionR.status === "rejected") return page(503, VISITOR, head)
  const viewer = sessionR.value
  if (loadR.status === "rejected") {
    const status = statusOf(loadR.reason)
    if (status === 401) return { kind: "login", next: pathname + new URL(url, "http://site").search }
    if (status === 403 || status === 404) return page(status, viewer, head)
    return page(503, VISITOR, head)
  }
  if (styleguideHidden(pathname, viewer.user?.admin === true)) return page(404, viewer, head)
  app.provide(VIEWER, viewer)
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

async function runLoad(route: { meta: { load?: Load }; params: Record<string, string | string[]> }, url: string, opts: RenderOpts): Promise<PageData> {
  const load = opts.load ?? route.meta.load
  if (!load) return { title: "" }
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(route.params)) params[key] = Array.isArray(value) ? value[0] : value
  return load({ params, url })
}

async function fetchSession(opts: RenderOpts): Promise<Viewer> {
  let response: Response
  try {
    response = await opts.fetch(opts.apiBase + "/api/session", {
      headers: forward(opts.headers),
      signal: AbortSignal.timeout(5000),
    })
  } catch {
    throw httpError(503)
  }
  if (response.status === 401) return VISITOR
  if (!response.ok) throw httpError(503)
  const body = (await response.json()) as { user?: { nickname?: unknown; admin?: unknown } | null }
  const user = body.user
  if (user === null || user === undefined || typeof user.nickname !== "string") return VISITOR
  return { user: { nickname: user.nickname, admin: user.admin === true } }
}

function forward(headers: { get(name: string): string | null }): Headers {
  const out = new Headers()
  for (const name of ["cookie", "x-real-ip", "x-request-id"]) {
    const value = headers.get(name)
    if (value) out.set(name, value)
  }
  return out
}
