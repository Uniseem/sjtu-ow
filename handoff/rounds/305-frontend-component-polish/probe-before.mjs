import { createRequire } from "node:module"
import { readFileSync } from "node:fs"
import { join } from "node:path"
const { base } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const require = createRequire(join(process.argv[3], "web/package.json"))
const { chromium } = require("playwright")
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true })
try {
  for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ colorScheme: theme })
    const page = await context.newPage()
    await page.goto(base + "/accounts/signup/")
    const checkbox = page.locator("#id_agreed_terms")
    await checkbox.focus()
    await page.keyboard.press("Tab")
    await page.keyboard.press("Shift+Tab")
    console.log(JSON.stringify({ theme, checkbox: await checkbox.evaluate(node => ({ focused: document.activeElement === node, visible: node.matches(":focus-visible"), outline: getComputedStyle(node).outlineStyle, width: getComputedStyle(node).outlineWidth })) }))
    await context.close()
  }
  const context = await browser.newContext({ javaScriptEnabled: false, reducedMotion: "reduce" })
  const page = await context.newPage()
  await page.goto(base + "/accounts/login/")
  await page.waitForTimeout(300)
  console.log(JSON.stringify({ reducedNoScriptAt300ms: await page.locator(".c-nojs").evaluate(node => ({ visibility: getComputedStyle(node).visibility, delay: getComputedStyle(node).animationDelay })) }))
  await context.close()
} finally { await browser.close() }
