import assert from "node:assert/strict"
import { spawn } from "node:child_process"
import { createServer } from "node:http"
import { createRequire } from "node:module"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { extname, join, resolve, sep } from "node:path"
import { once } from "node:events"

const root = resolve(import.meta.dirname, "../../..")
const require = createRequire(join(root, "web/package.json"))
const { chromium } = require("playwright")
const output = resolve(process.env.UI_OUTPUT || "/tmp/sjtuow-302-ui")
mkdirSync(output, { recursive: true })
const browserPath = process.env.CHROMIUM || "/usr/bin/chromium"
const adminDist = join(root, "web/apps/admin/dist")
const siteRoot = join(root, "web/apps/site")
const issues = []
const results = []
const image = { id: 7, title: "测试封面", collection_id: 1, width: 640, height: 360, version: 1 }
const user = { id: 1, nickname: "界面检查员", email: "ui@example.invalid", superuser: true, admin: true, caps: ["admin.enter"], email_verified: true, is_sjtu: true, can_submit_article: true, can_comment: true, avatar_image_id: 7, default_avatar_image_id: 7, profile_gaps: [], waiting_letters: 0 }
const tab = (key, label, url) => ({ key, label, url, count: 0, tabs: [] })
const sections = [
  { ...tab("home", "首页", "/admin/") },
  { ...tab("content", "内容", "/admin/articles/"), tabs: [tab("articles", "文章", "/admin/articles/"), tab("images", "图片", "/admin/images/")] },
  { ...tab("members", "成员", "/admin/member-groups/"), tabs: [tab("groups", "成员分组", "/admin/member-groups/")] },
  { ...tab("review", "审核", "/admin/moderation/"), tabs: [tab("moderation", "巡查记录", "/admin/moderation/"), tab("avatars", "头像", "/admin/avatars/")] },
  { ...tab("settings", "设置", "/admin/settings/site/"), tabs: [tab("site", "全站设置", "/admin/settings/site/")] },
]
const draft = { title: "界面检查文章", slug: "ui-check", category_id: 1, cover_image_id: null, summary: "测试摘要", body_md: "测试正文", author_id: 1, comments_enabled: true, related_tournament_id: null, seo_title: "", search_description: "", go_live_at: null, expire_at: null }
const settings = {
  id: 1, version: 1, site_description: "测试站点", from_name: "测试站点", from_address: "ui@example.invalid", email_subject_prefix: "[测试]", smtp_host: "smtp.invalid", smtp_port: 587, smtp_security: "starttls", smtp_username: "fixture", founded_on: "2020-01-01", qq_group_url: "",
  team_max_members: 10, team_max_captained: 2, max_game_accounts: 3, tournament_reminder_hours: 24, scrim_reminder_hours: 2,
  moderation_enabled: false, moderation_image_enabled: false, moderation_provider: "", moderation_base_url: "", moderation_model: "fixture", moderation_max_tokens: 512, moderation_timeout_seconds: 10, moderation_extra_params: "", moderation_daily_limit: 100, moderation_notify_email: "", has_smtp_password: false, has_moderation_api_key: false,
  default_share_image_id: null, hero_image_id: 7, banner_news_id: null, banner_tournaments_id: null, banner_scrims_id: null, banner_teams_id: null, banner_members_id: null, image_titles: { 7: image.title },
}
function fixture(path, request) {
  const admin = request.headers.cookie?.includes("fixture-admin=1")
  if (path === "/api/session") return { user: admin ? user : null, flash: "", font_css_path: "" }
  if (path === "/api/admin/navigation") return { sections }
  if (path === "/api/admin/home") return { nickname: user.nickname, roles: ["超级管理员"], actions: [{ label: "写文章", url: "/admin/articles/new/", primary: true }], has_duties: true, todo: [], articles: [], setup: { required: [], optional: [], done: [] } }
  if (path === "/api/admin/articles") return { items: [], categories: [], total: 0, page: 1, page_size: 25 }
  if (path === "/api/admin/articles/1") return {
    article: { id: 1, ...draft, live: false, has_unpublished_changes: false, version: 1, owner_id: 1, created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z" }, revision: draft, version: 1, guide: true,
    capabilities: { edit: true, publish: true, delete: true, edit_author: true, edit_schedule: true, edit_comments: true }, categories: [{ id: 1, name: "测试分类", allow_submission: true }], authors: [{ id: 1, nickname: user.nickname, label: user.nickname }], tournaments: [], announced: 0, verdict: null,
  }
  if (path === "/api/admin/member-groups") return { groups: [] }
  if (path === "/api/admin/moderation") return { items: [], total: 0, page: 1, page_size: 25 }
  if (path === "/api/admin/settings") return { settings }
  if (path === "/api/admin/settings/backup") return { version: 1, values: { enabled: false, endpoint: "", region: "auto", bucket: "", prefix: "", access_key_id: "", has_secret_access_key: false, retention_days: 14 } }
  if (path === "/api/admin/image-collections") return { collections: [{ id: 1, name: "测试图片", key: "fixture", parent_id: null, image_count: 1, version: 1, can_add: true, can_upload: true, can_change: false, can_delete: false }] }
  if (path === "/api/images/7") return image
  if (path === "/api/teams") return { banner_image_id: null, teams: [], team_total: 0, recruiting_total: 0, role_counts: { tank: 0, damage: 0, support: 0 }, max_members: 10, recruiting_only: false, role: "" }
  if (path === "/api/tournaments") return { banner_image_id: null, groups: [] }
  if (path === "/api/scrims") return { banner_image_id: null, scrims: [] }
  throw new Error(`Missing fixture ${request.method} ${path}`)
}
const policy = "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
const types = { ".js": "text/javascript", ".css": "text/css", ".html": "text/html", ".svg": "image/svg+xml", ".woff2": "font/woff2" }
let sitePort
const server = createServer(async (request, response) => {
  try {
    const path = new URL(request.url, "http://fixture").pathname
    if (request.method !== "GET") throw new Error(`Unexpected write ${request.method} ${path}`)
    if (path.startsWith("/api/")) { response.setHeader("content-type", "application/json"); response.end(JSON.stringify(fixture(path, request))); return }
    if (path === "/favicon.ico") { response.writeHead(204); response.end(); return }
    if (path.startsWith("/media/r/")) { response.setHeader("content-type", "image/svg+xml"); response.end(readFileSync(join(root, "static/img/placeholders/hue-1.svg"))); return }
    if (path.startsWith("/admin/")) {
      const file = extname(path) ? resolve(adminDist, path.slice("/admin/".length)) : join(adminDist, "index.html")
      assert(file.startsWith(adminDist + sep))
      response.setHeader("content-type", types[extname(file)] || "application/octet-stream")
      response.setHeader("content-security-policy", policy)
      response.end(readFileSync(file)); return
    }
    const upstream = await fetch(`http://127.0.0.1:${sitePort}${request.url}`, { headers: { cookie: request.headers.cookie || "" }, redirect: "manual" })
    response.writeHead(upstream.status, Object.fromEntries(upstream.headers))
    response.end(Buffer.from(await upstream.arrayBuffer()))
  } catch (error) {
    issues.push(String(error))
    response.writeHead(500); response.end(String(error))
  }
})
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve))
const base = `http://127.0.0.1:${server.address().port}`
const portServer = createServer()
await new Promise(resolve => portServer.listen(0, "127.0.0.1", resolve))
sitePort = portServer.address().port
await new Promise(resolve => portServer.close(resolve))
const site = spawn(process.execPath, ["dist/server/server.js"], { cwd: siteRoot, env: { ...process.env, NODE_ENV: "production", STRICT_CSP: "1", PORT: String(sitePort), API_BASE: base }, stdio: ["ignore", "pipe", "pipe"] })
site.stderr.on("data", data => process.stderr.write(data))
let browser
try {
  const deadline = Date.now() + 15000
  while (true) {
    try { const response = await fetch(`${base}/accounts/login/`); assert.equal(response.status, 200); break }
    catch (error) { if (Date.now() > deadline || site.exitCode !== null) throw error; await new Promise(resolve => setTimeout(resolve, 100)) }
  }
  issues.length = 0
  browser = await chromium.launch({ executablePath: browserPath, headless: true })
  for (const width of [375, 1280]) for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme })
    await context.addInitScript(theme => { localStorage.setItem("ow-theme", theme); window.uiCsp = []; document.addEventListener("securitypolicyviolation", event => window.uiCsp.push(event.violatedDirective)) }, theme)
    const page = await context.newPage()
    page.on("pageerror", error => issues.push(String(error)))
    page.on("console", message => { if (message.type() === "error") issues.push(message.text()) })
    const pages = ["/accounts/login/", "/accounts/signup/", "/teams/", "/tournaments/", "/scrims/", "/search/"]
    for (const path of [...pages, "/admin/", "/admin/articles/", "/admin/articles/1/", "/admin/member-groups/", "/admin/moderation/", "/admin/settings/site/"]) {
      if (path.startsWith("/admin/")) await context.addCookies([{ name: "fixture-admin", value: "1", url: base }])
      assert.equal((await page.goto(base + path)).status(), 200, path)
      await page.locator("h1").waitFor()
      if (path.startsWith("/admin/")) await page.locator(".b-nav a").first().waitFor()
      const ready = { "/admin/": "[data-todo]", "/admin/articles/": ".c-empty", "/admin/member-groups/": ".c-empty", "/admin/moderation/": ".c-table" }[path]
      if (ready) await page.locator(ready).waitFor()
      if (path === "/admin/articles/1/") await page.locator(".cm-content").waitFor()
      if (path === "/admin/settings/site/") await page.locator("#setting-site_description").waitFor()
      await page.evaluate(() => document.fonts.ready)
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
      const result = await page.evaluate(() => ({
        title: document.querySelector("h1")?.textContent,
        width: innerWidth, scroll: document.documentElement.scrollWidth,
        emptyDecoration: [...document.querySelectorAll(".c-empty")].some(node => { const style = getComputedStyle(node, "::before"); return !["none", "normal"].includes(style.content) || style.backgroundImage !== "none" }),
        emptyPreviews: [...document.querySelectorAll(".b-picker__preview")].filter(node => !node.querySelector("img")).length,
        brokenImages: [...document.images].filter(image => image.complete && !image.naturalWidth).map(image => image.src),
        csp: window.uiCsp,
      }))
      assert(result.title, `${path}: missing title`)
      assert(result.scroll <= result.width + 1, `${path}: overflow ${result.scroll}/${result.width}`)
      assert.equal(result.emptyDecoration, false, `${path}: decorated empty state`)
      assert.equal(result.emptyPreviews, 0, `${path}: empty picture preview`)
      assert.deepEqual(result.brokenImages, [], path)
      assert.deepEqual(result.csp, [], path)
      if (path.startsWith("/accounts/")) assert.equal(await page.locator(".c-why").count(), 0)
      if (path === "/accounts/signup/") {
        assert.equal(await page.locator('form a[href="/terms/"]').count(), 1)
        assert.equal(await page.locator('form a[href="/privacy/"]').count(), 1)
        assert.equal(await page.locator('input[type="checkbox"][required]').count(), 2)
      }
      if (path.startsWith("/admin/")) {
        assert.equal(await page.locator(".b-head__kicker,.b-account img").count(), 0)
        await page.locator(".b-account details.c-menu summary").click()
        assert(await page.locator('.b-account a[href="/me/"]').isVisible())
        await page.keyboard.press("Escape")
      }
      if (path === "/admin/articles/1/") {
        assert.equal(await page.locator("[data-submission-guide]").count(), 0)
        assert(await page.locator('button[name="publish"]').isVisible())
        assert.equal(await page.locator('button[aria-label="选择封面"]').count(), 1)
        assert.equal(await page.locator('select[name="author"] option:checked').innerText(), user.nickname)
      }
      if (path === "/admin/articles/") assert(await page.locator('.b-head__actions a[href="/admin/articles/new/"]').isVisible())
      if (path === "/admin/settings/site/") {
        assert.equal(await page.locator('.b-picker__preview img').count(), 1)
        assert.equal(await page.locator('button[aria-label^="选择"]').count(), 7)
      }
      const name = `${width}-${theme}-${path.replaceAll("/", "_") || "home"}.png`
      await page.locator("h1").click()
      await page.screenshot({ path: join(output, name), fullPage: true })
      results.push({ path, width, theme, title: result.title, screenshot: name })
      console.log(`PASS ${width} ${theme} ${path}`)
    }
    await context.close()
  }
  assert.deepEqual(issues, [], "browser or fixture errors")
  writeFileSync(join(output, "results.json"), JSON.stringify({ pages: results.length, results }, null, 2))
  console.log(`UI-CLEANUP PASS ${results.length} pages; screenshots ${output}`)
} finally {
  await browser?.close()
  if (site.exitCode === null) {
    const stopped = once(site, "exit")
    site.kill("SIGTERM")
    await stopped
  }
  await new Promise(resolve => server.close(resolve))
}
