import { createHead as createClientHead } from "@unhead/vue/client"
import { createHead as createServerHead } from "@unhead/vue/server"
import { createSSRApp } from "vue"
import App from "./App.vue"
import { createSiteRouter } from "./router"

// Both sides use createSSRApp: on the server it renders to a string, in the
// browser mount() hydrates the server's DOM. createApp() would clear the
// container and paint it again, and a hydration mismatch could never show
// (frontend-migration A1; 233–261 did that).
export function createApp(ssr: boolean) {
  const app = createSSRApp(App)
  // On the server a component that throws must fail the render (the 500 page,
  // server.ts), not log and paint half a page with a 200: Vue only rethrows
  // in development unless told so.
  if (ssr) app.config.throwUnhandledErrorInProduction = true
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
