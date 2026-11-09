import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
const { base, output, sessions } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const require = createRequire(join(process.env.POLISH_PLAYWRIGHT || join(process.argv[3], "web"), "package.json"))
const { chromium, webkit } = require("playwright")
const engine = process.env.UI_ENGINE || "chromium"
const browser = await (engine === "webkit" ? webkit.launch({ headless: true }) : chromium.launch({ executablePath: "/usr/bin/chromium", headless: true }))
const out = join(output, engine)
mkdirSync(out, { recursive: true })
const results = []
const errors = []
function observe(page) {
  page.on("pageerror", error => errors.push(String(error)))
  page.on("console", message => { if (message.type() === "error" || /hydration|mismatch/i.test(message.text())) errors.push(message.text()) })
}
try {
  const gate = await browser.newContext()
  assert.equal((await gate.request.get(base + "/_styleguide/interactions/")).status(), 404)
  await gate.addCookies([{ name: "ow_session", value: sessions.member, url: base }])
  const member = await (await gate.request.get(base + "/api/session")).json()
  assert(member.user)
  const memberStatus = member.user.admin ? 200 : 404
  assert.equal((await gate.request.get(base + "/_styleguide/interactions/")).status(), memberStatus)
  console.log(`PASS STYLEGUIDE-GATE ${engine}: visitor 404; member admin=${member.user.admin} status=${memberStatus}`)
  await gate.close()
  for (const width of [375, 1280]) for (const theme of ["light", "dark"]) for (const reduced of [false, true]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, hasTouch: width < 1000, reducedMotion: reduced ? "reduce" : "no-preference" })
    await context.addInitScript(choice => localStorage.setItem("ow-theme", choice), theme)
    const page = await context.newPage()
    observe(page)
    assert.equal((await page.goto(base + "/news/")).status(), 200)
    await page.evaluate(() => document.fonts.ready)
    const card = page.locator(".c-media").first()
    await card.hover()
    await page.waitForTimeout(340)
    const state = await card.locator(".c-media__pic img").evaluate(node => ({ scale: parseFloat(getComputedStyle(node).getPropertyValue("scale")) || 1, animated: getComputedStyle(node).animationName, hover: matchMedia("(hover: hover) and (pointer: fine)").matches, loaded: node.complete && node.naturalWidth > 0 }))
    const expected = !reduced && state.hover ? 1.03 : 1
    assert(Math.abs(state.scale - expected) < 0.001, JSON.stringify({ width, theme, reduced, state, expected }))
    assert(state.loaded)
    if (reduced) assert.equal(state.animated, "none")
    const file = `${width}-${theme}-${reduced ? "reduced" : "normal"}-card.png`
    if (engine !== "webkit") await card.screenshot({ path: join(out, file) })
    results.push({ width, theme, reduced, ...state, file: engine === "webkit" ? null : file })
    console.log(`PASS IMAGE ${engine} ${width} ${theme} reduced=${reduced}: ${JSON.stringify(state)}`)
    const button = page.locator(".c-pagehead__actions .c-btn").first()
    await button.hover()
    await page.mouse.down()
    await page.waitForTimeout(140)
    const press = await button.evaluate(node => ({ reduced: matchMedia("(prefers-reduced-motion:reduce)").matches, y: new DOMMatrix(getComputedStyle(node).transform).m42 }))
    assert(Math.abs(press.y - (reduced ? 0 : 1)) < 0.01, JSON.stringify(press))
    await page.mouse.move(0, 0)
    await page.mouse.up()
    assert.equal(new URL(page.url()).pathname, "/news/")
    console.log(`PASS PRESS ${engine} ${width} ${theme} reduced=${reduced}: ${JSON.stringify(press)}`)
    await context.close()
  }
  const role = Object.keys(sessions).find(name => /scrim/.test(name))
  assert(role, "Missing non-superuser scrim manager fixture")
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } })
  await context.addCookies([{ name: "ow_session", value: sessions[role], url: base }])
  const navigation = await (await context.request.get(base + "/api/admin/navigation")).json()
  const events = navigation.sections.find(section => section.label === "活动")
  assert.equal(events.tabs.length, 1)
  const page = await context.newPage()
  observe(page)
  assert.equal((await page.goto(base + "/admin/scrims/")).status(), 200)
  await page.locator(".b-nav a[aria-current=page]").waitFor()
  assert.equal(await page.locator("nav.b-tabs").count(), 0)
  if (engine !== "webkit") await page.screenshot({ path: join(out, "single-tab.png"), fullPage: true })
  console.log(`PASS SINGLE-TAB ${engine} ${role}: one API tab, no redundant strip`)
  await context.close()
  assert.deepEqual(errors, [], "Runtime, hydration and console errors")
  writeFileSync(join(out, "images.json"), JSON.stringify(results, null, 2))
} finally { await browser.close() }
