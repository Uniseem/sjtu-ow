import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { readFileSync } from "node:fs"
import { join } from "node:path"
const { base, sessions } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { chromium } = createRequire(join(process.argv[3], "web/package.json"))("playwright")
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true })
try {
  for (const mutation of ["focus", "grace"]) {
    const context = await browser.newContext({ javaScriptEnabled: mutation !== "grace", reducedMotion: mutation === "grace" ? "reduce" : "no-preference" })
    if (mutation === "focus") await context.addCookies([{ name: "ow_session", value: sessions.officer, url: base }])
    const page = await context.newPage()
    let changed = 0
    await page.route("**/*.css*", async route => {
      const response = await route.fetch()
      const override = mutation === "focus" ? '.c-field input[type="checkbox"]:focus-visible{outline:none!important}' : '@media(prefers-reduced-motion:reduce){*{animation-delay:0s!important}}'
      await route.fulfill({ response, body: await response.text() + "\n" + override })
      changed++
    })
    await page.goto(base + (mutation === "focus" ? "/_styleguide/interactions/" : "/accounts/login/"))
    let passes, details
    if (mutation === "focus") {
      await page.locator('[data-control="select"]').focus()
      await page.keyboard.press("Tab")
      details = await page.locator('[data-control="check"]').evaluate(node => ({ focused: node === document.activeElement, visible: node.matches(":focus-visible"), outline: getComputedStyle(node).outlineStyle }))
      passes = details.focused && details.visible && details.outline !== "none"
    } else {
      await page.waitForTimeout(300)
      details = await page.locator(".c-nojs").evaluate(node => ({ visibility: getComputedStyle(node).visibility, delay: getComputedStyle(node).animationDelay }))
      passes = details.visibility === "hidden" && parseFloat(details.delay) >= 8
    }
    assert(changed > 0, "No external stylesheet was mutated")
    assert.throws(() => assert(passes), assert.AssertionError, `${mutation}: acceptance missed a deliberately broken stylesheet`)
    console.log(`NEGATIVE-CAUGHT ${mutation}: ${JSON.stringify(details)}`)
    await context.close()
  }
} finally { await browser.close() }
