import { createMemoryHistory, createRouter, createWebHistory } from "vue-router"
import { load as loadHome } from "./pages/Home.vue"
import { load as loadTeams } from "./pages/Teams.vue"
import Home from "./pages/Home.vue"
import Teams from "./pages/Teams.vue"

export type PageData = { title: string; marker?: string }
export type Load = (ctx: { params: Record<string, string>; url: string }) => Promise<PageData> | PageData

export function createSiteRouter(ssr: boolean) {
  return createRouter({
    history: ssr ? createMemoryHistory() : createWebHistory(),
    routes: [
      { path: "/", component: Home, meta: { load: loadHome satisfies Load } },
      { path: "/teams/", component: Teams, meta: { load: loadTeams satisfies Load } },
    ],
  })
}

export function httpError(status: number): Error {
  return Object.assign(new Error(String(status)), { status })
}
