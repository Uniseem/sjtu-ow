import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { resolve } from "node:path"
const root = resolve(import.meta.dirname, "../..")
const { chromium } = createRequire(resolve(root, "web/package.json"))("playwright")
const config = JSON.parse(readFileSync(process.argv[2], "utf8"))
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] })
let checked = 0, failed = 0, broken = 0
try {
  for (const session of [null, ...config.sessions]) {
    const context = await browser.newContext({ baseURL: config.base })
    if (session) await context.addCookies([{ name: "ow_session", value: session.token, url: config.base }])
    await context.addInitScript(() => document.addEventListener("securitypolicyviolation", () => console.error("REHEARSAL-CSP")))
    const page = await context.newPage()
    page.on("pageerror", () => failed++)
    page.on("console", message => { if (/Hydration|REHEARSAL-CSP/.test(message.text())) failed++ })
    page.on("response", response => { if (response.status() >= 500) failed++ })
    const paths = [...config.paths, ...(session ? ["/me/", "/me/game-accounts/", "/me/contacts/", "/me/teams/", "/me/registrations/", "/me/scrims/", "/me/security/"] : []), ...(session?.admin ? ["/admin/", "/admin/articles/", "/admin/images/", "/admin/tournaments/", "/admin/scrims/", "/admin/users/", "/admin/settings/fonts/"] : [])]
    for (const path of paths) {
      const response = await page.goto(path)
      if (!response || response.status() >= 500) failed++
      await page.waitForFunction(() => document.readyState === "complete" && Boolean(document.querySelector("#main, main")))
      await page.waitForFunction(() => ![...document.querySelectorAll("[role=status]")].some(node => /^正在加载…$/.test(node.textContent.trim())))
      await page.evaluate(async () => {
        for (const image of document.images) image.loading = "eager"
        await document.fonts.ready
        await Promise.all([...document.images].map(image => image.decode().catch(() => {})))
      })
      broken += await page.evaluate(() => [...document.images].filter(image => image.naturalWidth === 0).length)
      checked++
    }
    await context.close()
  }
} catch { failed++ } finally { await browser.close() }
console.log(`PRIVATE-REHEARSAL-PAGES checked=${checked} failures=${failed} broken_images=${broken}`)
if (failed || broken || checked === 0) process.exit(1)
