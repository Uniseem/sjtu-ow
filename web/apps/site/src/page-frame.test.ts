import { describe, expect, it } from "vitest"
import { createSSRApp, defineComponent, h, inject, reactive } from "vue"
import { renderToString } from "vue/server-renderer"
import PageFrame from "./components/PageFrame.vue"
import type { PageData } from "./router"

describe("page payload scope", () => {
  it("keeps API payloads cloneable when supplied by the reactive client state", async () => {
    const state = reactive<PageData>({ title: "详情", page: { id: 7, roster: [{ nickname: "队员" }] } })
    const Child = defineComponent({ setup() {
      const payload = inject<{ page: { id: number; roster: { nickname: string }[] } }>("page-data")!
      const local = structuredClone(payload.page)
      local.roster[0].nickname = "本地编辑"
      return () => h("main", `${local.id}:${local.roster[0].nickname}`)
    } })
    const app = createSSRApp({ render: () => h(PageFrame, null, { default: () => h(Child) }) })
    app.provide("page-data", state)
    expect(await renderToString(app)).toContain("7:本地编辑")
    expect(state.page).toEqual({ id: 7, roster: [{ nickname: "队员" }] })
  })

  it("does not expose a partially replaced next-route payload to a mounted page", async () => {
    const state = reactive<PageData>({ title: "旧详情", page: { id: 7 } })
    const Child = defineComponent({ setup() {
      const payload = inject<{ page: { id: number } }>("page-data")!
      delete state.page
      state.title = "首页"
      state.home = { agenda: [] }
      return () => h("main", String(payload.page.id))
    } })
    const app = createSSRApp({ render: () => h(PageFrame, null, { default: () => h(Child) }) })
    app.provide("page-data", state)
    expect(await renderToString(app)).toContain("7")
    expect(state.page).toBeUndefined()
  })
})
