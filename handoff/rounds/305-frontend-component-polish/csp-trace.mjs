import { createRequire } from "node:module"
import { readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
const { base, sessions, output } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { webkit } = createRequire(join(process.argv[3], "web/package.json"))("playwright")
const browser = await webkit.launch({ headless: true })
const results = []
try {
  for (const mode of ["home-staff", "components", "dialog-removed", "select-removed", "choices-removed", "original-no-js"]) {
    const path = mode === "home-staff" ? "/" : mode === "components" ? "/_styleguide/components/" : "/_styleguide/interactions/"
    const context = await browser.newContext({ javaScriptEnabled: mode !== "original-no-js" })
    await context.addCookies([{ name: "ow_session", value: sessions.officer, url: base }])
    await context.addInitScript(() => {
      window.styleWrites = []
      window.cspEvents = []
      const record = (property, value) => window.styleWrites.push({ property, value, stack: new Error().stack })
      for (const property of Object.getOwnPropertyNames(CSSStyleDeclaration.prototype)) {
        const descriptor = Object.getOwnPropertyDescriptor(CSSStyleDeclaration.prototype, property)
        if (descriptor?.set && descriptor.configurable) Object.defineProperty(CSSStyleDeclaration.prototype, property, { ...descriptor, set(value) { if (!this.parentRule) record(property, value); return descriptor.set.call(this, value) } })
      }
      const setProperty = CSSStyleDeclaration.prototype.setProperty
      CSSStyleDeclaration.prototype.setProperty = function (property, value, priority) { if (!this.parentRule) record(property, value); return setProperty.call(this, property, value, priority) }
      const innerHTML = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML")
      Object.defineProperty(Element.prototype, "innerHTML", { ...innerHTML, set(value) { if (/style\s*=/.test(value)) record("innerHTML", value); return innerHTML.set.call(this, value) } })
      document.addEventListener("securitypolicyviolation", event => window.cspEvents.push({ directive: event.violatedDirective, source: event.sourceFile, line: event.lineNumber }))
    })
    const page = await context.newPage()
    if (mode.endsWith("removed")) await context.addInitScript(mode => {
      document.addEventListener("DOMContentLoaded", () => {
        const selector = mode === "dialog-removed" ? "dialog" : mode === "select-removed" ? "select" : '[data-polish="choices"]'
        document.querySelectorAll(selector).forEach(node => node.remove())
      })
    }, mode)
    if (mode === "no-css") await page.route("**/*.css*", route => route.fulfill({ body: "", contentType: "text/css" }))
    if (mode === "no-mixed") await page.route("**/InteractionSpecimen-*.js", async route => {
      const response = await route.fetch()
      await route.fulfill({ response, body: (await response.text()).replace("indeterminate=!0", "indeterminate=!1") })
    })
    await page.goto(base + path)
    await page.waitForTimeout(800)
    if (mode === "native-mixed") {
      await page.evaluate(() => { document.querySelector('[data-control="mixed"]').indeterminate = true })
      await page.waitForTimeout(100)
    }
    const state = await page.evaluate(() => ({ writes: window.styleWrites, events: window.cspEvents }))
    results.push({ mode, path, ...state })
    console.log("CSP-TRACE " + JSON.stringify(results.at(-1)))
    await context.close()
  }
  writeFileSync(join(output, "trace.json"), JSON.stringify(results, null, 2))
} finally { await browser.close() }
