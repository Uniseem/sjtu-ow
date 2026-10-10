import { readFileSync } from "node:fs"
import { expect, test } from "vitest"
import { CSP, STATIC_IMG_CACHE, handle, staticImgPath, staticImgRoot, type Incoming } from "../server"
import { ApiError } from "@sjtu-ow/api"
import { httpError } from "./router"

function incoming(method: string, url: string, headers: Record<string, string> = {}): Incoming {
  return { method, url, headers: { get: (name) => headers[name.toLowerCase()] ?? null } }
}

function api(status: number, body: unknown, seen?: { cookie: string | null }): typeof fetch {
  return async (_input, init) => {
    const headers = new Headers(init?.headers)
    if (seen) seen.cookie = headers.get("cookie")
    return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })
  }
}

const base = { apiBase: "http://api.test" }
const ASSETS = { entry: "/assets/entry-x.js", css: ["/assets/entry-x.css"], preloads: [] }

test("the content security policy is the one in section 6.9", () => {
  expect(CSP).toBe(
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
  )
  expect(CSP).not.toContain("unsafe-")
})

test("static images stay inside static/img and are cached for a day", () => {
  const root = staticImgRoot()
  expect(root).not.toBe("")
  const file = staticImgPath("/static/img/placeholders/cover-07.svg", root)
  expect(file?.endsWith("/placeholders/cover-07.svg")).toBe(true)
  expect(staticImgPath("/static/img/placeholders/..%2f..%2f..%2fweb/package.json", root)).toBeNull()
  expect(staticImgPath("/static/img/no-such.svg", root)).toBeNull()
  expect(STATIC_IMG_CACHE).toBe("public, max-age=86400")
})

test("only GET and HEAD are accepted", async () => {
  const out = await handle(incoming("POST", "/"), { ...base, fetch: api(200, { user: null }) })
  expect(out.status).toBe(405)
  expect(out.headers.allow).toBe("GET, HEAD")
})

test("a missing trailing slash redirects when the slashed path exists", async () => {
  const out = await handle(incoming("GET", "/teams?x=1"), { ...base, fetch: api(200, { user: null }) })
  expect(out.status).toBe(301)
  expect(out.headers.location).toBe("/teams/?x=1")
})

