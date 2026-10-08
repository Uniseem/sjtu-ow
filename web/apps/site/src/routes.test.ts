import { expect, test } from "vitest"
import { createSiteRouter } from "./router"
import { NAV } from "./sections"

function match(url: string) {
  const router = createSiteRouter(true)
  return router.resolve(url)
}

test("the navigation targets are pages", () => {
  for (const item of NAV) {
    expect(match(item.to).matched.length, item.to).toBeGreaterThan(0)
  }
})

test("a numeric id matches and anything else does not", () => {
  expect(match("/teams/12/").matched.length).toBeGreaterThan(0)
  expect(match("/teams/new/").matched.length).toBeGreaterThan(0)
  expect(match("/teams/abc/").matched.length).toBe(0)
  expect(match("/teams/123456789012345678/").matched.length).toBeGreaterThan(0)
  expect(match("/teams/1234567890123456789/").matched.length).toBe(0)
})

test("the listed front pages resolve", () => {
  for (const url of [
    "/news/",
    "/about/",
    "/terms/",
    "/privacy/",
    "/search/",
    "/submit/",
    "/letters/",
    "/letters/abc/",
    "/letters/abc/4/",
    "/me/",
    "/me/teams/",
    "/me/registrations/",
    "/me/scrims/",
    "/members/",
    "/members/3/",
    "/tournaments/",
    "/tournaments/8/signup/",
    "/registrations/2/",
    "/scrims/",
    "/scrims/5/",
    "/accounts/login/",
    "/accounts/signup/",
    "/accounts/password/reset/confirm/",
    "/unsubscribe/tok/",
    "/_styleguide/emails/welcome/",
  ]) {
    expect(match(url).matched.length, url).toBeGreaterThan(0)
  }
})
