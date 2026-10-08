import { readFileSync } from "node:fs"
import { expect, test } from "vitest"
import { CSP, STATIC_IMG_CACHE, handle, staticImgPath, staticImgRoot, type Incoming } from "../server"
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
  const out = await handle(incoming("GET", "/no-such/"), { ...base, fetch: api(200, { user: null }), assets: ASSETS })
  expect(out.status).toBe(404)
  expect(out.body).toContain("找不到这个页面")
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
  expect(visitor.body).toContain("找不到这个页面")
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
  expect(out.body).toContain("站点暂时连不上")
  expect(out.headers["cache-control"]).toBe("no-store")
})
