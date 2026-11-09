import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
const { base, sessions, output } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { webkit } = createRequire(join(process.argv[3], "web/package.json"))("playwright")
const browser = await webkit.launch({ headless: true })
try {
  const context = await browser.newContext()
  await context.addCookies([{ name: "ow_session", value: sessions.officer, url: base }])
  await context.addInitScript(() => {
    window.cspEvents = []
    window.styleWrites = []
    const setAttribute = Element.prototype.setAttribute
    Element.prototype.setAttribute = function (name, value) {
      if (name === "style") window.styleWrites.push({ element: this.tagName, value, stack: new Error().stack })
      return setAttribute.call(this, name, value)
    }
    const appendChild = Node.prototype.appendChild
    Node.prototype.appendChild = function (child) {
      if (child.tagName === "STYLE") window.styleWrites.push({ element: "STYLE", value: child.textContent, stack: new Error().stack })
      return appendChild.call(this, child)
    }
    document.addEventListener("securitypolicyviolation", event => window.cspEvents.push({ directive: event.violatedDirective, uri: event.blockedURI, source: event.sourceFile, line: event.lineNumber, sample: event.sample }))
  })
  const page = await context.newPage()
  await page.goto(base + "/_styleguide/interactions/")
  await page.waitForTimeout(500)
  const before = await page.evaluate(() => [...window.cspEvents])
  await page.locator('[data-control="text"]').waitFor()
  const afterLocator = await page.evaluate(() => [...window.cspEvents])
  await page.screenshot({ path: join(output, "default-caret.png") })
  await page.waitForTimeout(100)
  const defaultCaret = await page.evaluate(() => [...window.cspEvents])
  await page.evaluate(() => { window.cspEvents = [] })
  await page.screenshot({ path: join(output, "initial-caret.png"), caret: "initial" })
  await page.waitForTimeout(100)
  const initialCaret = await page.evaluate(() => [...window.cspEvents])
  const styleWrites = await page.evaluate(() => window.styleWrites)
  const result = { before, afterLocator, defaultCaret, initialCaret, styleWrites }
  console.log("SCREENSHOT-CSP " + JSON.stringify(result))
  writeFileSync(join(output, "csp.json"), JSON.stringify(result, null, 2))
  assert(defaultCaret.length > afterLocator.length)
  assert(initialCaret.some(event => event.directive === "style-src-elem"))
} finally { await browser.close() }
