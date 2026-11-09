import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
const { base, output, sessions } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { webkit } = createRequire(join(process.argv[3], "web/package.json"))("playwright")
const browser = await webkit.launch({ headless: true })
const observations = []
try {
  for (const reduced of [false, true]) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 1000 }, reducedMotion: reduced ? "reduce" : "no-preference" })
    await context.addCookies([{ name: "ow_session", value: sessions.officer, url: base }])
    const page = await context.newPage()
    await page.goto(base + "/_styleguide/interactions/")
    await page.locator('[data-control="toast"]').waitFor()
    await page.evaluate(() => {
      window.toastTimeline = []
      const record = () => window.toastTimeline.push({ time: performance.now(), messages: [...document.querySelectorAll(".c-toast")].map(node => ({ text: node.textContent, phase: node.className, opacity: getComputedStyle(node).opacity })) })
      new MutationObserver(record).observe(document.querySelector(".c-toasts"), { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] })
    })
    const before = await page.evaluate(() => performance.now())
    await page.locator('[data-control="toast"]').click()
    const first = await page.evaluate(() => performance.now())
    await page.locator('[data-control="flash"]').click()
    const second = await page.evaluate(() => performance.now())
    await page.waitForTimeout(4200)
    const state = await page.evaluate(() => ({ now: performance.now(), timeline: window.toastTimeline, messages: [...document.querySelectorAll(".c-toast")].map(node => ({ text: node.textContent, phase: node.className, visibility: getComputedStyle(node).visibility, opacity: getComputedStyle(node).opacity })) }))
    observations.push({ reduced, before, first, second, ...state })
    console.log("TOAST-TIMING " + JSON.stringify(observations.at(-1)))
    await page.waitForTimeout(1200)
    assert.equal(await page.locator(".c-toast").count(), 0)
    await context.close()
  }
  writeFileSync(join(output, "timing.json"), JSON.stringify(observations, null, 2))
} finally { await browser.close() }
