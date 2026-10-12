// Production admin SPA smoke checks, driven by Node's native WebSocket/CDP.
// API requests ALWAYS terminate at the local controlled fictional fixture server.
// This proves browser behavior/CSP, never real Go persistence or mail delivery.
// Run after a production build: node browser-check.mjs [chromium] [baseURL]
// With no baseURL the local server serves dist; baseURL only proxies read-only assets.
import { spawn } from "node:child_process"
import { createServer } from "node:http"
import { readFileSync, existsSync, mkdtempSync, rmSync, statSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, resolve, extname, sep } from "node:path"
import { fileURLToPath } from "node:url"

const appRoot = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(appRoot, "../../..")
const chromium = process.argv[2] || "/usr/bin/chromium"
const givenBase = process.argv[3]?.replace(/\/$/, "")
const policy = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://player.bilibili.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1sAAAAASUVORK5CYII="
const now = "2026-10-11T08:00:00Z"
const failures = []
const passed = []
const requests = []
const httpPending = new Map()
const httpTrace = []
const browserLog = []
const protocolTrace = []
let httpSequence = 0
let protocolDiagnostics = () => ({ pending: [] })
function trace(target, value, limit = 60) { target.push(value); if (target.length > limit) target.shift() }
function diagnostics(reason) {
  const value = {
    reason, stage, base, identity, browserPid: browser?.pid,
    browserExit: browser?.exitCode, browserSignal: browser?.signalCode,
    websocketState: socket?.readyState,
    protocol: protocolDiagnostics(),
    pendingHttp: [...httpPending.values()], http: httpTrace.slice(-30),
    protocolEvents: protocolTrace.slice(-25), browserLog: browserLog.slice(-30),
    apiRequests: requests.slice(-12).map(({ stage, method, path, key }) => ({ stage, method, path, keyPresent: Boolean(key) })),
  }
  console.error("ADMIN-BROWSER-DIAGNOSTICS " + JSON.stringify(value))
  return value
}
const expectedNetworkErrors = new Set()
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
let server
let browser
let socket
let profile
let base
let probeActive = false
let stage = "startup"
let identity = "editor"
let expireWrites = false
let editorDraft = {
  title: "Browser article", slug: "browser-article", category_id: 1,
  cover_image_id: null, summary: "Browser summary", body_md: "Original body",
  author_id: 1, comments_enabled: true, related_tournament_id: null,
  seo_title: "", search_description: "", go_live_at: null, expire_at: null,
}
let articleVersion = 3
let nextImage = 8
const images = [{ id: 7, collection_id: 1, title: "Fixture image", file_name: "fixture.png", file_size: 68, width: 1, height: 1, uploader_id: 1, created_at: now, version: 1 }]
const collections = [{ id: 1, name: "Fixture collection", key: "fixture", parent_id: null, version: 1, image_count: 1, can_add: true, can_change: false, can_delete: false, created_at: now }]
let boardVersion = 20
let placements = [
  { signup_id: 1, team: "a", role: "tank" },
  { signup_id: 2, team: "b", role: "tank" },
  { signup_id: 3, team: "", role: "" },
]
let picked = [1, 2, 3]

function recordFailure(name, detail) {
  failures.push({ name, detail, stage })
  console.error(`FAIL ${name}: ${JSON.stringify(detail)}`)
}
function assert(name, condition, detail = {}) {
  if (!condition) { recordFailure(name, detail); return false }
  passed.push(name)
  console.log(`PASS ${name}`)
  return true
}

