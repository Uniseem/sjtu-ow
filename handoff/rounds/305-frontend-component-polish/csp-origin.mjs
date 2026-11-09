import { createRequire } from "node:module"
import { readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
const { base, sessions, output } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { webkit } = createRequire(join(process.argv[3], "web/package.json"))("playwright")
const browser = await webkit.launch({ headless: true })
const results = []
try {
  for (const [path, javaScriptEnabled] of [["/accounts/login/", false], ["/does-not-exist-305/", true], ["/_styleguide/interactions/", true]]) {
    const context = await browser.newContext({ javaScriptEnabled })
    await context.addCookies([{ name: "ow_session", value: sessions.officer, url: base }])
    await context.addInitScript(() => {
      window.cspEvents = []
      document.addEventListener("securitypolicyviolation", event => window.cspEvents.push({ directive: event.violatedDirective, source: event.sourceFile, line: event.lineNumber, sample: event.sample }))
    })
    const page = await context.newPage()
    const response = await page.goto(base + path)
    const html = await response.text()
    await page.waitForTimeout(700)
    const state = await page.evaluate(() => ({ events: window.cspEvents || [], styles: [...document.querySelectorAll("[style]")].map(node => node.outerHTML), scripts: [...document.scripts].map(node => node.src) }))
    results.push({ path, javaScriptEnabled, status: response.status(), serverStyleAttributes: [...html.matchAll(/\sstyle="[^"]*"/g)].map(match => match[0]), ...state })
    console.log("CSP-ORIGIN " + JSON.stringify(results.at(-1)))
    await context.close()
  }
  writeFileSync(join(output, "origin.json"), JSON.stringify(results, null, 2))
} finally { await browser.close() }
