// Drives headless Chromium over the DevTools protocol (Node's built-in
// WebSocket, no extra packages) against a production build of the site and
// reports what 12-architecture 6.2/6.9/6.10 promise: hydration works,
// nothing is blocked by the strict CSP, client navigation works, the theme
// menu and the context menu behave, and with no script the banner shows up
// after 8 s. The API is a stub: /api/session says visitor — this checks the
// front end, not the API.
//
// Run it from web/apps/site after a build (pnpm --filter @sjtu-ow/site test):
//   node browser-check.mjs [chrome path] [base url]
// With no base url it starts its own server (needs dist/client + dist/server).
import { spawn, execSync } from "node:child_process"
import { mkdtempSync, writeFileSync, existsSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"

const chrome = process.argv[2] ?? "/usr/bin/chromium"
const given = process.argv[3]
const port = given ? 0 : 4200 + Math.floor(Math.random() * 500)
const base = given ?? `http://127.0.0.1:${port}`
const children = []
const failures = []

function fail(name, detail) {
  failures.push(`${name}: ${JSON.stringify(detail)}`)
  console.error(`✗ ${name}: ${JSON.stringify(detail)}`)
}

async function startServers() {
  if (given) return
  if (!existsSync("dist/server/server.js") || !existsSync("dist/client/.vite/manifest.json")) {
    throw new Error("先构建：pnpm --filter @sjtu-ow/site test")
  }
  const stubPort = 4700 + Math.floor(Math.random() * 200)
  const ssrPort = port + 1
  const stub = spawn(process.execPath, ["-e", `
    let user = null;
    let flash = "";
    require("node:http").createServer(async (req, res) => {
      let body = ""; for await (const chunk of req) body += chunk;
      const data = body ? JSON.parse(body) : {};
      res.setHeader("content-type", "application/json");
      if (req.url === "/api/auth/login") {
        if (data.password === "wrong") { res.statusCode = 400; res.end(JSON.stringify({ error: { code: "invalid", message: "邮箱或密码不正确。" } })); }
        else res.end(JSON.stringify({ result: "verify_required" }));
      }
      else if (req.url === "/api/auth/register") res.end(JSON.stringify({ email: data.email, message: "请查收验证码。" }));
      else if (req.url === "/api/auth/resend-code") res.end(JSON.stringify({ email: data.email }));
      else if (req.url === "/api/auth/verify-email") {
        user = { id: 7, nickname: "新人", email: "new@example.com", admin: false, superuser: false, caps: [], email_verified: true, is_sjtu: false };
        flash = "欢迎加入社区！先补全游戏 ID 和联系方式。";
        res.end(JSON.stringify({ result: "ok" }));
      }
      else if (req.url.startsWith("/api/session")) {
        const refresh = new URL(req.url, "http://stub").searchParams.get("refresh") === "true";
        res.end(JSON.stringify({ user, flash: refresh ? "" : flash }));
        if (!refresh) flash = "";
      }
      else if (req.url.startsWith("/api/page/home")) res.end(JSON.stringify({ stats: { member_count: 0, team_count: 0, scrims_held: 0 } }));
      // Like Go: an editor's page that is not there (/<slug>/ asks for it, 270).
      else if (req.url.startsWith("/api/page/")) { res.statusCode = 404; res.end(JSON.stringify({ error: { code: "not_found", message: "页面不存在" } })); }
      else res.end(JSON.stringify({}));
    }).listen(${stubPort});
  `])
  const server = spawn(process.execPath, ["dist/server/server.js"], {
    env: {
      ...process.env,
      NODE_ENV: "production",
      STRICT_CSP: "1",
      PORT: String(ssrPort),
      API_BASE: `http://127.0.0.1:${stubPort}`,
    },
    stdio: ["ignore", "inherit", "inherit"],
  })
  // The real site uses Caddy for /api. This throwaway proxy mirrors that
  // split so browser writes actually reach the stub, too.
  const proxy = spawn(process.execPath, ["-e", `
    const http = require("node:http");
    http.createServer((req, res) => {
      const up = http.request({ hostname: "127.0.0.1", port: req.url.startsWith("/api/") ? ${stubPort} : ${ssrPort}, method: req.method, path: req.url, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
      up.on("error", () => { res.writeHead(502); res.end(); }); req.pipe(up);
    }).listen(${port});
  `])
  children.push(stub, server, proxy)
  for (let i = 0; i < 50; i++) {
    try {
      await fetch(base + "/no-such-page/")
      return
    } catch {
      await new Promise((r) => setTimeout(r, 200))
    }
  }
  throw new Error("server did not come up")
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
async function main() {
  await startServers()
  const profile = mkdtempSync(join(tmpdir(), "ow-check-"))
  const debugPort = 9300 + Math.floor(Math.random() * 400)
  const real = spawn(chrome, ["--headless=new", `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, "--no-first-run", "--no-sandbox", "--window-size=1280,900", "about:blank"], { stdio: "ignore" })
  children.push(real)

  let wsUrl
  for (let i = 0; i < 50 && !wsUrl; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json()
      wsUrl = list.find((t) => t.type === "page")?.webSocketDebuggerUrl
    } catch {}
    if (!wsUrl) await sleep(200)
  }
  if (!wsUrl) throw new Error("no chrome")
  const ws = new WebSocket(wsUrl)
  await new Promise((r) => (ws.onopen = r))
  let id = 0
  const waiting = new Map()
  const events = []
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data)
    if (msg.id && waiting.has(msg.id)) {
      waiting.get(msg.id)(msg)
      waiting.delete(msg.id)
    } else events.push(msg)
  }
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })
    if (!r.result) throw new Error(`no result: ${expression.slice(0, 120)} ${JSON.stringify(r)}`)
    if (r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails))
    return r.result.result.value
  }
  await send("Runtime.enable")
  await send("Log.enable")
  await send("Page.enable")
  await send("Network.enable")
  // CDP cannot emulate the pointer media feature, and headless reports no
  // precise pointer — the site (rightly) keeps its context menu off those.
  // Pretend to be a desktop for this run; the gate itself is the old
  // contextmenu.js rule, unchanged.
  await send("Page.addScriptToEvaluateOnNewDocument", {
    source:
      "const realMatchMedia = window.matchMedia.bind(window);" +
      "window.matchMedia = (q) => q === '(pointer: fine)' ? { matches: true, media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} } : realMatchMedia(q);",
  })

  // Hydration keeps the server's DOM: nothing that holds #main may be removed
  // while the first page starts. createApp() (clear and paint again) and a
  // mismatch (node replaced) both remove it (frontend-migration A1).
  await send("Page.addScriptToEvaluateOnNewDocument", {
    source:
      "window.__ssrReplaced = [];" +
      "new MutationObserver((records) => { for (const r of records) for (const n of r.removedNodes) if (n.nodeType === 1 && (n.id === 'main' || (n.querySelector && n.querySelector('#main')))) window.__ssrReplaced.push(n.id || n.tagName); }).observe(document, { childList: true, subtree: true });",
  })

  const noted = () =>
    events
      .filter((e) => ["Log.entryAdded", "Runtime.exceptionThrown", "Runtime.consoleAPICalled"].includes(e.method))
      .map((e) =>
        e.method === "Log.entryAdded"
          ? `${e.params.entry.level}: ${e.params.entry.text} ${e.params.entry.url ?? ""}`
          : e.method === "Runtime.exceptionThrown"
            ? `exception: ${e.params.exceptionDetails.text}`
            : `console.${e.params.type}: ${e.params.args.map((a) => a.value ?? a.description).join(" ")}`,
      )
      // The favicon is not built and the night band's placeholder pictures
      // are not in this build yet (the asset pipeline is a later round).
      .filter((line) => !/favicon|\/img\/placeholders\//i.test(line))
  const go = async (path) => {
    events.length = 0
    await send("Page.navigate", { url: base + path })
    for (let i = 0; i < 50; i++) {
      const ready = await evaluate("document.readyState").catch(() => "")
      if (ready === "complete") break
      await sleep(100)
    }
    await sleep(300)
  }
  const waitJs = async () => {
    for (let i = 0; i < 50; i++) {
      if (await evaluate("document.documentElement.classList.contains('js-ready')").catch(() => false)) return true
      await sleep(100)
    }
    return false
  }

  // 1. first page: hydration, layout, the strict CSP
  await go("/")
  const home = await evaluate(`({
    jsReady: document.documentElement.classList.contains("js-ready"),
    h1: document.querySelector("h1")?.textContent,
    title: document.title,
    // 两处主导航（页头和抽屉）同有 aria-label=主导航；只数页头那份
    nav: [...document.querySelector("nav[aria-label=主导航]").querySelectorAll("a")].map((a) => a.textContent),
    footer: document.querySelector(".c-footer__statement")?.textContent.slice(0, 12),
    account: [...document.querySelectorAll(".c-account a")].map((a) => a.textContent.trim()),
    stylesheet: !!document.querySelector('link[rel="stylesheet"]'),
    entryScript: document.querySelector("script[type=module]")?.getAttribute("src"),
    themeHidden: document.querySelector(".c-theme")?.hasAttribute("hidden"),
    banner: !!document.querySelector(".c-nojs"),
    replaced: window.__ssrReplaced,
  })`)
  if (!home.jsReady) fail("激活", home)
  if (home.replaced?.length !== 0) fail("没有激活：服务端画的 #main 被换掉了", home)
  if ((home.h1 !== "SJTU-OW" && home.h1 !== "上海交通大学守望先锋社区") || home.title !== "首页 · SJTU-OW") fail("首页标题", home)
  if (home.nav.join(",") !== "首页,资讯,赛事,内战,战队,成员") fail("导航", home)
  if (!home.footer) fail("页脚", home)
  if (home.account.join(",") !== "登录,注册") fail("账号区", home)
  if (!/\/assets\/.*\.js$/.test(home.entryScript ?? "")) fail("入口脚本不是构建产物", home)
  if (!home.stylesheet) fail("没有样式表", home)
  if (home.themeHidden !== false) fail("主题菜单没有在激活后出现", home)
  const homeMessages = noted().filter((line) => !/favicon/i.test(line))
  if (homeMessages.length) fail("首页报错/CSP 违规", homeMessages)

  // 2. the policy really is on: inline things are stopped, CSSOM is not
  const policy = await evaluate(`(async () => {
    const violations = [];
    document.addEventListener("securitypolicyviolation", (e) => violations.push(e.violatedDirective));
    const s = document.createElement("script");
    s.textContent = "window.__ran = 1";
    document.body.append(s);
    const plain = document.createElement("div");
    document.body.append(plain);
    const attr = document.createElement("div");
    attr.setAttribute("style", "color:red");
    document.body.append(attr);
    const cssom = document.createElement("div");
    cssom.style.color = "red";
    document.body.append(cssom);
    await new Promise((r) => setTimeout(r, 200));
    return { inlineScriptRan: !!window.__ran, violations, plainColor: getComputedStyle(plain).color, attrColor: getComputedStyle(attr).color, cssomColor: getComputedStyle(cssom).color };
  })()`)
  if (policy.inlineScriptRan || policy.violations.length !== 2 || policy.attrColor !== policy.plainColor) fail("CSP 不严", policy)
  if (policy.cssomColor !== "rgb(255, 0, 0)") fail("CSSOM 被误拦", policy)
  // The probe above raised the two violations it wanted; drop them so they
  // do not pollute the next page's report.
  events.length = 0

  // 3. client-side navigation and back, without a page reload
  const nav = await evaluate(`(async () => {
    window.__same = 1;
    const violations = [];
    document.addEventListener("securitypolicyviolation", (e) => violations.push(e.violatedDirective));
    [...document.querySelectorAll("nav[aria-label=主导航] a")].find((a) => a.textContent === "战队").click();
    await new Promise((r) => setTimeout(r, 600));
    const there = { path: location.pathname, h1: document.querySelector("h1")?.textContent, title: document.title, same: window.__same };
    history.back();
    await new Promise((r) => setTimeout(r, 600));
    return { there, back: { path: location.pathname, h1: document.querySelector("h1")?.textContent, same: window.__same }, violations };
  })()`)
  if (nav.there.path !== "/teams/" || nav.there.h1 !== "战队" || nav.there.title !== "战队" || nav.there.same !== 1) fail("客户端换页", nav)
  if (nav.back.path !== "/" || (nav.back.h1 !== "SJTU-OW" && nav.back.h1 !== "上海交通大学守望先锋社区")) fail("后退", nav)
  const navMessages = noted().filter((line) => !/favicon/i.test(line))
  if (navMessages.length) fail("换页报错", navMessages)

  // 4. the theme menu: pick 深色, then back to 跟随系统
  const theme = await evaluate(`(async () => {
    const menu = document.querySelector("details.c-theme");
    menu.open = true;
    const dark = [...menu.querySelectorAll("button")].find((b) => b.textContent.trim() === "深色");
    dark.click();
    await new Promise((r) => setTimeout(r, 400));
    const picked = {
      attr: document.documentElement.getAttribute("data-theme"),
      stored: localStorage.getItem("ow-theme"),
      pressed: dark.getAttribute("aria-pressed"),
      closed: !menu.open,
    };
    menu.open = true;
    const system = [...menu.querySelectorAll("button")].find((b) => b.textContent.trim() === "跟随系统");
    system.click();
    await new Promise((r) => setTimeout(r, 400));
    return { ...picked, back: { attr: document.documentElement.getAttribute("data-theme"), stored: localStorage.getItem("ow-theme"), pressed: system.getAttribute("aria-pressed") } };
  })()`)
  if (theme.attr !== "dark" || theme.stored !== "dark" || theme.pressed !== "true" || theme.closed !== true) fail("主题选择", theme)
  if (theme.back.attr !== null || theme.back.stored !== null || theme.back.pressed !== "true") fail("主题恢复系统", theme)

  // 5. the context menu on a link, closed by Escape
  const ctx = await evaluate(`(async () => {
    const pointerFine = window.matchMedia("(pointer: fine)").matches;
    const link = [...document.querySelectorAll("nav a")].find((a) => a.textContent === "战队");
    const rect = link.getBoundingClientRect();
    link.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: rect.left + 4, clientY: rect.top + 4, button: 2 }));
    const menu = document.querySelector(".c-ctxmenu");
    const opened = { pointerFine, there: !!menu, items: menu ? [...menu.querySelectorAll(".c-ctxmenu__item")].map((b) => b.textContent) : [], focused: document.activeElement?.className };
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await new Promise((r) => setTimeout(r, 100));
    return { ...opened, gone: !document.querySelector(".c-ctxmenu") };
  })()`)
  if (!ctx.there || !ctx.items.includes("在新标签页打开") || !ctx.items.includes("复制本页链接") || !ctx.gone) fail("右键菜单", ctx)

  // 6. a screenshot for the round's report
  const shot = await send("Page.captureScreenshot", { format: "png" })
  writeFileSync("screenshot-home.png", Buffer.from(shot.result.data, "base64"))

  // 7. no script: still readable, the banner after 8 s
  await send("Emulation.setScriptExecutionDisabled", { value: true })
  await go("/?nojs=1")
  const early = await evaluate(`getComputedStyle(document.querySelector(".c-nojs")).visibility`)
  const readable = await evaluate(`document.querySelector("h1")?.textContent`)
  await sleep(8500)
  const after = await evaluate(`getComputedStyle(document.querySelector(".c-nojs")).visibility`)
  await send("Emulation.setScriptExecutionDisabled", { value: false })
  if (readable !== "SJTU-OW" && readable !== "上海交通大学守望先锋社区") fail("无脚本读不了", readable)
  if (early !== "hidden" || after !== "visible") fail("无脚本横幅", { early, after })

  // 8. unknown address: the server's 404, not a blank page
  const unknown = await fetch(base + "/no-such-page/")
  const unknownBody = await unknown.text()
  if (unknown.status !== 404 || !unknownBody.includes("页面不存在")) fail("404", { status: unknown.status })
  if (unknownBody.includes("ow-state")) fail("404 不该有数据块", {})
  // In the browser: the old error page with error.css applied, no script,
  // nothing blocked by the policy (frontend-migration A12).
  await go("/no-such-page/")
  const errorPage = await evaluate(`({
    sheets: [...document.styleSheets].map((s) => new URL(s.href).pathname),
    rules: document.styleSheets[0]?.cssRules.length ?? 0,
    scripts: document.scripts.length,
    h1: document.querySelector("h1")?.textContent,
    code: document.querySelector(".code")?.textContent,
  })`)
  if (errorPage.sheets.join() !== "/static/css/error.css" || errorPage.rules < 10) fail("404 页没有 error.css", errorPage)
  if (errorPage.scripts !== 0 || errorPage.h1 !== "页面不存在" || errorPage.code !== "404") fail("404 页不是旧站的样子", errorPage)
  // The page's own 404 is logged as a failed load: that is the point of it.
  const errorMessages = noted().filter((line) => !line.includes(base + "/no-such-page/"))
  if (errorMessages.length) fail("404 页报错/CSP 违规", errorMessages)

  const cover = await fetch(base + "/static/img/placeholders/cover-07.svg")
  const coverBody = await cover.text()
  const coverType = cover.headers.get("content-type") ?? ""
  const coverCache = cover.headers.get("cache-control") ?? ""
  if (cover.status !== 200 || !coverType.includes("image/svg+xml") || !coverBody.includes("<svg")) {
    fail("占位图", { status: cover.status, coverType })
  }
  if (!coverCache.includes("max-age=86400")) fail("占位图缓存", coverCache)

  // Only exercise the local throwaway API. A supplied base may be a real site.
  if (!given) {
    await go("/accounts/login/?next=%2Faccounts%2Finactive%2F")
    await waitJs()
    const wrong = await evaluate(`(async () => {
      const input = (name, value) => { const el = document.querySelector('[name="' + name + '"]'); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); };
      input('login', 'new@example.com'); input('password', 'wrong');
      document.querySelector('#main form').requestSubmit();
      await new Promise(r => setTimeout(r, 350));
      return { error: document.querySelector('.c-field__error')?.textContent, email: document.querySelector('[name=login]').value, password: document.querySelector('[name=password]').value };
    })()`)
    if (!wrong.error?.includes("邮箱或密码不正确") || wrong.email !== "new@example.com" || wrong.password !== "wrong") fail("登录错误保留输入", wrong)
    await evaluate(`const p = document.querySelector('[name=password]'); p.value = 'ValidPass!234'; p.dispatchEvent(new Event('input', { bubbles: true })); document.querySelector('#main form').requestSubmit();`)
    await sleep(600)
    await waitJs()
    const verification = await evaluate(`({ path: location.pathname, email: document.querySelector('a[href^="mailto:"]')?.textContent, next: new URLSearchParams(location.search).get('next'), replaced: window.__ssrReplaced })`)
    if (verification.path !== "/accounts/confirm-email/" || verification.email !== "new@example.com" || verification.next !== "/accounts/inactive/" || verification.replaced?.length) fail("未验证邮箱跳转与激活", verification)
    const cooldown = await evaluate(`(async () => {
      document.querySelector('input[name=action]').form.requestSubmit();
      await new Promise(r => setTimeout(r, 250));
      const b = document.querySelector('input[name=action]').form.querySelector('button');
      return { disabled: b.disabled, label: b.textContent };
    })()`)
    if (!cooldown.disabled || !cooldown.label.includes("秒后可重新发送")) fail("重发验证码冷却", cooldown)
    await go("/accounts/signup/?next=%2Faccounts%2Finactive%2F")
    await waitJs()
    await evaluate(`{
      const input = (name, value) => { const el = document.querySelector('[name="' + name + '"]'); el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); };
      input('email', 'new@example.com'); input('nickname', '新人'); input('password1', 'ValidPass!234'); input('password2', 'ValidPass!234');
      document.querySelector('[name=is_sjtu][value=false]').click(); document.querySelector('[name=agreed_terms]').click(); document.querySelector('[name=agreed_cross_border]').click(); document.querySelector('#main form').requestSubmit();
    }`)
    await sleep(600)
    await waitJs()
    await evaluate(`const c = document.querySelector('[name=code]'); c.value = '123456'; c.dispatchEvent(new Event('input', { bubbles: true })); document.querySelector('#main form').requestSubmit();`)
    await sleep(600)
    await waitJs()
    const completed = await evaluate(`({ path: location.pathname, notice: document.querySelector('.c-toast')?.textContent, stored: sessionStorage.getItem('ow-account-notice') })`)
    if (completed.path !== "/accounts/inactive/" || !completed.notice?.includes("欢迎加入社区") || completed.stored !== null) fail("注册验证完成与一次性提示", completed)
    const accountMessages = noted().filter(line => !/favicon/.test(line))
    if (accountMessages.length) fail("账号入口报错/CSP 违规", accountMessages)
  }

  if (!given && !failures.length) {
    const comments = spawn(process.execPath, ["comments-browser-check.mjs", chrome], { stdio: "inherit" })
    children.push(comments)
    const code = await new Promise((resolve) => comments.on("exit", resolve))
    if (code !== 0) fail("评论真实浏览器回归", { code })
  }
  console.log(failures.length ? `\n${failures.length} 项没过` : "\nBROWSER-CHECK-OK")
}

try {
  await main()
} catch (error) {
  failures.push(String(error))
  console.error(error)
} finally {
  for (const child of children) {
    child.kill("SIGTERM")
  }
  try {
    execSync("pkill -f ow-check- || true", { stdio: "ignore" })
  } catch {}
}
process.exit(failures.length ? 1 : 0)
