import { renderSSRHead } from "@unhead/vue/server"
import { renderToString } from "vue/server-renderer"
import { createApp } from "./main"
import { httpError, type Load, type PageData } from "./router"

export type Rendered =
  | { kind: "slash"; location: string }
  | { kind: "login"; next: string }
  | { kind: "page"; status: number; html: string; head: string; state: PageData | null; loggedIn: boolean }

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
  if (!route.matched.length) return page(404, false, null, head)

  const [sessionR, loadR] = await Promise.allSettled([fetchSession(opts), runLoad(route, url, opts)])
  if (sessionR.status === "rejected") return page(503, false, null, head)
  if (loadR.status === "rejected") {
    const status = statusOf(loadR.reason)
    if (status === 401) return { kind: "login", next: pathname + new URL(url, "http://site").search }
    if (status === 403 || status === 404) return page(status, sessionR.value.loggedIn, null, head)
    return page(503, false, null, head)
  }
  app.provide("page-data", loadR.value)
  const html = await renderToString(app)
  const tags = await renderSSRHead(head)
  return { kind: "page", status: 200, html, head: tags.headTags, state: loadR.value, loggedIn: sessionR.value.loggedIn }
}

async function page(status: number, loggedIn: boolean, state: PageData | null, head: ReturnType<typeof createApp>["head"]): Promise<Rendered> {
  const tags = await renderSSRHead(head)
  return { kind: "page", status, html: ERROR_HTML[status] ?? ERROR_HTML[404], head: tags.headTags, state, loggedIn }
}

async function runLoad(route: { meta: { load?: Load }; params: Record<string, string | string[]> }, url: string, opts: RenderOpts): Promise<PageData> {
  const load = opts.load ?? route.meta.load
  if (!load) return { title: "" }
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(route.params)) params[key] = Array.isArray(value) ? value[0] : value
  return load({ params, url })
}

async function fetchSession(opts: RenderOpts): Promise<{ loggedIn: boolean }> {
  let response: Response
  try {
    response = await opts.fetch(opts.apiBase + "/api/session", {
      headers: forward(opts.headers),
      signal: AbortSignal.timeout(5000),
    })
  } catch {
    throw httpError(503)
  }
  if (response.status === 401) return { loggedIn: false }
  if (!response.ok) throw httpError(503)
  const body = (await response.json()) as { user?: unknown }
  return { loggedIn: body.user != null }
}

function forward(headers: { get(name: string): string | null }): Headers {
  const out = new Headers()
  for (const name of ["cookie", "x-real-ip", "x-request-id"]) {
    const value = headers.get(name)
    if (value) out.set(name, value)
  }
  return out
}
