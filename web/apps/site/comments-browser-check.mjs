// Real Chromium + the production SSR build. The temporary API mirrors Go's
// comment JSON and records writes; no production database or email is used.
import { createServer, request } from "node:http"
import { spawn } from "node:child_process"
import { mkdtempSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath } from "node:url"

const site = fileURLToPath(new URL(".", import.meta.url))
const chrome = process.argv[2] ?? "/usr/bin/chromium"
const children = [], servers = [], events = [], checks = []
const pause = (ms) => new Promise((r) => setTimeout(r, ms))
const user = { id: 7, nickname: "测试成员", email: "review@example.test", admin: true, superuser: false, caps: ["comments.moderate"], email_verified: true, is_sjtu: true, can_comment: true }
const makeComment = (id, article, content) => ({ id, article_id: article, user_id: 7, author_name: "测试成员", content, is_pinned: false, is_hidden: false, is_deleted: false, like_count: 0, liked_by_me: false, version: 1, created_at: "2026-10-10T12:00:00Z", updated_at: "2026-10-10T12:00:00Z", replies: [] })
function fixture(options = {}) {
  const rows = Array.from({ length: options.count ?? 21 }, (_, i) => makeComment(100 + i, 1, `A comment ${i + 1}`))
  if (rows.length) rows[0].replies = [makeComment(150, 1, "A reply")]
  return { rows: { 1: rows, 2: [makeComment(200, 2, "B comment only")] }, user: options.visitor ? null : user, nextId: 300, writes: [], reads: [], writeStatus: 200, writeDelay: 0, readDelay: 0, failNextRead: false, failRefresh: false, ...options }
}
let state = fixture()
const article = (slug) => ({ id: slug === "a" ? 1 : 2, slug, title: `Article ${slug.toUpperCase()}`, category_name: "攻略", summary: "测试正文", body_html: "<p>Public body</p>", char_count: 10, reading_time: 1, author_name: "测试成员", comments_enabled: true, first_published_at: "2026-10-10T12:00:00Z", headings: [] })
async function serve(handler) {
  const server = createServer(handler)
  servers.push(server)
  await new Promise((r) => server.listen(0, "127.0.0.1", r))
  return server.address().port
}
async function reservePort() { const port = await serve((q, r) => r.end()); await new Promise((r) => servers.pop().close(r)); return port }
let ws, evaluate, send, base
function check(name, actual, valid) {
  checks.push({ name, passed: !!valid, actual })
  console.log(`${valid ? "PASS" : "FAIL"} ${name}: ${JSON.stringify(actual)}`)
}
try {
  const apiPort = await serve(async (req, res) => {
    const current = state
    const url = new URL(req.url, "http://fixture")
    let raw = ""; for await (const chunk of req) raw += chunk
    const body = raw ? JSON.parse(raw) : {}
    const json = (data, status = 200) => { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(data)) }
    if (req.method !== "GET") {
      current.writes.push({ method: req.method, path: url.pathname, body, key: req.headers["idempotency-key"] })
      await pause(current.writeDelay)
      if (current.writeStatus !== 200) { json({ error: { code: "invalid", message: "测试提交失败，请保留正文。" }, fields: { content: ["测试拒绝"] } }, current.writeStatus); return }
      const create = /^\/api\/articles\/(\d+)\/comments$/.exec(url.pathname)
      const action = /^\/api\/comments\/(\d+)(?:\/(like|hide|pin))?$/.exec(url.pathname)
      if (create) {
        const id = Number(create[1]), created = makeComment(++current.nextId, id, body.content)
        if (body.parent_id) {
          const parent = current.rows[id].find((c) => c.id === body.parent_id || c.replies.some((r) => r.id === body.parent_id))
          parent.replies.push(created)
        } else current.rows[id].unshift(created)
      } else if (action) {
        const id = Number(action[1]), rows = Object.values(current.rows).flat()
        const comment = rows.flatMap((c) => [c, ...c.replies]).find((c) => c.id === id)
        if (req.method === "DELETE") {
          for (const key of Object.keys(current.rows)) current.rows[key] = current.rows[key].filter((c) => c.id !== id)
          for (const c of rows) c.replies = c.replies.filter((r) => r.id !== id)
        } else if (req.method === "PATCH") comment.content = body.content
        else if (action[2] === "like") { comment.liked_by_me = !comment.liked_by_me; comment.like_count = comment.liked_by_me ? 1 : 0 }
        else if (action[2] === "hide") comment.is_hidden = body.hidden
        else if (action[2] === "pin") comment.is_pinned = body.pinned
      }
      if (current.failRefresh) current.failNextRead = true
      json({ result: "ok" }); return
    }
    if (url.pathname === "/api/session") { json({ user: current.user }); return }
    if (url.pathname === "/api/page/home") { json({ stats: { member_count: 1, team_count: 0, scrims_held: 0 }, scrims: [], news: [], notices: [], teams: [] }); return }
    if (url.pathname === "/api/me/agenda") { json({ items: [] }); return }
    const art = /^\/api\/page\/news\/(a|b)$/.exec(url.pathname)
    if (art) { json(article(art[1])); return }
    const list = /^\/api\/articles\/(\d+)\/comments$/.exec(url.pathname)
    if (list) {
      const id = Number(list[1]), page = Number(url.searchParams.get("page") ?? 1), sort = url.searchParams.get("sort") ?? "new"
      current.reads.push({ id, page, sort })
      if (current.failNextRead) { current.failNextRead = false; json({ error: { code: "unavailable", message: "测试列表暂不可用" } }, 503); return }
      const rows = sort === "top" ? [...current.rows[id]].reverse() : current.rows[id]
      // Snapshot before delaying: the old response genuinely contains old data.
      const result = JSON.parse(JSON.stringify({ total: rows.length, page, page_size: 20, comments: rows.slice((page - 1) * 20, page * 20) }))
      if (id === 1) await pause(current.readDelay)
      json(result); return
    }
    json({ error: { code: "not_found", message: "无此测试数据" } }, 404)
  })
  const ssrPort = await reservePort()
  const ssr = spawn(process.execPath, ["dist/server/server.js"], { cwd: site, env: { ...process.env, NODE_ENV: "production", STRICT_CSP: "1", PORT: String(ssrPort), API_BASE: `http://127.0.0.1:${apiPort}` }, stdio: ["ignore", "ignore", "inherit"] })
  children.push(ssr)
  const proxyPort = await serve((req, res) => {
    const up = request({ hostname: "127.0.0.1", port: req.url.startsWith("/api/") ? apiPort : ssrPort, path: req.url, method: req.method, headers: req.headers }, (reply) => { res.writeHead(reply.statusCode, reply.headers); reply.pipe(res) })
    up.on("error", () => { res.writeHead(502); res.end() }); req.pipe(up)
  })
  base = `http://127.0.0.1:${proxyPort}`
  for (let i = 0; i < 50; i++) { try { if ((await fetch(base + "/news/a/")).status === 200) break } catch {} await pause(100) }
  const debugPort = await reservePort()
  children.push(spawn(chrome, ["--headless=new", "--no-sandbox", "--no-first-run", `--remote-debugging-port=${debugPort}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "ow-comments-"))}`, "about:blank"], { stdio: "ignore" }))
  let targets
  for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json(); if (targets.some((t) => t.type === "page")) break } catch {} await pause(100) }
  ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl)
  await new Promise((r) => ws.onopen = r)
  let counter = 0; const pending = new Map()
  ws.onmessage = (m) => { const msg = JSON.parse(m.data); if (pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id) } else events.push(msg) }
  send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++counter, timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 30000)
    pending.set(id, (msg) => { clearTimeout(timer); resolve(msg) }); ws.send(JSON.stringify({ id, method, params }))
  })
  evaluate = async (expression) => {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })
    if (result.result?.exceptionDetails) throw new Error(JSON.stringify(result.result.exceptionDetails))
    return result.result?.result?.value
  }
  await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable")
  await send("Page.addScriptToEvaluateOnNewDocument", { source: "window.__confirmCalls=[]; window.__confirmResult=true; window.confirm=(m)=>{window.__confirmCalls.push(m);return window.__confirmResult;}; window.__violations=[]; document.addEventListener('securitypolicyviolation',e=>window.__violations.push(e.violatedDirective));" })
  async function wait(expression) { for (let i = 0; i < 100; i++) { if (await evaluate(expression).catch(() => false)) return; await pause(50) } throw new Error(`wait failed: ${expression}`) }
  async function open(path = "/news/a/", options = {}) {
    console.log(`CASE ${path} ${JSON.stringify(options)}`)
    state = fixture(options)
    await send("Page.navigate", { url: base + path })
    await wait("document.documentElement.classList.contains('js-ready') && !!document.querySelector('.c-comments')")
  }
  const topCount = () => evaluate("document.querySelectorAll('#comment-list > li.c-comment').length")
  const clickText = (id, text) => evaluate(`(()=>{const root=document.querySelector('#comment-${id}'); [...root.querySelectorAll('button')].find(b=>b.closest('.c-comment')===root && b.textContent.trim()===${JSON.stringify(text)}).click()})()`)
  async function fillAndSend(selector, text, twice = false) {
    await evaluate(`(()=>{const f=document.querySelector(${JSON.stringify(selector)});const t=f.querySelector('textarea');t.value=${JSON.stringify(text)};t.dispatchEvent(new Event('input',{bubbles:true}));const b=f.querySelector('button[type=submit]');b.click();${twice ? "b.click();" : ""}})()`)
  }
  const composer = "#slot-article-comments > .c-composer"
  const draft = () => evaluate(`document.querySelector(${JSON.stringify(composer)}).querySelector('textarea').value`)

  for (const count of [20, 21, 40, 41]) {
    await open("/news/a/", { count, visitor: true })
    const actual = { count: await topCount(), more: await evaluate("!!document.querySelector('#comments-more a')"), total: count }
    check(`visitor pagination ${count}`, actual, actual.count === Math.min(20, count) && actual.more === (count > 20))
  }
  await open("/news/a/?sort=top", { count: 41 })
  await evaluate("document.querySelector('#comments-more a').click()")
  await wait("document.querySelectorAll('#comment-list > li.c-comment').length === 40")
  check("load more keeps sort and first page", { reads: state.reads, count: await topCount() }, state.reads.at(-1).page === 2 && state.reads.at(-1).sort === "top")
  await evaluate("document.querySelector('#comments-more a').click()")
  await wait("document.querySelectorAll('#comment-list > li.c-comment').length === 41")
  check("last page removes load-more", { count: await topCount(), more: await evaluate("!!document.querySelector('#comments-more a')") }, !(await evaluate("!!document.querySelector('#comments-more a')")))

  await open()
  await clickText(101, "赞 0")
  await wait("document.querySelector('#comment-101 button[aria-pressed]').getAttribute('aria-pressed') === 'true'")
  await clickText(101, "已赞 1")
  await wait("document.querySelector('#comment-101 button[aria-pressed]').getAttribute('aria-pressed') === 'false'")
  check("top-level like and unlike", state.writes, state.writes.length === 2 && state.writes.every((w) => w.path === "/api/comments/101/like"))
  await evaluate("document.querySelector('#comment-100 > details.c-comment__thread').open=true")
  await clickText(150, "赞 0")
  await wait("document.querySelector('#comment-150 button[aria-pressed]').getAttribute('aria-pressed') === 'true'")
  check("reply like reaches the reply ID", state.writes.at(-1), state.writes.at(-1).path === "/api/comments/150/like")

  await evaluate("window.__confirmResult=false")
  const beforeCancel = state.writes.length
  await clickText(101, "删除"); await clickText(101, "隐藏")
  check("cancel confirmation has no write", { count: state.writes.length, messages: await evaluate("window.__confirmCalls") }, state.writes.length === beforeCancel)
  await evaluate("window.__confirmResult=true")
  await clickText(101, "隐藏")
  await wait("document.querySelector('#comment-101 .c-status')?.textContent==='已隐藏'")
  await clickText(101, "恢复")
  await wait("!document.querySelector('#comment-101 .c-status')")
  await clickText(101, "置顶")
  await wait("document.querySelector('#comment-101').classList.contains('is-pinned')")
  await clickText(101, "取消置顶")
  await wait("!document.querySelector('#comment-101').classList.contains('is-pinned')")
  check("moderation preserves action payloads", state.writes.slice(beforeCancel), state.writes.slice(beforeCancel).map((w) => w.body).every((b) => "hidden" in b || "pinned" in b))
  await clickText(101, "删除")
  await wait("!document.querySelector('#comment-101')")
  check("delete updates list and total", { count: await topCount(), header: await evaluate("document.querySelector('.c-cover__facts a[href=\"#comments\"]').textContent") }, (await topCount()) === 20 && state.writes.at(-1).method === "DELETE")
  await evaluate("document.querySelector('#comment-100 > details.c-comment__thread').open=true")
  await clickText(150, "隐藏")
  await wait("document.querySelector('#comment-150 .c-status')?.textContent==='已隐藏'")
  await clickText(150, "恢复")
  await wait("!document.querySelector('#comment-150 .c-status')")
  await clickText(150, "删除")
  await wait("!document.querySelector('#comment-150')")
  check("reply hide, restore and delete", state.writes.slice(-3), state.writes.slice(-3).every((w) => w.path.startsWith("/api/comments/150")))

  await open("/news/a/", { writeDelay: 300 })
  await fillAndSend(composer, "新评论", true)
  const busy = await evaluate(`({button:document.querySelector(${JSON.stringify(composer)}).querySelector('button').disabled,field:document.querySelector(${JSON.stringify(composer)}).querySelector('textarea').disabled})`)
  await wait(`document.querySelector(${JSON.stringify(composer)}).querySelector('textarea').value === ''`)
  check("slow submit sends once and clears only on success", { writes: state.writes, busy, draft: await draft() }, state.writes.length === 1 && busy.button && busy.field && (await draft()) === "")
  const counts = await evaluate("({section:document.querySelector('.c-comments__head h2').textContent,header:document.querySelector('.c-cover__facts a[href=\"#comments\"]').textContent})")
  check("header and section use live total", counts, counts.section.trim() === counts.header.trim())
  state.writeStatus = 422
  await fillAndSend(composer, "失败时保留")
  await wait(`!document.querySelector(${JSON.stringify(composer)}).querySelector('button').disabled`)
  check("failed submission keeps draft and error", { draft: await draft(), notice: await evaluate("document.querySelector('.c-toast')?.textContent") }, (await draft()) === "失败时保留" && (await evaluate("document.body.textContent.includes('测试提交失败')")))
  state.writeStatus = 200; state.failRefresh = true
  await fillAndSend(composer, "已保存但刷新失败")
  await wait(`document.querySelector(${JSON.stringify(composer)}).querySelector('textarea').value === ''`)
  check("saved write is acknowledged if reload fails", { writes: state.writes.length, notice: await evaluate("document.body.textContent.includes('操作已完成')") }, await evaluate("document.body.textContent.includes('操作已完成')"))

  await open()
  await evaluate("[...document.querySelectorAll('#comment-100 details > summary')].find(s=>s.textContent.trim()==='回复').parentElement.open=true")
  const replyComposer = "#comment-100 details:not(.c-comment__thread) > .c-composer"
  await fillAndSend(replyComposer, "回复测试")
  await wait(`document.querySelector(${JSON.stringify(replyComposer)}).querySelector('textarea').value === ''`)
  check("reply success clears and folds", { write: state.writes.at(-1), open: await evaluate(`document.querySelector(${JSON.stringify(replyComposer)}).closest('details').open`) }, state.writes.at(-1).body.parent_id === 100 && !(await evaluate(`document.querySelector(${JSON.stringify(replyComposer)}).closest('details').open`)))
  await evaluate("[...document.querySelectorAll('#comment-101 details > summary')].find(s=>s.textContent.trim()==='编辑').parentElement.open=true")
  const editComposer = "#comment-101 .c-composer:has(textarea[aria-label='修改评论'])"
  await fillAndSend(editComposer, "编辑测试")
  await wait("document.querySelector('#comment-101 .c-comment__body').textContent==='编辑测试'")
  check("edit success folds and displays saved body", { write: state.writes.at(-1), open: await evaluate(`document.querySelector(${JSON.stringify(editComposer)}).closest('details').open`) }, state.writes.at(-1).method === "PATCH" && !(await evaluate(`document.querySelector(${JSON.stringify(editComposer)}).closest('details').open`)))

  await open("/news/a/", { count: 41 })
  await evaluate("document.querySelector('#comments-more a').click()")
  await wait("document.querySelectorAll('#comment-list > li.c-comment').length===40")
  await clickText(101, "赞 0")
  await wait("document.querySelector('#comment-101 button[aria-pressed]').getAttribute('aria-pressed')==='true'")
  check("write refresh keeps all loaded pages", { count: await topCount(), reads: state.reads.slice(-2) }, (await topCount()) === 40 && state.reads.slice(-2).map((r) => r.page).join() === "1,2")

  state.readDelay = 400
  await evaluate("document.querySelector('#comments-more a').click()")
  await evaluate("document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/news/b/?sort=top')")
  await wait("document.querySelector('.c-cover__title').textContent==='Article B'")
  await pause(500)
  const switched = await evaluate("({title:document.querySelector('.c-cover__title').textContent,comments:[...document.querySelectorAll('.c-comment__body')].map(c=>c.textContent)})")
  check("old load-more cannot repaint a new article", switched, switched.comments.join() === "B comment only")
  await evaluate("document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/news/a/?sort=top')")
  await wait("document.querySelector('.c-cover__title').textContent==='Article A'")
  check("reused component resets sorting", { current: await evaluate("document.querySelector('.c-comments__sort a[aria-current=true]').textContent"), first: await evaluate("document.querySelector('.c-comment__body').textContent") }, (await evaluate("document.querySelector('.c-comments__sort a[aria-current=true]').textContent")) === "最热" && (await evaluate("document.querySelector('.c-comment__body').textContent")) === "A comment 41")
  state.readDelay = 0; state.writeDelay = 300
  await fillAndSend(composer, "离开后完成的写入")
  await evaluate("document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/news/b/')")
  await wait("document.querySelector('.c-cover__title').textContent==='Article B'")
  await pause(400)
  check("old write cannot repaint a new article", { body: await evaluate("document.querySelector('.c-comment__body').textContent") }, (await evaluate("document.querySelector('.c-comment__body').textContent")) === "B comment only")
  await evaluate("document.querySelector('#app').__vue_app__.config.globalProperties.$router.push('/')")
  await wait("!!document.querySelector('.c-hero')")
  const runtime = events.filter((e) => e.method === "Runtime.exceptionThrown" || (e.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(e.params.type))).map((e) => e.params.exceptionDetails?.exception?.description ?? e.params.args?.map((a) => a.value ?? a.description).join(" "))
  const violations = await evaluate("window.__violations")
  const cspLogs = events.filter((e) => e.method === "Log.entryAdded" && /Refused|Content Security Policy/i.test(e.params.entry.text)).map((e) => e.params.entry.text)
  check("comment interactions and navigation have zero runtime/CSP errors", { runtime, violations, cspLogs }, !runtime.length && !violations.length && !cspLogs.length)
  if (checks.some((c) => !c.passed)) process.exitCode = 1
  console.log(`COMMENTS-BROWSER-CHECK ${checks.filter((c) => c.passed).length}/${checks.length}`)
} catch (error) { console.error(error); process.exitCode = 1 }
finally { ws?.close(); for (const child of children) child.kill("SIGTERM"); for (const server of servers) server.close() }
