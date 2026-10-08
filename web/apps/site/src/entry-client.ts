import { reactive } from "vue"
import { createApp } from "./main"
import type { Load, PageData } from "./router"

const raw = document.getElementById("ow-state")?.textContent ?? "null"
const state = JSON.parse(raw) as { data: PageData | null }
const page = reactive<PageData>(state.data ?? { title: "" })
const { app, router } = createApp(false)
app.provide("page-data", page)
router.isReady().then(() => {
  app.mount("#app")
  document.documentElement.classList.add("js-ready")
})

router.beforeResolve(async (to, from) => {
  if (!from.matched.length) return
  const load = to.meta.load as Load | undefined
  if (!load) return
  const params: Record<string, string> = {}
  for (const [key, value] of Object.entries(to.params)) params[key] = Array.isArray(value) ? value[0] : value
  Object.assign(page, await load({ params, url: to.fullPath }))
})