test("a registered page shows its title and a non-numeric id is a 404", async () => {
  const news = await handle(incoming("GET", "/news/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(news.status).toBe(200)
  expect(news.body.replace(/<!--.*?-->/g, "")).toContain(">资讯</h1>")
  const bare = await handle(incoming("GET", "/news"), { ...base, fetch: api(200, { user: null }) })
  expect(bare.status).toBe(301)
  expect(bare.headers.location).toBe("/news/")
  const bad = await handle(incoming("GET", "/teams/abc/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(bad.status).toBe(404)
})

test("an unknown path is a 404 page without any script", async () => {
  // Two segments: one segment is an editor's page (/<slug>/) and asks Go first (content.test.ts).
  const out = await handle(incoming("GET", "/no/such/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(out.status).toBe(404)
  expect(out.body).toContain("页面不存在")
  // 错误页不是 App 画出来的，不该有数据块和入口脚本
  expect(out.body).not.toContain('id="ow-state"')
  expect(out.body).not.toContain("entry-x.js")
  expect(out.body).not.toContain("/src/entry-client.ts")
  expect(out.body).not.toContain("页面脚本没有加载成功")
})

test("the shell has no executable inline script and escapes state", async () => {
  const out = await handle(incoming("GET", "/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(out.status).toBe(200)
  expect(out.headers["cache-control"]).toBe("no-cache")
  expect(out.headers.vary).toBe("Cookie")
  expect(out.body).not.toContain('style="')
  expect(out.body.match(/charset/g)).toHaveLength(1)
  expect(out.body.indexOf('src="/theme.js"')).toBeLessThan(out.body.indexOf("charset"))
  expect(out.body).toContain('src="/assets/entry-x.js"')
  expect(out.body).toContain('rel="stylesheet" href="/assets/entry-x.css"')
  expect(out.body).not.toContain("/src/entry-client.ts")
  expect(out.body).toContain('class="flex min-h-screen flex-col"')
  expect(out.body).toContain("\\u003c")
  expect(out.body).not.toContain('id="ow-state"><')
  expect(out.body).toContain("页面脚本没有加载成功")
  const source = readFileSync(new URL("../server.ts", import.meta.url), "utf8")
  expect(source.split("\n").length).toBeLessThanOrEqual(300)
  expect(source).not.toContain("<meta charset")
})

test("a logged-in session is not cached", async () => {
  const seen = { cookie: null as string | null }
  const out = await handle(incoming("GET", "/", { cookie: "ow_session=abc" }), {
    ...base,
    fetch: api(200, { user: { nickname: "夜蛾", admin: false } }, seen),
  })
  expect(out.status).toBe(200)
  expect(out.headers["cache-control"]).toBe("private, no-store")
  expect(seen.cookie).toBe("ow_session=abc")
})

test("HEAD has the same status and an empty body", async () => {
  const out = await handle(incoming("HEAD", "/"), { ...base, fetch: api(200, { user: null }) })
  expect(out.status).toBe(200)
  expect(out.body).toBe("")
})

test("a 401 from the loader redirects to login", async () => {
  const out = await handle(incoming("GET", "/teams/"), {
    ...base,
    fetch: api(200, { user: { nickname: "夜蛾", admin: false } }),
    load: () => {
      throw httpError(401)
    },
  })
  expect(out.status).toBe(302)
  expect(out.headers.location).toBe("/accounts/login/?next=" + encodeURIComponent("/teams/"))
})

test("the style guide is a 404 unless the viewer is staff", async () => {
  const visitor = await handle(incoming("GET", "/_styleguide/"), {
    ...base,
    fetch: api(200, { user: null }),
    assets: ASSETS,
  })
  expect(visitor.status).toBe(404)
  expect(visitor.body).toContain("页面不存在")
  expect(visitor.body).not.toContain("设计体系样张")
  const member = await handle(incoming("GET", "/_styleguide/"), {
    ...base,
    fetch: api(200, { user: { nickname: "夜航", admin: false } }),
    assets: ASSETS,
  })
  expect(member.status).toBe(404)
  expect(member.body).not.toContain("为战队报名")
  const emails = await handle(incoming("GET", "/_styleguide/emails/"), {
    ...base,
    fetch: api(200, { user: null }),
    assets: ASSETS,
  })
  expect(emails.status).toBe(404)
  const staff = await handle(incoming("GET", "/_styleguide/"), {
    ...base,
    fetch: api(200, { user: { nickname: "夜蛾", admin: true } }),
    assets: ASSETS,
  })
  expect(staff.status).toBe(200)
  const html = staff.body.replace(/<!--.*?-->/g, "")
  expect(html).toContain('<main id="main"')
  expect(html).toContain(">设计体系样张</h1>")
  expect(html).toContain("为战队报名")
  expect(html).toContain("这个队名已经有人用了。")
  expect(html).toContain("评论已删除。")
  expect(html).toContain("/static/img/placeholders/cover-07.svg")
  expect(html).toContain("#9B3A33")
  expect(html).not.toContain('style="')
  expect((html.match(/is-taken/g) ?? []).length).toBe(36)
})

test("an unreachable API is a 503 page", async () => {
  const out = await handle(incoming("GET", "/"), {
    ...base,
    fetch: async () => {
      throw new Error("connect")
    },
  })
  expect(out.status).toBe(503)
  expect(out.body).toContain("网站维护中")
  expect(out.headers["cache-control"]).toBe("no-store")
})

// ---- 262: login gate, error mapping, the whole session, the loader context ----

test("a page that needs a login sends a visitor to the login page and lets a member in", async () => {
  const visitor = await handle(incoming("GET", "/me/teams/?x=1"), { ...base, fetch: api(200, { user: null }) })
  expect(visitor.status).toBe(302)
  expect(visitor.headers.location).toBe("/accounts/login/?next=" + encodeURIComponent("/me/teams/?x=1"))
  const member = await handle(incoming("GET", "/me/teams/"), {
    ...base,
    fetch: api(200, { user: { id: 3, nickname: "夜蛾", admin: false, superuser: false, caps: [] } }),
    assets: ASSETS,
  })
  expect(member.status).toBe(200)
  // A public page stays public.
  const teams = await handle(incoming("GET", "/teams/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(teams.status).toBe(200)
})

test("a loader's ApiError decides the status: 404, 403, 429 are pages, a dead API is 503", async () => {
  const at = (load: () => never) =>
    handle(incoming("GET", "/teams/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS, load })
  expect((await at(() => { throw new ApiError(404, "not_found", "没有") })).status).toBe(404)
  expect((await at(() => { throw new ApiError(403, "forbidden", "不行") })).status).toBe(403)
  expect((await at(() => { throw new ApiError(429, "rate_limited", "太快") })).status).toBe(429)
  expect((await at(() => { throw new ApiError(0, "network", "连不上") })).status).toBe(503)
  const missing = await at(() => { throw new ApiError(404, "not_found", "没有") })
  expect(missing.body).not.toContain('id="ow-state"')
})

test("the whole session goes into the page state, caps and all", async () => {
  const user = { id: 9, nickname: "站长", email: "a@b.c", admin: true, superuser: false, caps: ["scrims.manage"], email_verified: true, is_sjtu: true }
  const out = await handle(incoming("GET", "/"), { ...base, fetch: api(200, { user }), assets: ASSETS })
  const state = JSON.parse(out.body.match(/id="ow-state">([\s\S]*?)<\/script>/)![1])
  expect(state.viewer.user).toEqual(user)
})

test("a loader gets the API client, the params and the query", async () => {
  const seen: { url?: string; params?: unknown; query?: unknown; got?: unknown } = {}
  const out = await handle(incoming("GET", "/teams/12/?tab=x"), {
    apiBase: "http://api.test",
    fetch: (async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith("/api/session")) return new Response(JSON.stringify({ user: null }))
      seen.url = url
      return new Response(JSON.stringify({ team: { name: "夜航" } }))
    }) as typeof fetch,
    assets: ASSETS,
    load: async (ctx) => {
      seen.params = ctx.params
      seen.query = ctx.query
      seen.got = await ctx.api("GET", "/api/teams/{id}", { params: { id: ctx.params.id } })
      return { title: "夜航" }
    },
  })
  expect(out.status).toBe(200)
  expect(seen.params).toEqual({ id: "12" })
  expect(seen.query).toEqual({ tab: "x" })
  expect(seen.url).toBe("http://api.test/api/teams/12")
  expect(seen.got).toEqual({ team: { name: "夜航" } })
})

// ---- 263: the error pages are the old site's (templates/errors) ----

test("an error page is its own document: error.css, the old wording, no script", async () => {
  const out = await handle(incoming("GET", "/no/such/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(out.status).toBe(404)
  expect(out.headers["cache-control"]).toBe("no-store")
  expect(out.body).toContain("<title>页面不存在 · SJTU-OW</title>")
  expect(out.body).toContain('<link rel="stylesheet" href="/static/css/error.css">')
  expect(out.body).toContain('<p class="code" aria-hidden="true">404</p>')
  expect(out.body).toContain("内容可能已经下线，或者网址有误。")
  expect(out.body).toContain("学生社团自办网站 · 不是上海交通大学官方网站")
  expect(out.body).not.toContain("<script")
  expect(out.body).not.toContain("/assets/entry-x.css")
  expect(out.body).not.toContain('style="')
})

test("each status has the old page: 403, 429, Go's 500 with the request id, Go down is maintenance", async () => {
  const at = (load: () => never, headers: Record<string, string> = {}) =>
    handle(incoming("GET", "/teams/", headers), { ...base, fetch: api(200, { user: null }), assets: ASSETS, load })
  const forbidden = await at(() => { throw new ApiError(403, "forbidden", "x") })
  expect(forbidden.body).toContain("<h1>没有权限</h1>")
  expect(forbidden.body).toContain('href="/accounts/login/"')
  expect((await at(() => { throw new ApiError(429, "rate_limited", "x") })).body).toContain("<h1>操作太频繁</h1>")
  const broken = await at(() => { throw new ApiError(500, "internal", "x") }, { "x-request-id": "req-<7>" })
  expect(broken.status).toBe(500)
  expect(broken.body).toContain("请求编号：req-&lt;7&gt;")
  const down = await at(() => { throw new ApiError(502, "", "") })
  expect(down.status).toBe(503)
  expect(down.body).toContain("<h1>网站维护中</h1>")
})

test("a bug in a load is the 500 page", async () => {
  const out = await handle(incoming("GET", "/teams/"), {
    ...base,
    fetch: api(200, { user: null }),
    assets: ASSETS,
    load: () => {
      throw new TypeError("a bug")
    },
  })
  expect(out.status).toBe(500)
  expect(out.body).toContain("<h1>服务器出错了</h1>")
  expect(out.body).toContain("当前没有请求编号。")
})

test("a component that throws while rendering is the 500 page, not a hanging request", async () => {
  const out = await handle(incoming("GET", "/unsubscribe/tok/"), {
    ...base,
    fetch: api(200, { user: null }),
    assets: ASSETS,
    // Page.vue reads the title in setup: the throw happens inside renderToString.
    load: () =>
      ({
        get title(): string {
          throw new TypeError("a bug in a component")
        },
      }) as never,
  })
  expect(out.status).toBe(500)
  expect(out.body).toContain("<h1>服务器出错了</h1>")
})

test("the server app rethrows component errors in production as well", async () => {
  const { createApp } = await import("./main")
  expect(createApp(true).app.config.throwUnhandledErrorInProduction).toBe(true)
})