function viewer() {
  if (identity === "anonymous") return null
  return {
    id: 1, nickname: "Browser Editor", email: "browser@example.invalid",
    superuser: identity === "editor", admin: identity !== "blocked",
    caps: identity === "blocked" ? [] : identity === "contributor"
      ? ["admin.enter", "articles.publish_own", "images.contribute"]
      : ["admin.enter", "articles.edit_any", "articles.edit_author", "articles.publish_own", "article_categories.manage", "site_pages.manage", "images.manage", "images.contribute", "scrims.manage"],
    email_verified: true, is_sjtu: false, can_submit_article: true, can_comment: true,
    avatar_image_id: null, default_avatar_image_id: null, profile_gaps: [], waiting_letters: 0,
  }
}
function navigation() {
  const tab = (key, label, url) => ({ key, label, url, count: 0, tabs: [] })
  const tabs = [tab("articles", "文章", "/admin/articles/"), tab("images", "图片", "/admin/images/")]
  if (identity === "editor") tabs.push(tab("categories", "分类", "/admin/categories/"), tab("pages", "网站页面", "/admin/pages/"))
  const sections = [{ key: "content", label: "内容", url: "/admin/articles/", tabs }]
  if (identity === "editor") sections.push({ key: "events", label: "活动", url: "/admin/scrims/8/split/", tabs: [tab("scrims", "内战", "/admin/scrims/8/split/")] })
  return { sections }
}
function article() {
  return {
    id: 1, kind: "article", ...editorDraft, draft_title: editorDraft.title,
    live: false, has_unpublished_changes: true,
    first_published_at: null, last_published_at: null, live_revision_id: null,
    latest_revision_id: 12, owner_id: 1, version: articleVersion,
    created_at: now, updated_at: now, category_name: "Fixture category",
    author_name: "Browser Editor", body_html: "", body_plain: editorDraft.body_md,
    char_count: editorDraft.body_md.length, reading_time: 1, search_text: "", renderer_version: 1,
  }
}
function articleDetail() {
  return {
    article: article(), revision: { ...editorDraft }, version: articleVersion,
    capabilities: { edit: true, publish: true, unpublish: false, delete: true, announce: false, edit_author: true, edit_schedule: true },
    guide: false, categories: [{ id: 1, name: "Fixture category", allow_submission: true }],
    authors: [{ id: 1, nickname: "Browser Editor" }], tournaments: [],
    preview_url: "/api/admin/articles/1/preview", announced: 0, verdict: null,
  }
}
function scrimBoard() {
  const signups = placements.map(placement => ({
    ...placement, assigned_role: placement.role,
    user_id: placement.signup_id + 100, nickname: `Member ${placement.signup_id}`,
    battletag: `Fixture${placement.signup_id}#1234`, roles: ["tank", "damage", "support"],
    ratings: { tank: 10, damage: 20, support: 30 }, rank_text: { tank: "白银 5", damage: "钻石 5", support: "宗师 5" },
    best_rating: 30, is_selected: picked.includes(placement.signup_id), rating_used: placement.role ? 10 : null,
    is_active: true, is_sjtu: false, created_at: now,
  }))
  return {
    scrim: { id: 8, title: "Browser scrim", description: "Fixture", starts_at: now, signup_closes_at: null, format: "rq_5v5", sjtu_only: false, status: "published", version: 3, board_version: boardVersion, created_at: now, updated_at: now, default_cover_image_id: null },
    order: "created", signups, selected_count: picked.length, needed: 10,
    teams: ["a", "b"].map(team => ({ team, label: team === "a" ? "A 队" : "B 队", total: 10, problems: [], members: signups.filter(signup => signup.team === team) })),
    bench: signups.filter(signup => signup.is_selected && !signup.team),
    gap: 0, has_teams: true, teams_stale: false, copy_text: "Fixture confirmed placements", board_version: boardVersion, show_contacts: false,
  }
}
const htmlEscape = text => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
function mockResponse(url, method, body) {
  const path = url.pathname
  const json = value => ({ status: 200, type: "application/json", body: JSON.stringify(value) })
  const intentionalError = (status, message) => {
    expectedNetworkErrors.add(url.href)
    return { status, type: "application/json", body: JSON.stringify({ error: { code: status === 401 ? "unauthorized" : status === 403 ? "forbidden" : "not_found", message } }) }
  }
  if (path === "/api/session") return json({ user: viewer(), flash: "", font_css_path: "" })
  if (path === "/api/admin/navigation") return json(navigation())
  if (method === "PATCH" && expireWrites) return intentionalError(401, "登录已失效，请重新登录。")
  if (path === "/api/admin/categories") {
    if (identity === "contributor") return intentionalError(403, "没有权限做这件事")
    return json({ items: [{ id: 1, name: "Fixture category", slug: "fixture", description: "", sort_order: 0, allow_submission: true, version: 1, article_count: 0, created_at: now, updated_at: now }] })
  }
  if (path === "/api/admin/articles") return json({ items: [article()], total: 1, page: 1, page_size: 25 })
  if (path === "/api/admin/articles/1") return json(articleDetail())
  if (path === "/api/admin/articles/404") return intentionalError(404, "文章不存在")
  if (path === "/api/admin/articles/new") return json({ ...articleDetail(), article: null, version: 0, revision: { ...editorDraft, title: "", body_md: "" } })
  if (path === "/api/articles/1" && method === "PATCH") {
    if (body.base_version !== articleVersion) {
      return { status: 409, type: "application/json", body: JSON.stringify({ error: { code: "stale", message: "Fixture version mismatch" }, current: { version: articleVersion, values: editorDraft } }) }
    }
    editorDraft = { ...editorDraft, ...body.changes }
    articleVersion++
    return json({ version: articleVersion, saved: Object.keys(body.changes), fields: {}, values: editorDraft, saved_at: now })
  }
  if (path === "/api/admin/image-collections") return json({ collections })
  if (path === "/api/admin/images") return json({ items: images, total: images.length, page: 1, page_size: 48 })
  if (path === "/api/admin/images/upload" && method === "POST") {
    const image = { ...images[0], id: nextImage++, title: body.title, file_name: body.file_name }
    images.push(image)
    return json({ image })
  }
  if (/^\/api\/images\/\d+$/.test(path)) return json(images.find(image => image.id === Number(path.split("/").at(-1))) || images[0])
  if (path === "/api/admin/markdown/preview") return json({ preview_url: "/api/admin/previews/browser-fixture" })
  if (path.startsWith("/api/admin/previews/") || path === "/api/admin/articles/1/preview") {
    return { status: 200, type: "text/html", policy: "default-src 'none'; style-src 'self'; frame-ancestors 'self'; sandbox", body: `<!doctype html><html><head><title>Fixture preview</title></head><body><h1>Fixture preview</h1><p>${htmlEscape(editorDraft.body_md)}</p></body></html>` }
  }
  if (path === "/api/admin/scrims/8/board" && method === "GET") return json(scrimBoard())
  if (path === "/api/admin/scrims/8/board/teams" && method === "POST") {
    placements = body.placements.map(placement => ({ signup_id: placement.signup_id, team: placement.team, role: placement.role }))
    boardVersion++
    return json(scrimBoard())
  }
  if (path === "/api/admin/scrims/8/board/selection" && method === "POST") {
    picked = body.signup_ids
    boardVersion++
    return json(scrimBoard())
  }
  // A missing fixture is a test failure, never a fake successful object.
  recordFailure("unexpected fixture endpoint", { method, path })
  return { status: 501, type: "application/json", body: JSON.stringify({ error: { code: "missing_fixture", message: "Unexpected browser-check API" } }) }
}

