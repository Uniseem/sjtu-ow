import { createHead as createClientHead } from "@unhead/vue/client"
import { createHead as createServerHead } from "@unhead/vue/server"
import { createApp as createCSR, createSSRApp, type App as VueApp } from "vue"
import App from "./App.vue"
import { createSiteRouter } from "./router"

export function createApp(ssr: boolean) {
  const app: VueApp = ssr ? createSSRApp(App) : createCSR(App)
  const router = createSiteRouter(ssr)
  const head = ssr ? createServerHead() : createClientHead()
  head.push({
    meta: [
      { charset: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      // The browser bar takes the masthead's colour; theme.js repaints both.
      { name: "theme-color", content: "#ffffff", media: "(prefers-color-scheme: light)" },
      { name: "theme-color", content: "#171a20", media: "(prefers-color-scheme: dark)" },
    ],
  })
  app.use(router)
  app.use(head)
  return { app, router, head }
}
