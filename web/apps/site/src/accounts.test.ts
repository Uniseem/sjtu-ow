import { expect, test } from "vitest"
import { handle } from "../server"
import { safeNext } from "@sjtu-ow/shared/navigation"

const user = { id: 7, nickname: "成员", email: "member@example.com", admin: false, superuser: false, caps: [], email_verified: true, is_sjtu: true }
async function page(url: string, loggedIn = false) {
  return handle({ method: "GET", url, headers: { get: () => null } }, {
    apiBase: "http://api.test",
    fetch: async () => new Response(JSON.stringify({ user: loggedIn ? user : null }), { status: 200 }),
  })
}
test("next allows local return addresses and rejects external, encoded and malformed targets", () => {
  expect(safeNext("/scrims/8/?role=support#signup")).toBe("/scrims/8/?role=support#signup")
  for (const target of ["https://evil.test/", "//evil.test/", "/\\evil.test/", "/%5cevil.test/", "/%2fevil.test/", "/%", "/\nevil.test/", "https:evil.test", null]) {
    expect(safeNext(target, "/me/")).toBe("/me/")
  }
})
test("authenticated account entrances return a safe next with an actual 302", async () => {
  for (const url of ["/accounts/login/", "/accounts/signup/"]) {
    const next = await page(url + "?next=%2Fscrims%2F8%2F", true)
    expect(next.status).toBe(302)
    expect(next.headers.location).toBe("/scrims/8/")
    const external = await page(url + "?next=https%3A%2F%2Fevil.test", true)
    expect(external.headers.location).toBe("/")
  }
})
test("unused login-code and password-set entrances redirect instead of painting placeholders", async () => {
  const code = await page("/accounts/login/code/confirm/")
  expect([code.status, code.headers.location]).toEqual([302, "/accounts/login/"])
  const password = await page("/accounts/password/set/", true)
  expect([password.status, password.headers.location]).toEqual([301, "/me/security/"])
})
test("protected account pages send visitors to login before painting a form", async () => {
  for (const url of ["/accounts/reauthenticate/", "/accounts/password/change/"]) {
    const result = await page(url)
    expect(result.status).toBe(302)
    expect(result.headers.location).toBe("/accounts/login/?next=" + encodeURIComponent(url))
  }
})
test("confirmation carries its email in SSR and missing context goes to login", async () => {
  const missing = await page("/accounts/confirm-email/")
  expect([missing.status, missing.headers.location]).toEqual([302, "/accounts/login/"])
  const result = await page("/accounts/confirm-email/?email=new%40example.com&next=%2Fme%2F")
  expect(result.status).toBe(200)
  expect(result.body).toContain('href="mailto:new@example.com"')
  expect(result.body).toContain('autocomplete="one-time-code"')
  expect(result.body).toContain('name="action" value="resend"')
})
test("registration consents stay separate and affiliation has no default", async () => {
  const result = await page("/accounts/signup/")
  expect(result.body).toContain('name="agreed_terms"')
  expect(result.body).toContain('name="agreed_cross_border"')
  expect(result.body).not.toMatch(/type="radio"[^>]*checked/)
  expect(result.body).toContain('rel="noopener"')
})
