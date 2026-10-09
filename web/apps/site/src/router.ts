import { createMemoryHistory, createRouter, createWebHistory } from "vue-router"
import { load as loadHome } from "./pages/Home.vue"
import { load as loadTeams } from "./pages/Teams.vue"
import Home from "./pages/Home.vue"
import Teams from "./pages/Teams.vue"
import { loadStyleguide } from "./specimen"
import { PAGES } from "./routes"

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
export type LoadCtx = { params: Record<string, string>; url: string; fetch?: typeof fetch; apiBase?: string }
export type Load = (ctx: LoadCtx) => Promise<PageData> | PageData

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
