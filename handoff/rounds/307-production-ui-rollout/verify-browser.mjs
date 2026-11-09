import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { readFileSync, writeFileSync, mkdirSync } from "node:fs"
import { join, resolve } from "node:path"
import { createHash } from "node:crypto"
const root = resolve(import.meta.dirname, "../../..")
const { chromium, request } = createRequire(join(root, "web/package.json"))("playwright")
const privateFile = process.argv[2]
const config = JSON.parse(readFileSync(privateFile, "utf8"))
const manifest = JSON.parse(readFileSync(process.argv[3], "utf8"))
const output = process.argv[4]
mkdirSync(output, { recursive: true, mode: 0o700 })
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true })
const results = [], errors = []
let revoked = false, entrypoints = 0
function observe(page) {
  page.on("pageerror", error => errors.push({ kind: "runtime", type: error.name }))
  page.on("console", message => { if (message.type() === "error" || /hydration|mismatch/i.test(message.text())) errors.push({ kind: "console", type: message.type() }) })
  page.on("response", response => { if (response.status() >= 500) errors.push({ kind: "http", status: response.status() }) })
}
async function ready(page, admin = false) {
  await page.locator(admin ? ".b-head__title" : "#main").first().waitFor()
  if (!admin) await page.waitForFunction(() => document.documentElement.classList.contains("js-ready"))
  await page.evaluate(async () => {
    await document.fonts.ready
    for (const image of document.images) image.loading = "eager"
    await Promise.all([...document.images].map(image => image.decode().catch(() => {})))
  })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), "No horizontal overflow")
  assert.equal(await page.evaluate(() => [...document.images].filter(image => !image.complete || !image.naturalWidth).length), 0, "Images load")
}
async function verifyEntry(page, context) {
  const entries = await page.locator('script[src]').evaluateAll(nodes => nodes.map(node => node.src))
  for (const source of entries) {
    const url = new URL(source)
    assert.equal(url.origin, new URL(config.base).origin)
    const path = url.pathname.slice(1)
    assert(manifest.assets[path], "Runtime entry must belong to the released asset set")
    const response = await context.request.get(source)
    assert(response.ok())
    assert.equal(createHash("sha256").update(await response.body()).digest("hex"), manifest.assets[path], "Public entry bytes match the release")
    entrypoints++
  }
}
try {
  const probe = await request.newContext({ baseURL: config.base, extraHTTPHeaders: { Cookie: "ow_session=" + config.token } })
  const initialSession = await (await probe.get("/api/session")).json()
  assert(initialSession.user && initialSession.user.id === config.userId && initialSession.user.superuser)
  const publicHealth = await probe.get("/healthz")
  const status = await publicHealth.json()
  assert(publicHealth.ok() && status.status === "ok" && Object.values(status.checks).every(item => item.ok))
  await probe.dispose()
  console.log("PASS PRODUCTION public health and existing-account session")
  for (const width of [375, 1280]) for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ baseURL: config.base, viewport: { width, height: 1000 }, colorScheme: theme, hasTouch: width === 375 })
    await context.addInitScript(theme => {
      localStorage.setItem("ow-theme", theme)
      document.addEventListener("securitypolicyviolation", () => console.error("PRODUCTION-CSP"))
    }, theme)
    const page = await context.newPage()
    observe(page)
    for (const path of config.paths) {
      assert((await page.goto(path)).ok())
      await ready(page)
      if (path === "/") await verifyEntry(page, context)
      if (path === "/accounts/signup/") {
        await page.locator("#id_agreed_terms").focus()
        await page.keyboard.press("Tab")
        const focus = await page.locator("#id_agreed_cross_border").evaluate(node => ({ visible: node.matches(":focus-visible"), outline: getComputedStyle(node).outlineStyle, width: parseFloat(getComputedStyle(node).outlineWidth) }))
        assert(focus.visible && focus.outline === "solid" && focus.width >= 2)
        await page.screenshot({ path: join(output, `${width}-${theme}-signup-public.png`), fullPage: true })
      }
      results.push({ width, theme, audience: "public", checked: true })
    }
    await page.goto("/admin/")
    await page.waitForURL(url => url.pathname === "/accounts/login/")
    assert(new URL(page.url()).pathname === "/accounts/login/", "Visitor admin redirects to login")
    await context.addCookies([{ name: "ow_session", value: config.token, url: config.base, secure: true, httpOnly: true, sameSite: "Lax" }])
    const session = await (await context.request.get("/api/session")).json()
    assert(session.user && session.user.id === config.userId && session.user.superuser, "Pre-deploy session survives upgrade")
    for (const path of ["/me/", "/admin/", "/admin/articles/", "/admin/images/", "/admin/settings/site/", "/admin/settings/typography/", "/admin/users/"]) {
      assert((await page.goto(path)).ok())
      await ready(page, path.startsWith("/admin/"))
      if (path === "/admin/") await verifyEntry(page, context)
      results.push({ width, theme, audience: "existing-account", checked: true })
    }
    await context.close()
    console.log(`PASS PRODUCTION ${width} ${theme}: public/private pages, fresh entries, focus, images, bounds`)
  }
  assert.deepEqual(errors, [], "No runtime/hydration/CSP/500 errors")
} finally {
  await browser.close()
  const client = await request.newContext({ baseURL: config.base, extraHTTPHeaders: { Cookie: "ow_session=" + config.token, Origin: config.base } })
  try {
    const logout = await client.post("/api/auth/logout", { data: {} })
    assert(logout.ok(), "Revoke only the temporary verification session")
    // Send the original token explicitly, independent of the cleared cookie jar.
    const check = await client.get("/api/session", { headers: { Cookie: "ow_session=" + config.token } })
    assert.equal((await check.json()).user, null)
    revoked = true
    console.log("PASS PRODUCTION temporary session revoked; original token no longer authenticates")
  } finally { await client.dispose() }
  writeFileSync(join(output, "production-result.json"), JSON.stringify({ source: manifest.source, views: results.length, entrypointsVerified: entrypoints, results, errors, temporarySessionRevoked: revoked }, null, 2))
}
