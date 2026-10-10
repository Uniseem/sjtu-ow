import { createMemoryHistory, createRouter, createWebHistory } from "vue-router"
import { load as loadHome } from "./pages/Home.vue"
import { load as loadTeams } from "./pages/Teams.vue"
import Home from "./pages/Home.vue"
import Teams from "./pages/Teams.vue"
import { loadStyleguide } from "./specimen"
import { PAGES } from "./routes"
import type { Requester } from "@sjtu-ow/api"
import type { Viewer } from "./viewer"

export type SampleClock = {
  dayDate: string
  dayMd: string
  dayTime: string
  dayWeekday: string
  dayMonth: string
  dayDom: string
  closeDate: string
  closeMd: string
  closeTime: string
  closeWeekday: string
  pastDate: string
  pastMd: string
  pastTime: string
}

export type PageData = { title: string; marker?: string; clock?: SampleClock; [key: string]: any }
// What a page's load() gets (frontend-migration A2). `api` is the one way to
// Go: pass it to the generated functions (getApiTeamsId(ctx.api, id)). Errors
// are not caught here: an ApiError's status decides the response (401 → login,
// 403/404 → error page) in entry-server, and the navigation in entry-client.
// `viewer()` is who is looking: the same /api/session call the page is
// painted with (no second request), for a load that answers differently per
// person (/submit/ sends a contributor on to the editor).
// `fetch` and `apiBase` are only for the 260 pages until they are rewritten.
export type LoadCtx = {
  params: Record<string, string>
  query: Record<string, string>
  url: string
  api: Requester
  viewer: () => Promise<Viewer>
  fetch?: typeof fetch
  apiBase?: string
}
export type Load = (ctx: LoadCtx) => Promise<PageData> | PageData

// Route meta: `load` as above; `auth: "member"` for pages that need a login —
// SSR sends a visitor to the login page before painting (as Django's
// login_required did); Go stays the real gate.
declare module "vue-router" {
  interface RouteMeta {
    load?: Load
    auth?: "member"
    guest?: boolean
    admin?: boolean
  }
}

export function createSiteRouter(ssr: boolean) {
  return createRouter({
    history: ssr ? createMemoryHistory() : createWebHistory(),
    routes: [
      { path: "/", component: Home, meta: { load: loadHome satisfies Load } },
      { path: "/teams/", component: Teams, meta: { load: loadTeams satisfies Load } },
      { path: "/_styleguide/", component: () => import("./pages/Styleguide.vue"), meta: { load: loadStyleguide satisfies Load } },
      ...PAGES,
    ],
  })
}

export function httpError(status: number): Error {
  return Object.assign(new Error(String(status)), { status })
}

/** The status of an error thrown by a load (ApiError or httpError); undefined for anything else. */
export function statusOf(err: unknown): number | undefined {
  return typeof err === "object" && err !== null && "status" in err ? Number((err as { status: number }).status) : undefined
}

/** Plain string params and query from a matched route, first value of repeated ones. */
export function flat(values: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(values)) {
    const first = Array.isArray(value) ? value[0] : value
    if (typeof first === "string") out[key] = first
  }
  return out
}
