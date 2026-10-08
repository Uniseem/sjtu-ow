import { readFileSync } from "node:fs"
import { expect, test } from "vitest"
import { handle, type Incoming } from "../server"
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

test("an unknown path is a 404 page", async () => {
  const out = await handle(incoming("GET", "/no-such/"), { ...base, fetch: api(200, { user: null }) })
  expect(out.status).toBe(404)
  expect(out.body).toContain("找不到这个页面")
})

test("the shell has no executable inline script and escapes state", async () => {
  const out = await handle(incoming("GET", "/"), { ...base, fetch: api(200, { user: null }) })
  expect(out.status).toBe(200)
  expect(out.headers["cache-control"]).toBe("no-cache")
  expect(out.headers.vary).toBe("Cookie")
  expect(out.body).not.toContain('style="')
  expect(out.body.match(/charset/g)).toHaveLength(1)
  expect(out.body.indexOf('src="/theme.js"')).toBeLessThan(out.body.indexOf("charset"))
  expect(out.body).toContain("SJTU-OW")
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
    fetch: api(200, { user: { id: 1 } }, seen),
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
    fetch: api(200, { user: { id: 1 } }),
    load: () => {
      throw httpError(401)
    },
  })
  expect(out.status).toBe(302)
  expect(out.headers.location).toBe("/accounts/login/?next=" + encodeURIComponent("/teams/"))
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