async function localServer(upstreamBase) {
  const dist = join(appRoot, "dist")
  if (!upstreamBase && !existsSync(join(dist, "index.html"))) throw new Error("Build admin production dist before browser-check")
  const types = { ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2", ".woff": "font/woff", ".ttf": "font/ttf", ".otf": "font/otf", ".html": "text/html" }
  server = createServer(async (request, response) => {
    const id = ++httpSequence
    const entry = { id, method: request.method, path: request.url, stage, started: Date.now() }
    httpPending.set(id, entry)
    response.on("finish", () => {
      httpPending.delete(id)
      trace(httpTrace, { ...entry, status: response.statusCode, elapsedMs: Date.now() - entry.started })
    })
    response.on("close", () => { httpPending.delete(id) })
    response.setHeader("Content-Security-Policy", policy)
    response.setHeader("X-Content-Type-Options", "nosniff")
    response.setHeader("Cache-Control", "no-store")
    try {
      const url = new URL(request.url, `http://${request.headers.host}`)
      let path
      try { path = decodeURIComponent(url.pathname) } catch { response.writeHead(400); response.end(); return }
      if (path.startsWith("/api/")) {
        let input = ""
        for await (const chunk of request) {
          input += chunk
          if (input.length > 8 * 1024 * 1024) throw new Error("Browser fixture body exceeds limit")
        }
        const body = input ? JSON.parse(input) : {}
        requests.push({ stage, method: request.method, path: url.pathname, body, key: request.headers["idempotency-key"] || "" })
        const result = mockResponse(url, request.method, body)
        response.statusCode = result.status
        response.setHeader("Content-Type", result.type)
        if (result.policy) response.setHeader("Content-Security-Policy", result.policy)
        response.end(result.body)
        return
      }
      if (path.startsWith("/media/r/")) {
        response.setHeader("Content-Type", "image/png")
        response.end(Buffer.from(png, "base64"))
        return
      }
      // Never forward writes or API calls to a supplied Go/site origin.
      if (request.method !== "GET" && request.method !== "HEAD") {
        response.writeHead(405); response.end("Only fixture API writes are allowed"); return
      }
      if (path === "/favicon.ico") { response.writeHead(204); response.end(); return }
      if (upstreamBase) {
        const target = new URL(upstreamBase)
        target.pathname = path
        target.search = url.search
        const upstream = await fetch(target, { method: request.method, redirect: "manual", signal: AbortSignal.timeout(10000) })
        response.statusCode = upstream.status
        for (const name of ["content-type", "content-security-policy", "x-content-type-options", "x-frame-options"]) {
          const value = upstream.headers.get(name)
          if (value) response.setHeader(name, value)
        }
        const location = upstream.headers.get("location")
        if (location) {
          const redirected = new URL(location, target)
          if (redirected.origin !== target.origin) throw new Error("Cross-origin fixture asset redirect")
          response.setHeader("Location", redirected.pathname + redirected.search)
        }
        response.end(Buffer.from(await upstream.arrayBuffer()))
        return
      }
      if (path.startsWith("/accounts/login/")) {
        response.setHeader("Content-Type", "text/html")
        const shell = readFileSync(join(dist, "index.html"), "utf8")
        const styles = (shell.match(/<link\b[^>]*>/g) || []).filter(link => /rel=["']stylesheet["']/.test(link)).join("")
        response.end(`<!doctype html><html><head><title>Fixture login</title>${styles}</head><body><h1>Fixture login</h1></body></html>`)
        return
      }
      let file = path === "/theme.js" ? (existsSync(join(dist, "theme.js")) ? join(dist, "theme.js") : join(repoRoot, "web/apps/site/public/theme.js"))
        : path.startsWith("/static/") ? resolve(repoRoot, path.slice(1))
        : resolve(dist, path.replace(/^\/admin\/?/, ""))
      const allowed = file.startsWith(dist + sep) || file.startsWith(join(repoRoot, "static") + sep) || file === join(repoRoot, "web/apps/site/public/theme.js")
      if (!allowed) { response.writeHead(403); response.end(); return }
      if (!existsSync(file) || !statSync(file).isFile()) {
        if (path.startsWith("/admin/") && !extname(path)) file = join(dist, "index.html")
        else { response.writeHead(404); response.end(); return }
      }
      const type = types[extname(file)]
      if (!type) { response.writeHead(404); response.end(); return }
      response.setHeader("Content-Type", type)
      response.end(readFileSync(file))
    } catch (error) {
      recordFailure("fixture HTTP request failed", { method: request.method, path: request.url, error: String(error) })
      if (!response.headersSent) response.writeHead(500)
      response.end("Browser fixture request failed")
    }
  })
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve))
  return `http://127.0.0.1:${server.address().port}`
}

async function main() {
  console.log("ADMIN-BROWSER-CHECK STUB-API: production Vue/CodeMirror/Sortable; fictional local fixture API. No real Go write validation.")
  base = await localServer(givenBase)
  const document = await fetch(base + "/admin/articles/1/", { signal: AbortSignal.timeout(10000) })
  const header = document.headers.get("content-security-policy") || ""
  await document.arrayBuffer()
  assert("parent strict CSP header", header.includes("script-src 'self'") && header.includes("style-src 'self'") && !header.includes("unsafe-inline") && !header.includes("unsafe-eval"), { header })
  profile = mkdtempSync(join(tmpdir(), "sjtuow-admin-browser-"))
  // Size both the native window and screen to fit the board drag endpoints.
  // CSS viewport emulation alone does not resize the native drag surface.
  browser = spawn(chromium, ["--headless=new", "--no-proxy-server", "--proxy-bypass-list=*", "--no-sandbox", "--no-first-run", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--window-size=1280,1800", "--ozone-override-screen-size=1280,1800", "about:blank"], { stdio: ["ignore", "pipe", "pipe"] })
  for (const [name, stream] of [["stdout", browser.stdout], ["stderr", browser.stderr]]) {
    stream.on("data", chunk => trace(browserLog, { stream: name, text: chunk.toString().slice(-3000) }))
  }
  browser.on("error", error => trace(browserLog, { error: String(error) }))
  browser.on("exit", (code, signal) => trace(browserLog, { exit: code, signal }))
  let debugPort
  for (let attempt = 0; attempt < 100 && !debugPort; attempt++) {
    if (existsSync(join(profile, "DevToolsActivePort"))) debugPort = Number(readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0])
    if (!debugPort) await sleep(100)
  }
  if (!debugPort) throw new Error("Chromium did not publish DevToolsActivePort")
  const pages = await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json()
  const target = pages.find(page => page.type === "page")
  if (!target) throw new Error("Chromium has no page target")
  socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.addEventListener("open", resolve, { once: true }); socket.addEventListener("error", reject, { once: true }) })
  let sequence = 0
  let dragData = null
  const commands = new Map()
  const messages = []
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence
    const detail = params.url || params.requestId || params.expression?.slice(0, 180) || ""
    // Fresh Chromium startup may exceed 15 seconds on the test host.
    // Bound only the initial navigation at 60 seconds; later CDP stays strict.
    const commandTimeout = method === "Page.navigate" && stage === "editor load" ? 60000 : 15000
    const timer = setTimeout(() => {
      diagnostics(`CDP timeout: ${method}`)
      commands.delete(id)
      reject(new Error(`CDP command timed out: ${method}`))
    }, commandTimeout)
    commands.set(id, { resolve, reject, timer, method, detail, started: Date.now() })
    socket.send(JSON.stringify({ id, method, params }))
  })
  protocolDiagnostics = () => ({ pending: [...commands.entries()].map(([id, command]) => ({ id, method: command.method, detail: command.detail, elapsedMs: Date.now() - command.started })) })
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data)
    if (message.id) {
      const command = commands.get(message.id)
      if (!command) return
      clearTimeout(command.timer); commands.delete(message.id)
      if (message.error) command.reject(new Error(`${message.error.message}`))
      else command.resolve(message.result)
    } else if (message.method === "Input.dragIntercepted") dragData = message.params.data
    else if (message.method === "Page.javascriptDialogOpening") void send("Page.handleJavaScriptDialog", { accept: true }).catch(error => recordFailure("controlled fixture dialog", String(error)))
    else {
      messages.push({ ...message, stage, probe: probeActive })
      trace(protocolTrace, { method: message.method, stage, url: message.params?.request?.url || message.params?.frame?.url || message.params?.entry?.url || "", text: message.params?.entry?.text || message.params?.exceptionDetails?.text || "" })
    }
  })
  const evaluate = async expression => {
    const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result?.value
  }
  const waitFor = async (expression, timeout = 12000) => {
    const deadline = Date.now() + timeout
    while (Date.now() < deadline) {
      try { const result = await evaluate(expression); if (result) return result } catch {}
      await sleep(80)
    }
    diagnostics(`DOM wait timeout: ${expression.slice(0, 180)}`)
    throw new Error(`Timed out waiting for: ${expression}`)
  }
  const navigate = async path => {
    const previous = await evaluate("window.__adminDocumentMarker").catch(() => null)
    await send("Page.navigate", { url: base + path })
    await waitFor(`document.readyState === 'complete' && document.querySelector('h1') && window.__adminDocumentMarker !== ${JSON.stringify(previous ?? null)}`)
    await sleep(150)
  }
  const button = text => evaluate(`(() => {const button = [...document.querySelectorAll('button')].find(node => node.textContent.trim() === ${JSON.stringify(text)});if (!button) return false;button.click();return true})()`)
  const key = async (name, code, modifiers = 0, number = 0) => {
    await send("Input.dispatchKeyEvent", { type: "keyDown", key: name, code, modifiers, windowsVirtualKeyCode: number })
    await send("Input.dispatchKeyEvent", { type: "keyUp", key: name, code, modifiers, windowsVirtualKeyCode: number })
  }
  const quiet = async name => {
    await sleep(100)
    const bad = messages.filter(message => message.stage === stage && !message.probe).filter(message => {
      if (message.method === "Runtime.exceptionThrown") return true
      if (message.method === "Runtime.consoleAPICalled") return ["error", "assert"].includes(message.params.type)
      if (message.method === "Log.entryAdded") {
        const entry = message.params.entry
        if (entry.source === "security") return true
        return entry.level === "error" && !(entry.source === "network" && expectedNetworkErrors.has(entry.url))
      }
      return false
    })
    const violations = await evaluate("window.__adminCsp || []")
    assert(name, bad.length === 0 && violations.length === 0, { messages: bad.map(message => message.params), violations })
  }
  await send("Runtime.enable")
  await send("Log.enable")
  await send("Page.enable")
  await send("Network.enable")
  await send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__adminCsp=[]; window.__adminDocumentMarker=Math.random(); document.addEventListener('securitypolicyviolation',event=>window.__adminCsp.push({directive:event.violatedDirective,blocked:event.blockedURI}));" })

  stage = "editor load"
  await navigate("/admin/articles/1/")
  await waitFor("[...document.querySelectorAll('*')].some(node => node.shadowRoot?.querySelector('.cm-content'))")
  const editor = await evaluate(`(() => { const host = [...document.querySelectorAll('*')].find(node => node.shadowRoot?.querySelector('.cm-content'));const content = host.shadowRoot.querySelector('.cm-content');return {adopted:host.shadowRoot.adoptedStyleSheets.length,editable:content.contentEditable,minHeight:getComputedStyle(host.shadowRoot.querySelector('.cm-editor')).minHeight,body:content.textContent,title:document.title}})()`)
  assert("CodeMirror loaded in ShadowRoot with adopted styles", editor.adopted > 0 && editor.editable === "true" && editor.minHeight !== "0px", editor)
  await quiet("editor has zero console errors and CSP violations")

  stage = "Markdown toolbar and keyboard"
  await evaluate("[...document.querySelectorAll('*')].find(node=>node.shadowRoot?.querySelector('.cm-content')).shadowRoot.querySelector('.cm-content').focus()")
  await key("a", "KeyA", 2, 65)
  await send("Input.insertText", { text: "Browser body" })
  await key("a", "KeyA", 2, 65)
  assert("bold toolbar button exists", await button("加粗"))
  await waitFor("[...document.querySelectorAll('*')].find(node=>node.shadowRoot?.querySelector('.cm-content')).shadowRoot.querySelector('.cm-content').textContent.includes('**Browser body**')")
  await key("i", "KeyI", 2, 73)
  await waitFor("[...document.querySelectorAll('*')].find(node=>node.shadowRoot?.querySelector('.cm-content')).shadowRoot.querySelector('.cm-content').textContent.includes('*Browser body*')")
  await waitFor(`document.querySelector('[data-autosave-status]')?.textContent.includes('已保存')`)
  assert("Markdown keyboard changes reached stub autosave", requests.some(request => request.path === "/api/articles/1" && request.body.changes?.body_md?.includes("Browser body")))
  await quiet("Markdown toolbar/keyboard stays under CSP")

  stage = "image picker and upload"
  assert("cover picker opens", await button("选择"))
  await waitFor("document.querySelector('dialog[open] input[type=file]')")
  const focus = await evaluate("({dialog:document.querySelector('dialog[open]')?.getAttribute('aria-labelledby'),focused:document.activeElement?.type})")
  assert("native image dialog focuses search", focus.focused === "search", focus)
  await evaluate(`(() => {const input=document.querySelector('dialog[open] input[type=file]');const bytes=Uint8Array.from(atob(${JSON.stringify(png)}),char=>char.charCodeAt(0));const file=new File([bytes],'browser-fixture.png',{type:'image/png'});const data=new DataTransfer();data.items.add(file);input.files=data.files;input.dispatchEvent(new Event('change',{bubbles:true}))})()`)
  assert("upload and choose button exists", await button("上传并选用"))
  await waitFor("!document.querySelector('dialog[open]') && document.querySelector('input[name=cover_image_id]')?.value === '8'")
  await waitFor(`document.querySelector('[data-autosave-status]')?.textContent.includes('已保存')`)
  const upload = requests.find(request => request.path === "/api/admin/images/upload")
  assert("image upload reached controlled API with stable request key", upload?.body.data_url?.startsWith("data:image/png;base64,") && Boolean(upload.key), upload && { path: upload.path, file: upload.body.file_name, keyPresent: Boolean(upload.key) })
  const selected = await evaluate("({cover:document.querySelector('input[name=cover_image_id]')?.value,focused:document.activeElement?.textContent?.trim()})")
  assert("uploaded image is selected and focus restored", selected.cover === "8" && selected.focused === "选择", selected)
  await quiet("image dialog and upload have zero CSP violations")

  stage = "theme and internal navigation"
  await evaluate("document.querySelector('details.c-theme').open=true")
  await button("深色")
  await waitFor("document.documentElement.getAttribute('data-theme') === 'dark' && localStorage.getItem('ow-theme') === 'dark'")
  const theme = await evaluate("({theme:document.documentElement.getAttribute('data-theme'),stored:localStorage.getItem('ow-theme'),closed:!document.querySelector('details.c-theme').open})")
  assert("admin dark theme persists and closes menu", theme.theme === "dark" && theme.stored === "dark" && theme.closed, theme)
  await evaluate("document.querySelector('details.c-theme').open=true")
  await button("跟随系统")
  const marker = await evaluate("window.__adminDocumentMarker")
  // Editing hides list tabs while showing its real return link. Exercise that
  // link first, then the image tab; neither step may replace the SPA document.
  await evaluate("document.querySelector('a[href=\"/admin/articles/\"]').click()")
  await waitFor("location.pathname === '/admin/articles/' && document.querySelector('nav.b-tabs a[href=\"/admin/images/\"]')")
  await evaluate("document.querySelector('nav.b-tabs a[href=\"/admin/images/\"]').click()")
  await waitFor("location.pathname === '/admin/images/' && document.querySelector('h1')?.textContent === '图片'")
  assert("plain internal admin link uses SPA navigation", marker === await evaluate("window.__adminDocumentMarker"))
  await quiet("theme and SPA navigation remain error-free")

  stage = "Sortable board"
  await navigate("/admin/scrims/8/split/")
  await waitFor("document.querySelector('[data-split-board] [data-signup=\"1\"]')")
  await sleep(400)
  assert("Sortable binds real zone instances", await evaluate("Object.keys(document.querySelector('[data-board-zone]')).some(key => key.startsWith('Sortable'))"))
  await evaluate("document.querySelector('[data-signup=\"1\"]').focus()")
  await key("ArrowDown", "ArrowDown", 1, 40)
  await waitFor("document.querySelector('[data-board-zone=buffer] [data-signup=\"1\"]')")
  await waitFor("document.querySelector('[data-autosave-status]')?.textContent.includes('已保存')")
  assert("board keyboard move reaches stub persistence", placements.find(value => value.signup_id === 1)?.team === "")
  await evaluate("document.querySelector('[data-signup=\"1\"]').scrollIntoView({block:'center',behavior:'instant'})")
  await evaluate("document.fonts.ready.then(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))")
  await send("Input.setInterceptDrags", { enabled: true })
  dragData = null
  const coords = await evaluate("(() => {const from=document.querySelector('[data-signup=\"1\"] [data-drag-handle]').getBoundingClientRect();const to=document.querySelector('[data-board-zone=\"a:tank\"]')?.getBoundingClientRect() || document.querySelector('[data-team-panel=a] [data-board-zone]')?.getBoundingClientRect();return {from:{x:from.x+from.width/2,y:from.y+from.height/2},to:to?{x:to.x+to.width/2,y:to.y+Math.max(5,to.height/2)}:null}})()")
  const viewport = await evaluate("({width:innerWidth,height:innerHeight,screenWidth:screen.width,screenHeight:screen.height})")
  assert("Sortable drag endpoints are inside the browser viewport", !!coords.to && [coords.from,coords.to].every(point => point.x > 0 && point.x < Math.min(viewport.width,viewport.screenWidth) && point.y > 0 && point.y < Math.min(viewport.height,viewport.screenHeight)), {coordinates:coords,viewport})
  if (coords.to) {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: coords.from.x, y: coords.from.y })
    await send("Input.dispatchMouseEvent", { type: "mousePressed", button: "left", buttons: 1, clickCount: 1, x: coords.from.x, y: coords.from.y })
    for (let part = 1; part <= 12; part++) {
      await send("Input.dispatchMouseEvent", { type: "mouseMoved", button: "left", buttons: 1, x: coords.from.x + (coords.to.x - coords.from.x) * part / 12, y: coords.from.y + (coords.to.y - coords.from.y) * part / 12 })
      await sleep(25)
    }
    if (dragData) {
      await send("Input.dispatchDragEvent", { type: "dragEnter", x: coords.to.x, y: coords.to.y, data: dragData })
      await send("Input.dispatchDragEvent", { type: "dragOver", x: coords.to.x, y: coords.to.y, data: dragData })
      await send("Input.dispatchDragEvent", { type: "drop", x: coords.to.x, y: coords.to.y, data: dragData })
    }
    await send("Input.dispatchMouseEvent", { type: "mouseReleased", button: "left", buttons: 0, clickCount: 1, x: coords.to.x, y: coords.to.y })
    await sleep(200)
    assert("Sortable pointer drag returns card to A team", await evaluate("!!document.querySelector('[data-team-panel=a] [data-signup=\"1\"]')"), { coordinates: coords })
    await waitFor("document.querySelector('[data-autosave-status]')?.textContent.includes('已保存')")
  } else recordFailure("Sortable target zone missing", coords)
  await send("Input.setInterceptDrags", { enabled: false })
  await quiet("Sortable keyboard/pointer behavior stays under strict CSP")

  stage = "permissions and 404"
  identity = "contributor"
  await navigate("/admin/articles/")
  const permitted = await evaluate("[...document.querySelectorAll('nav.b-tabs a')].map(node=>node.getAttribute('href'))")
  assert("contributor navigation omits forbidden categories and pages", permitted.includes("/admin/articles/") && permitted.includes("/admin/images/") && !permitted.includes("/admin/categories/") && !permitted.includes("/admin/pages/"), permitted)
  await navigate("/admin/categories/")
  await waitFor("document.querySelector('h1')?.textContent === '没有权限'")
  assert("direct forbidden page displays 403 without private rows", await evaluate("!document.querySelector('tbody tr')"))
  assert("forbidden page is the standalone scriptless document", await evaluate("document.querySelector('.code')?.textContent==='403' && document.scripts.length===0"))
  await quiet("permission handling produces no runtime or CSP errors")
  await navigate("/admin/articles/404/")
  await waitFor("document.querySelector('h1')?.textContent === '页面不存在'")
  assert("missing article stays a 404 state", await evaluate("!document.querySelector('input[name=title]')"))
  await navigate("/admin/does-not-exist/")
  await waitFor("document.querySelector('h1')?.textContent.includes('页面不存在')")
  assert("unknown SPA route has explicit 404", true)
  await quiet("404 states do not throw or violate CSP")

  stage = "entry permission and anonymous redirect"
  identity = "blocked"
  await navigate("/admin/articles/")
  await waitFor("location.pathname === '/admin/articles/' && document.querySelector('h1')?.textContent.includes('权限')")
  assert("user without admin.enter receives explicit forbidden entry", await evaluate("!document.querySelector('input[name=title]')"))
  await quiet("blocked entry has no runtime or CSP errors")
  identity = "anonymous"
  await navigate("/admin/articles/")
  await waitFor("location.pathname.startsWith('/accounts/login/')")
  assert("anonymous entry redirects to login with admin next", await evaluate("new URL(location.href).searchParams.get('next') === '/admin/articles/'"))
  await quiet("anonymous login redirect has no uncaught exceptions")

  stage = "expired session"
  identity = "editor"
  await navigate("/admin/articles/1/")
  await waitFor("document.querySelector('input[name=title]')")
  expireWrites = true
  await evaluate("(() => {const input=document.querySelector('input[name=title]');input.value='Expired attempt';input.dispatchEvent(new Event('input',{bubbles:true}))})()")
  await waitFor("document.querySelector('a[href^=\"/accounts/login/?next=\"]')")
  assert("autosave 401 asks for login and retains draft", await evaluate("document.querySelector('input[name=title]').value === 'Expired attempt'"))
  await quiet("401 UI produces no uncaught exceptions or CSP violations")
  expireWrites = false

  stage = "CSP negative probe"
  // Deliberate forbidden nodes prove the header is enforced, not just present.
  // These exact security log events are excluded only during this probe.
  probeActive = true
  const probe = await evaluate(`(async()=>{window.__adminCsp=[];const plain=document.createElement('div');const styled=document.createElement('div');plain.id='csp-plain';styled.id='csp-styled';document.body.append(plain,styled);styled.setAttribute('style','color:rgb(255,0,0)');const script=document.createElement('script');script.id='csp-script';script.textContent='window.__adminInlineRan=true';document.body.append(script);await new Promise(resolve=>setTimeout(resolve,150));const result={ran:!!window.__adminInlineRan,plain:getComputedStyle(plain).color,styled:getComputedStyle(styled).color,violations:window.__adminCsp};plain.remove();styled.remove();script.remove();window.__adminCsp=[];return result})()`)
  assert("CSP rejects both inline script and inline style attribute", !probe.ran && probe.plain === probe.styled && probe.violations.length === 2 && probe.violations.some(value => value.directive.startsWith("script-src")) && probe.violations.some(value => value.directive.startsWith("style-src")), probe)
  await sleep(100)
  probeActive = false
  console.log(JSON.stringify({ mode: "STUB-API", passed: passed.length, failures, requestCount: requests.length, realGoPersistenceVerified: false }))
}

try { await main() }
catch (error) { diagnostics(`browser-check aborted: ${error}`); recordFailure("browser-check aborted", String(error)) }
finally {
  try { socket?.close() } catch {}
  if (browser && browser.exitCode === null && browser.signalCode === null) {
    browser.kill("SIGTERM")
    await Promise.race([new Promise(resolve => browser.once("exit", resolve)), sleep(2000)])
    if (browser.exitCode === null && browser.signalCode === null) {
      browser.kill("SIGKILL")
      await Promise.race([new Promise(resolve => browser.once("exit", resolve)), sleep(1000)])
    }
  }
  if (server) await new Promise(resolve => server.close(resolve))
  if (profile && (!browser || browser.exitCode !== null || browser.signalCode !== null)) rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
}
console.log(failures.length ? "ADMIN-BROWSER-CHECK-FAILED STUB-API" : "ADMIN-BROWSER-CHECK-OK STUB-API")
process.exitCode = failures.length ? 1 : 0
