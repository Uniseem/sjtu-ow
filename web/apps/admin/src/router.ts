import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router"
import type { AdminSession } from "./core/session"
import { contentRoutes } from "./pages/content/routes"
import { activitiesRoutes } from "./pages/activities/routes"
import { mailpreviewRoutes } from "./pages/mailpreview/routes"
import { managementRoutes } from "./pages/management/routes"

const letterRoutes: RouteRecordRaw[] = [
  { path: "/admin/letters/", component: () => import("./pages/letters/Letters.vue") },
  { path: "/admin/letters/:batch([A-Za-z0-9_-]{1,128})/", component: () => import("./pages/letters/Letters.vue") },
  { path: "/admin/letters/:batch([A-Za-z0-9_-]{1,128})/:id(\\d{1,18})/", component: () => import("./pages/letters/Preview.vue") },
]
export const ADMIN_ROUTES:RouteRecordRaw[]=[...contentRoutes,...activitiesRoutes,...managementRoutes,...mailpreviewRoutes,...letterRoutes,
 {path:"/admin/settings/prerender/",redirect:"/admin/settings/"},
 {path:"/admin/:pathMatch(.*)*",component:()=>import("./pages/NotFound.vue")}
]
export function createAdminRouter(session: AdminSession) {
  const router = createRouter({ history:createWebHistory(), routes:ADMIN_ROUTES, scrollBehavior(to,from,saved) {
    if (saved) return saved
    if (to.hash) return { el:to.hash }
    return to.path === from.path ? undefined : { top:0 }
  } })
  router.beforeEach(async to => {
    if (!session.ready.value) await session.refresh()
    if (!session.user.value) { window.location.assign("/accounts/login/?next="+encodeURIComponent(to.fullPath));return false }
    if (!session.can("admin.enter")) return to.path === "/admin/forbidden/" ? true : "/admin/forbidden/"
    return true
  })
  return router
}
