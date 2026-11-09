import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { readFileSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
const root = resolve(import.meta.dirname, "../../..")
const { chromium } = createRequire(join(root, "web/package.json"))("playwright")
const { base, token, output } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true })
const results = [], errors = []
try {
  for (const width of [375, 1280]) for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, hasTouch: width === 375 })
    await context.addInitScript(theme => {
      localStorage.setItem("ow-theme", theme)
      document.addEventListener("securitypolicyviolation", () => console.error("RELEASE-CSP"))
    }, theme)
    const page = await context.newPage()
    page.on("pageerror", error => errors.push(String(error)))
    page.on("console", message => { if (message.type() === "error" || /hydration|mismatch/i.test(message.text())) errors.push(message.text()) })
    assert.equal((await page.goto(base + "/accounts/signup/")).status(), 200)
    await page.waitForFunction(() => document.documentElement.classList.contains("js-ready"))
    await page.evaluate(() => document.fonts.ready)
    await page.locator("#id_agreed_terms").focus()
    await page.keyboard.press("Tab")
    const focus = await page.locator("#id_agreed_cross_border").evaluate(node => ({ visible: node.matches(":focus-visible"), outline: getComputedStyle(node).outlineStyle, width: parseFloat(getComputedStyle(node).outlineWidth) }))
    assert(focus.visible && focus.outline === "solid" && focus.width >= 2, JSON.stringify(focus))
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    await page.screenshot({ path: join(output, `image-${width}-${theme}-signup.png`), fullPage: true })
    await context.addCookies([{ name: "ow_session", value: token, url: base }])
    for (const path of ["/admin/", "/admin/articles/", "/admin/settings/site/"]) {
      assert.equal((await page.goto(base + path)).status(), 200)
      await page.locator(".b-head__title").waitFor()
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    }
    assert.equal((await page.goto(base + "/_styleguide/interactions/")).status(), 200)
    await page.locator('[data-control="menu"] summary').click()
    const panel = page.locator('[data-control="menu"] .c-menu__panel')
    await panel.waitFor()
    assert.equal(await panel.evaluate(node => getComputedStyle(node).animationName), "c-surface-in")
    await page.keyboard.press("Escape")
    await page.emulateMedia({ reducedMotion: "reduce" })
    await page.locator('[data-control="dialog-open"]').click()
    const dialog = page.locator('[data-control="dialog"]')
    await dialog.waitFor()
    assert(await dialog.evaluate(node => node.open && parseFloat(getComputedStyle(node).animationDuration) < 0.001))
    await page.keyboard.press("Escape")
    results.push({ width, theme, pages: 5, focus })
    console.log(`PASS IMAGE-SMOKE ${width} ${theme}: SSR/API/admin/CSP/focus/motion/bounds`)
    await context.close()
  }
  assert.deepEqual(errors, [])
  writeFileSync(join(output, "smoke-result.json"), JSON.stringify({ source: "564bb9a34a38f1ce630cee476b71c1e5cbe999cf", views: 20, results, errors }, null, 2))
} finally { await browser.close() }
