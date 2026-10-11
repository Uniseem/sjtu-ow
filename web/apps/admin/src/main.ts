import "@sjtu-ow/styles/dist/site.css"
import {createHead} from "@unhead/vue/client"
import { createApp } from "vue"
import { isNavigationFailure } from "vue-router"
import { createClient } from "@sjtu-ow/api"
import App from "./App.vue"
import { ADMIN_API } from "./core/api"
import { ADMIN_SESSION, createAdminSession } from "./core/session"
import { createAdminRouter } from "./router"
import { installAdminLinks } from "./core/navigation"

const api=createClient({ onWrite:()=> { void session.refresh().catch(()=>undefined) } })
const session=createAdminSession(api)
const router=createAdminRouter(session)
const app=createApp(App)
app.provide(ADMIN_API,api)
app.provide(ADMIN_SESSION,session)
app.use(router)
app.use(createHead())
document.body.classList.add("b-body")
document.body.dataset.backoffice=""
router.afterEach(to=> {
 document.body.dataset.section=String(to.meta.section || "")
 document.body.dataset.tab=String(to.meta.tab || "")
 document.querySelector<HTMLDetailsElement>(".c-menu[open]")?.removeAttribute("open")
})
function startupError(error: unknown): void {
 console.error("Admin route failed",error)
 const main=document.getElementById("admin-app")
 if (!main || main.childElementCount) return
 const paragraph=document.createElement("p")
 paragraph.className="b-main"
 paragraph.textContent="后台暂时无法打开，请刷新后再试。"
 main.replaceChildren(paragraph)
}
router.onError(startupError)
void router.isReady().then(()=> {app.mount("#admin-app");installAdminLinks(router)}, error=> {
 // An initial guard can intentionally leave for the login document.
 if (!isNavigationFailure(error)) startupError(error)
})
