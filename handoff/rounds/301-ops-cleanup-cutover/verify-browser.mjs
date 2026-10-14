import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { resolve } from "node:path"
const root = resolve(import.meta.dirname, "../../..")
const { chromium } = createRequire(resolve(root, "web/package.json"))("playwright")
const config = JSON.parse(readFileSync(process.argv[2], "utf8"))
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] })
let checked = 0, failures = 0, broken = 0
try {
  for (const session of [null, ...config.sessions]) {
    const context = await browser.newContext({ baseURL: config.base })
    if (session) await context.addCookies([{ name: "ow_session", value: session.token, url: config.base, secure: true, httpOnly: true, sameSite: "Lax" }])
    await context.addInitScript(() => document.addEventListener("securitypolicyviolation", () => console.error("PRODUCTION-CSP")))
    const page = await context.newPage()
    page.setDefaultTimeout(20000)
    page.on("pageerror", () => failures++)
    page.on("console", message => { if (message.type() === "error" || /Hydration|PRODUCTION-CSP/.test(message.text())) failures++ })
    page.on("response", response => { if (response.status() >= 500) failures++ })
    const paths = session ? ["/me/", "/admin/", "/admin/articles/", "/admin/images/", "/admin/tournaments/", "/admin/scrims/", "/admin/users/"] : config.paths
    for (const path of paths) {
      const response = await page.goto(path)
      if (!response?.ok()) failures++
      await page.waitForFunction(() => document.readyState === "complete" && document.querySelector("#main") && ![...document.querySelectorAll('[role=status]')].some(node => /^正在加载…$|^加载中…$/.test(node.textContent.trim())))
      if (!session || path === "/me/") await page.waitForFunction(() => document.documentElement.classList.contains("js-ready"))
      await page.evaluate(async () => {
        for (const image of document.images) image.loading = "eager"
        await document.fonts.ready
        await Promise.all([...document.images].map(image => image.decode().catch(() => {})))
      })
      broken += await page.evaluate(() => [...document.images].filter(image => image.naturalWidth === 0).length)
      checked++
    }
    if (!session) {
      await page.goto("/admin/")
      await page.waitForURL(url => url.pathname === "/accounts/login/")
      if (new URL(page.url()).searchParams.get("next") !== "/admin/") failures++
      checked++
    } else {
      const response = await context.request.post("/api/auth/logout", { data: {}, headers: { "Idempotency-Key": "production-301-check-logout" } })
      if (!response.ok()) failures++
      const current = await context.request.get("/api/session")
      if ((await current.json()).user !== null) failures++
      checked++
    }
    await context.close()
  }
} catch (error) {
  failures++
  console.error("PRODUCTION-BROWSER-OPERATION-FAILED " + error.name)
} finally {
  await browser.close()
}
console.log(`PRODUCTION-BROWSER checked=${checked} failures=${failures} broken_images=${broken}`)
if (failures || broken || !checked) process.exitCode = 1
