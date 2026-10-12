#!/usr/bin/env node
// Production Go/worker/SMTP/Caddy journeys; browser events are fatal.
import { spawnSync } from "node:child_process"
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { resolve } from "node:path"
import { exerciseMarkdownEditor } from "../e2e/journeys/markdown-editor.mjs"
const root = resolve(import.meta.dirname, "..")
const mode = process.argv[2] ?? "newbie"
const option = name => process.argv.find(arg => arg.startsWith(`--${name}=`))?.split("=").slice(1).join("=")
const engine = option("engine") ?? "chromium"
if (!["newbie", "admin", "pages"].includes(mode) || !["chromium", "webkit"].includes(engine)) throw new Error("unknown journey/engine")
const fixture = option("fixture")
if (!fixture) {
  const result = spawnSync("uv", ["run", "python", "e2e/journeys/run.py", mode, engine], { cwd: root, stdio: "inherit" })
  process.exit(result.status ?? 1)
}
const config = JSON.parse(readFileSync(fixture, "utf8"))
const require = createRequire(resolve(root, "web/package.json"))
const { chromium, webkit } = require("playwright")
const browser = await (engine === "webkit" ? webkit : chromium).launch(engine === "chromium" ? { executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] } : {})
const failures = [], contexts = [], checks = []
const check = (name, condition) => { if (!condition) throw new Error(name); checks.push(name); console.log(`PASS JOURNEY ${engine} ${mode} ${name}`) }
async function context(role = "visitor", ip = "203.0.113.90") {
  const ctx = await browser.newContext({ baseURL: config.base, extraHTTPHeaders: { "X-Forwarded-For": ip }, reducedMotion: "reduce" })
  contexts.push(ctx)
  if (config.sessions[role]) await ctx.addCookies([{ name: "ow_session", value: config.sessions[role], url: config.base }])
  await ctx.addInitScript(() => document.addEventListener("securitypolicyviolation", event => console.error("JOURNEY-CSP", event.violatedDirective)))
  const page = await ctx.newPage()
  page.on("dialog", async dialog => { if (dialog.type() === "confirm") await dialog.accept(); else failures.push("unexpected dialog " + dialog.type()) })
  page.on("pageerror", error => failures.push("runtime " + error.message))
  page.on("console", message => {
    const text = message.text()
    if (/Hydration/i.test(text) || message.type() === "error") {
      // Browser-generated log of an expected gate is accounted for by pages
      // status assertions. Application console errors are never suppressed.
      if (!/^Failed to load resource:.*status of (401|403|404|429)/.test(text)) failures.push("console " + text)
    }
  })
  page.on("response", response => { if (response.status() >= 500) failures.push("HTTP " + response.status() + " " + new URL(response.url()).pathname) })
  return { ctx, page }
}
async function settle(page) {
  await page.waitForFunction(() => document.readyState === "complete" && (document.querySelector("#main,main") || (/^\/_styleguide\/emails\/[^/]+\/$|^\/api\/letters\/.+\/preview$/.test(location.pathname) && document.body)))
  await page.waitForFunction(() => ![...document.querySelectorAll("[role=status]")].some(node => /^正在加载…$|^加载中…$/.test(node.textContent.trim())))
  await page.evaluate(() => document.fonts.ready)
}
async function go(page, path) { const response = await page.goto(path); await settle(page); return response }
async function json(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => {
    const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers ?? {}) } })
    const body = await response.json()
    if (!response.ok) throw new Error(`API ${path}: ${response.status} ${body.error?.message}`)
    return body
  }, { path, options })
}
async function mailbox(email, start = 0) {
  for (let attempts = 0; attempts < 300; attempts++) {
    let rows = []
    try { rows = readFileSync(config.mailbox, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse) } catch {}
    const mail = rows.slice(start).filter(row => row.to === email && row.code && row.valid_mime).at(-1)
    if (mail) return mail.code
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  throw new Error("actual SMTP verification mail missing")
}
async function register(index) {
  const current = await context("visitor", `203.0.113.${100 + index}`)
  const { page } = current
  const email = `journey${index}@example.test`
  await go(page, "/accounts/signup/")
  await page.locator("#id_email").fill(email)
  await page.locator("#id_nickname").fill(`Journey ${index}`)
  await page.locator("#id_password1").fill("Birch!Comet736")
  await page.locator("#id_password2").fill("Birch!Comet736")
  await page.locator("#id_is_sjtu_0").check()
  await page.locator("#id_agreed_terms").check()
  await page.locator("#id_agreed_cross_border").check()
  await page.locator("#main form button[type=submit]").click()
  await page.waitForURL("**/accounts/confirm-email/**")
  await page.locator("#id_code").fill(await mailbox(email))
  await page.locator("#main form").first().locator("button[type=submit]").click()
  await page.waitForURL("**/me/")
  check("actual SMTP registration " + index, (await json(page, "/api/session")).user.email === email)
  await go(page, "/me/game-accounts/?new=1")
  await page.locator("#create-game-account input[name=battletag]").fill(`Journey${index}#12345`)
  for (const role of ["tank", "damage", "support"]) await page.locator(`#create-game-account select[name=rank_${role}]`).selectOption("20")
  await page.locator("#create-game-account button[type=submit]").click()
  await page.waitForFunction(() => !document.querySelector("#create-game-account") || document.querySelector("#game-account-list")?.textContent.includes("Journey"))
  await go(page, "/me/contacts/?new=1")
  await page.locator("#create-contact input[name=value]").fill(`1234567${index}`)
  await page.locator("#create-contact button[type=submit]").click()
  await go(page, "/me/")
  const profile = await json(page, "/api/me/profile")
  check("real game ID/contact persistence " + index, profile.game_accounts.length === 1 && profile.contacts.length === 1)
  return { ...current, account: profile.game_accounts[0].id }
}
async function signupScrim(page) {
  await go(page, `/scrims/${config.data.scrim}/`)
  for (const checkbox of await page.locator("#slot-scrim-actions input[name=roles]").all()) {
    if (!await checkbox.isChecked()) await checkbox.locator('xpath=..').click()
    check('role choice label toggles checkbox', await checkbox.isChecked())
  }
  await page.locator("#slot-scrim-actions button[type=submit]").filter({ hasText: /^报名$/ }).click()
  await page.getByText("已报名", { exact: true }).waitFor()
  const personal = await json(page, "/api/me/scrims")
  check("real scrim persisted", JSON.stringify(personal).includes(String(config.data.scrim)))
}
async function letters(page) {
  if (!new URL(page.url()).pathname.includes("/letters/")) await page.waitForURL("**/letters/**")
  await settle(page)
  const submit = page.locator("#main button[type=submit]").filter({ hasText: /发出|发送|决定|确认/ }).first()
  await submit.click()
  await page.waitForURL(url => !url.pathname.includes("/letters/"))
  await settle(page)
}
try {
  if (mode === "pages") {
    for (const role of ["visitor", "member", "captain", "tournament_admin", "scrim_admin", "content_editor", "officer"]) {
      const { ctx, page } = await context(role)
      for (const item of config.pages.filter(row => row.role === role)) {
        if (item.path.startsWith('/accounts/')) {
          const fresh = spawnSync('uv',['run','python','e2e/journeys/account_context.py',fixture,item.name,role,item.path],{cwd:root,encoding:'utf8'})
          if (fresh.status !== 0) throw new Error('account context setup failed')
          const data = JSON.parse(fresh.stdout.trim().split('\n').at(-1))
          Object.assign(item,{path:data.path,status:data.status,location:data.location})
          await ctx.clearCookies()
          await ctx.addCookies(data.cookies.map(cookie => ({...cookie,url:config.base})))
        }
        if (["/sitemap.xml", "/robots.txt", "/favicon.ico", "/apple-touch-icon.png"].includes(item.path)) {
          const resource = await ctx.request.get(item.path)
          check(role + " resource " + item.path, resource.status() < 400 && (await resource.body()).length > 0)
          continue
        }
        const responses = []
        const listen = response => { if (new URL(response.url()).pathname.startsWith("/api/")) responses.push(response.status()) }
        page.on("response", listen)
        const response = await go(page, item.path)
        let actual = response.status()
        if (item.path.startsWith("/admin/") && actual === 200) {
          if (new URL(page.url()).pathname === "/accounts/login/") actual = 302
          else actual = await page.evaluate(() => {
            const status = document.querySelector('[data-page-status]')?.getAttribute('data-page-status') ?? document.querySelector('.code')?.textContent
            return status === undefined || status === null ? null : Number(status)
          }) ?? responses.filter(code => code >= 400).at(-1) ?? 200
        }
        if (item.status >= 300 && item.status < 400) {
          const expected = new URL(item.location, config.base)
          const current = new URL(page.url())
          check(role + " redirect " + item.path, current.pathname === expected.pathname && current.searchParams.toString() === expected.searchParams.toString())
        } else check(role + " status " + item.path, actual === item.status)
        check(role + " body " + item.path, (await page.locator("body").innerText()).trim().length > 0)
        check(role + " no broken images " + item.path, await page.evaluate(() => [...document.images].filter(image => image.complete && image.naturalWidth === 0).length) === 0)
        page.off("response", listen)
      }
      await ctx.close()
    }
  } else if (mode === "newbie") {
    const { page } = await register(1)
    await signupScrim(page)
    await go(page, `/teams/${config.data.team}/apply/`)
    await page.locator("#id_role_support").check()
    await page.locator("#id_message").fill("新人旅程申请")
    await page.getByRole("button", { name: "提交申请", exact: true }).click()
    await letters(page)
    const teams = await json(page, "/api/me/teams")
    check("application persisted after letters", JSON.stringify(teams).includes("pending"))
    await go(page, "/")
    check("home my agenda", (await page.locator("#main").innerText()).includes("截图内战"))
    await go(page, "/me/teams/")
    await page.getByRole("button", { name: "撤回", exact: true }).click()
    await page.getByText("入队申请已撤回。", { exact: true }).waitFor()
    await go(page, "/me/teams/")
    check("cross page application cancellation", JSON.stringify(await json(page, "/api/me/teams")).includes("cancelled"))
  } else {
    for (let index = 1; index <= 10; index++) {
      const { page, ctx, account } = await register(index)
      await signupScrim(page)
      // Prepare three real individual registrations through the public API;
      // the admin composition and save itself are exercised with UI clicks.
      if (index <= 3) await json(page, `/api/tournaments/${config.data.cup}/signup`, { method: "POST", body: JSON.stringify({ game_account_id: account, roles: ["support"] }) })
      await ctx.close()
    }
    const { page } = await context("officer")
    await go(page, `/admin/scrims/${config.data.scrim}/split/`)
    const choices = page.locator("table input[type=checkbox]")
    check("at least ten actual registrations", await choices.count() >= 10)
    for (const checkbox of (await choices.all()).slice(0, 10)) await checkbox.check()
    await page.getByRole("button", { name: "生成分队", exact: true }).click()
    await page.locator("[data-split-board]").waitFor()
    const card = page.locator('[data-team-panel=a] [data-signup]').first()
    const signup = await card.getAttribute("data-signup")
    await card.getByRole("button", { name: "缓冲", exact: true }).click()
    const buffered = page.locator(`[data-board-zone=buffer] [data-signup="${signup}"]`)
    await buffered.waitFor()
    await buffered.getByRole("button", { name: "A", exact: true }).click()
    await page.locator(`[data-team-panel=a] [data-signup="${signup}"]`).waitFor()
    await go(page, `/admin/scrims/${config.data.scrim}/split/`)
    check("split movement persisted across reload", await page.locator(`[data-team-panel=a] [data-signup="${signup}"]`).count() === 1)
    await go(page, `/admin/tournaments/${config.data.cup}/teams/`)
    await page.getByRole("button", { name: "再加一支队伍", exact: true }).click()
    const zone = page.locator("[data-team-panel]").last()
    await zone.locator("input").fill("Journey队伍")
    for (let index = 0; index < 3; index++) await page.locator('[data-board-zone=""] [data-signup]').first().getByRole("button", { name: "Journey队伍", exact: true }).click()
    await page.getByRole("button", { name: "保存编队", exact: true }).click()
    await letters(page)
    await go(page, `/admin/tournaments/${config.data.cup}/teams/`)
    check("team composition persisted", (await page.locator("#main").innerText()).includes("Journey队伍"))
    await go(page, "/admin/articles/new/")
    await page.locator("input[name=title]").fill("Journey真实发布")
    await page.locator("select[name=category]").selectOption(String(config.data.category))
    await exerciseMarkdownEditor(page)
    check("legacy Markdown commands/preview/fullscreen", true)
    const editor = page.locator(".cm-content").first()
    await editor.fill("真实浏览器里撰写的文章正文。")
    await page.locator(".b-picker button").filter({ hasText: /^选择$/ }).first().click()
    await page.locator('[role=dialog] button').filter({ has: page.locator('img') }).first().click()
    await page.getByRole("button", { name: "发布", exact: true }).click()
    await page.getByText("文章已发布。", { exact: true }).waitFor()
    const published = await json(page, "/api/page/news")
    check("article publicly published with selected cover", JSON.stringify(published).includes("Journey真实发布"))
  }
  check("zero runtime/console/CSP/hydration/500", failures.length === 0)
  console.log(`JOURNEY-OK ${mode} ${engine} ${checks.length}`)
} catch (error) {
  console.error("JOURNEY-FAILED", error.stack, JSON.stringify(failures))
  process.exitCode = 1
} finally {
  for (const ctx of contexts) await ctx.close().catch(() => {})
  await browser.close()
}
