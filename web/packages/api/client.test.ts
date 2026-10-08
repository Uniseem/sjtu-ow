import { expect, test } from "vitest"
import { ApiError, createClient } from "./src/client"

function fake(status: number, body: unknown, seen: { headers: Headers; url: string }) {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    seen.url = String(input)
    seen.headers = new Headers(init?.headers)
    return new Response(body === undefined ? "" : JSON.stringify(body), { status })
  }) as typeof fetch
}

test("a write carries an idempotency key and a given key is reused", async () => {
  const seen = { headers: new Headers(), url: "" }
  const request = createClient({ fetch: fake(200, {}, seen), newKey: () => "generated" })
  await request("POST", "/api/teams/{id}/applications", { params: { id: "12" }, body: { note: "a" } })
  expect(seen.headers.get("Idempotency-Key")).toBe("generated")
  expect(seen.headers.get("content-type")).toBe("application/json")
  expect(seen.url).toBe("/api/teams/12/applications")
  await request("POST", "/api/x", { key: "same", body: {} })
  expect(seen.headers.get("Idempotency-Key")).toBe("same")
})

test("a read does not send an idempotency key", async () => {
  const seen = { headers: new Headers(), url: "" }
  const request = createClient({ fetch: fake(200, { title: "x" }, seen), newKey: () => "nope" })
  const data = await request<{ title: string }>("GET", "/api/session")
  expect(data.title).toBe("x")
  expect(seen.headers.get("Idempotency-Key")).toBeNull()
})

test("401 sends the visitor to the login page", async () => {
  const seen = { headers: new Headers(), url: "" }
  let gone = ""
  const request = createClient({
    fetch: fake(401, { error: { code: "unauthorized", message: "no" } }, seen),
    location: () => "/teams/12/",
    assign: (url) => {
      gone = url
    },
  })
  await expect(request("GET", "/api/session")).rejects.toBeInstanceOf(ApiError)
  expect(gone).toBe("/accounts/login/?next=" + encodeURIComponent("/teams/12/"))
})

test("letters in a response open the confirm page", async () => {
  const seen = { headers: new Headers(), url: "" }
  let gone = ""
  const request = createClient({
    fetch: fake(200, { letters: { batch: "abc", count: 1 } }, seen),
    location: () => "/teams/12/",
    assign: (url) => {
      gone = url
    },
    onWrite: () => {
      throw new Error("写成功的通知不该在跳转前漏掉，但本测试只看地址")
    },
  })
  // onWrite throws after assign; the address must already be the confirm page.
  await expect(request("POST", "/api/x", { body: {} })).rejects.toThrow("写成功")
  expect(gone).toBe("/letters/abc/?back=" + encodeURIComponent("/teams/12/"))
})

test("an admin page confirms letters inside the admin", async () => {
  const seen = { headers: new Headers(), url: "" }
  let gone = ""
  const request = createClient({
    fetch: fake(200, { ok: true, letters: { batch: "abc" } }, seen),
    location: () => "/admin/articles/3/",
    assign: (url) => {
      gone = url
    },
  })
  await request("POST", "/api/admin/articles/3", { body: {} })
  expect(gone).toBe("/admin/letters/abc/?back=" + encodeURIComponent("/admin/articles/3/"))
})

test("a 422 keeps the field errors", async () => {
  const seen = { headers: new Headers(), url: "" }
  const request = createClient({
    fetch: fake(422, { error: { code: "invalid", message: "没通过" }, fields: { name: ["太短"] } }, seen),
    assign: () => {
      throw new Error("不该跳转")
    },
  })
  try {
    await request("POST", "/api/x", { body: {} })
    expect.fail("应该抛出")
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError)
    const api = err as ApiError
    expect(api.status).toBe(422)
    expect(api.fields).toEqual({ name: ["太短"] })
  }
})
