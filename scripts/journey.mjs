#!/usr/bin/env node
/**
 * 新栈自动化端到端测试与真实浏览器全流程检验套件（对照旧站 scripts/journey.py）。
 *
 * 用法：
 *   node scripts/journey.mjs         # 新人的第一晚（注册 -> 验证码登录 -> 填资料 -> 报内战 -> 申请战队 -> 首页验证）
 *   node scripts/journey.mjs pages   # 全站页面遍历巡检（访客、成员、超管，确保 0 报错、0 异常、0 CSP 违规）
 *   node scripts/journey.mjs admin   # 干部那一晚（内战分队板与管理后台）
 */

import { spawn, execSync } from "node:child_process"
import { mkdtempSync, writeFileSync, existsSync, mkdirSync, readFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

const mode = process.argv[2] ?? "newbie"
const ROOT = resolve(import.meta.dirname, "..")

// 探测 Chromium / Chrome 路径
const chromeCandidates = [
  process.env.CHROME_BIN,
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
const chrome = chromeCandidates.find((c) => c && existsSync(c))
if (!chrome) {
  console.error("未找到可用 Chromium 或 Chrome 浏览器。")
  process.exit(1)
}

const workDir = mkdtempSync(join(tmpdir(), "sjtu-ow-journey-"))
const dataDir = join(workDir, "data")
mkdirSync(dataDir, { recursive: true })

const apiPort = 4800 + Math.floor(Math.random() * 200)
const ssrPort = 4200 + Math.floor(Math.random() * 200)
const apiBase = `http://127.0.0.1:${apiPort}`
const ssrBase = `http://127.0.0.1:${ssrPort}`

const children = []
const events = []
const failures = []

function fail(name, detail = "") {
  failures.push(`${name} ${detail}`)
  console.error(`✗ BAD ${name} ${detail}`)
}

function step(name, ok, detail = "") {
  if (ok) {
    console.log(`✓ ok  ${name} ${detail}`)
  } else {
    fail(name, detail)
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// 1. 初始化数据库并打入基础种子数据
console.log(`[1/4] 初始化测试数据库并植入种子数据 (${dataDir})...`)
const env = {
  ...process.env,
  DATA_DIR: dataDir,
  SITE_URL: ssrBase,
  SIGNING_KEY: "journey-test-signing-key-32-chars-long",
  FIELD_ENCRYPTION_KEY: "journey-test-field-key-32-chars-long1",
}

execSync("go run ./cmd/sjtuow migrate", { cwd: join(ROOT, "server"), env, stdio: "ignore" })
const seedRaw = execSync("go run ./cmd/sjtuow seed", { cwd: join(ROOT, "server"), env, encoding: "utf8" })
const seedData = JSON.parse(seedRaw.trim().split("\n").pop())

// 2. 启动 Go API 与 Node SSR 服务
console.log(`[2/4] 启动 Go API (: ${apiPort}) 与 Vue 3 SSR (: ${ssrPort})...`)
const apiProc = spawn("go", ["run", "./cmd/sjtuow", "serve"], {
  cwd: join(ROOT, "server"),
  env: { ...env, SJTUOW_HTTP_ADDR: `127.0.0.1:${apiPort}` },
  stdio: ["ignore", "ignore", "inherit"],
})
children.push(apiProc)

// 确保 web 构建存在
if (!existsSync(join(ROOT, "web/apps/site/dist/server/server.js"))) {
  console.log("正在构建前端 SSR 与资源产物...")
  execSync("pnpm --filter @sjtu-ow/site build", { cwd: ROOT, stdio: "inherit" })
}

const ssrProc = spawn(process.execPath, ["dist/server/server.js"], {
  cwd: join(ROOT, "web/apps/site"),
  env: {
    ...process.env,
    NODE_ENV: "production",
    STRICT_CSP: "1",
    PORT: String(ssrPort),
    API_BASE: apiBase,
  },
  stdio: ["ignore", "ignore", "inherit"],
})
children.push(ssrProc)

// 等待服务就绪
let ready = false
for (let i = 0; i < 50; i++) {
  try {
    const res = await fetch(`${ssrBase}/`)
    if (res.ok) {
      ready = true
      break
    }
  } catch {}
  await sleep(200)
}
if (!ready) {
  console.error("SSR 服务未能成功启动。")
  cleanup()
  process.exit(1)
}

// 3. 启动无头 Chromium 并建立 CDP 调试连接
console.log(`[3/4] 启动无头 Chromium (${chrome})...`)
const debugPort = 9400 + Math.floor(Math.random() * 400)
const browserProc = spawn(
  chrome,
  [
    "--headless=new",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${join(workDir, "chrome-profile")}`,
    "--no-first-run",
    "--no-sandbox",
    "--window-size=1280,900",
    "about:blank",
  ],
  { stdio: "ignore" },
)
children.push(browserProc)

let wsUrl = ""
for (let i = 0; i < 50 && !wsUrl; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json()
    wsUrl = list.find((t) => t.type === "page")?.webSocketDebuggerUrl
  } catch {}
  if (!wsUrl) await sleep(200)
}
if (!wsUrl) {
  console.error("未能连接到 Chromium DevTools 接口。")
  cleanup()
  process.exit(1)
}

const ws = new WebSocket(wsUrl)
await new Promise((r) => (ws.onopen = r))

let cdpId = 0
const waitingMap = new Map()
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data)
  if (msg.id && waitingMap.has(msg.id)) {
    waitingMap.get(msg.id)(msg)
    waitingMap.delete(msg.id)
  } else {
    events.push(msg)
  }
}

const send = (method, params = {}) =>
  new Promise((r) => {
    const i = ++cdpId
    waitingMap.set(i, r)
    ws.send(JSON.stringify({ id: i, method, params }))
  })

const evaluate = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true })
  if (r.result?.exceptionDetails) {
    throw new Error(JSON.stringify(r.result.exceptionDetails))
  }
  return r.result?.result?.value
}

await send("Runtime.enable")
await send("Log.enable")
await send("Page.enable")
await send("Network.enable")

const go = async (path) => {
  await send("Page.navigate", { url: path.startsWith("http") ? path : ssrBase + path })
  for (let i = 0; i < 50; i++) {
    const st = await evaluate("document.readyState").catch(() => "")
    if (st === "complete") break
    await sleep(100)
  }
  await sleep(300)
}

const fillAndSubmit = async (fnScript) => {
  await evaluate(fnScript)
  await evaluate("document.querySelector('form[data-journey]')?.requestSubmit?.() || document.querySelector('form[data-journey] button[type=submit]')?.click()")
  await sleep(1000)
}

const pageSays = async (text) => {
  const bodyText = await evaluate("document.body.innerText")
  return (bodyText ?? "").includes(text)
}

const setSessionCookie = async (token) => {
  await send("Network.clearBrowserCookies")
  if (token) {
    await send("Network.setCookie", {
      name: "ow_session",
      value: token,
      domain: "127.0.0.1",
      path: "/",
    })
  }
}

// 4. 执行对应测试流程
console.log(`[4/4] 执行测试流程: [${mode}]...`)

if (mode === "newbie") {
  // === 新人的第一晚 ===
  const EMAIL = "newbie@journey.test"
  const NICKNAME = "新来的"
  const PASSWORD = "Journey-Pass-2026!"

  await go("/accounts/signup/")
  await fillAndSubmit(`(() => {
    const f = document.querySelector('form[action*="signup"]');
    f.querySelector('[name=email]').value = ${JSON.stringify(EMAIL)};
    f.querySelector('[name=nickname]').value = ${JSON.stringify(NICKNAME)};
    f.querySelector('[name=password1]').value = ${JSON.stringify(PASSWORD)};
    f.querySelector('[name=password2]').value = ${JSON.stringify(PASSWORD)};
    const sjtu = f.querySelector('[name=is_sjtu][value=true]');
    if (sjtu) sjtu.checked = true;
    f.querySelectorAll('input[type=checkbox]').forEach(b => b.checked = true);
    f.setAttribute('data-journey', '1');
  })()`)
  const signupPath = await evaluate("location.pathname")
  step("注册表单提交", signupPath === "/accounts/confirm-email/", signupPath)

  // 从 jobs 表中读取邮件车道上的验证码明文
  let code = ""
  for (let i = 0; i < 30; i++) {
    try {
      const out = execSync(`sqlite3 ${join(dataDir, "sjtuow.sqlite3")} "SELECT args FROM jobs WHERE kind = 'mail.letter' ORDER BY id DESC LIMIT 1"`, { encoding: "utf8" }).trim()
      if (out) {
        const payload = JSON.parse(out)
        const c = payload?.letter?.code || payload?.Letter?.Code || payload?.Letter?.code
        if (c && c.length === 6) {
          code = c
          break
        }
      }
    } catch {}
    await sleep(200)
  }
  step("验证码邮件发出", Boolean(code), code)

  if (code) {
    await fillAndSubmit(`(() => {
      const f = document.querySelector('form');
      const emailField = f.querySelector('input[name=email]');
      if (emailField) emailField.value = ${JSON.stringify(EMAIL)};
      const field = f.querySelector('input[name=code]');
      field.value = ${JSON.stringify(code)};
      f.setAttribute('data-journey', '1');
    })()`)
  }
  await sleep(1200)
  const verifiedPath = await evaluate("location.pathname")
  step("验证后到了个人中心", verifiedPath === "/me/", verifiedPath)

  // 加游戏 ID
  await go("/me/game-accounts/?new=1")
  await fillAndSubmit(`(() => {
    const f = document.querySelector('main form');
    f.querySelector('[name=battletag]').value = 'Newbie#1234';
    f.setAttribute('data-journey', '1');
  })()`)
  step("加了游戏 ID", await pageSays("Newbie#1234"))

  // 加联系方式
  await go("/me/contacts/?new=1")
  await fillAndSubmit(`(() => {
    const f = document.querySelector('main form');
    f.querySelector('[name=value]').value = '123456789';
    f.setAttribute('data-journey', '1');
  })()`)
  step("加了联系方式", await pageSays("123456789"))

  // 资料自动保存
  await go("/me/")
  await evaluate(`(() => {
    const motto = document.querySelector('form[data-autosave] [name=motto]');
    motto.value = '浏览器里自动保存的宣言';
    motto.dispatchEvent(new Event('input', { bubbles: true }));
  })()`)
  await sleep(1500)
  const autoStatus = await evaluate("document.querySelector('[data-autosave-status]')?.textContent")
  step("资料改了就自动保存", (autoStatus ?? "").includes("已保存"), autoStatus)
  await go("/me/")
  const keptMotto = await evaluate("document.querySelector('[name=motto]')?.value")
  step("刷新以后还在", keptMotto === "浏览器里自动保存的宣言", keptMotto)

  // 报内战
  await go(`/scrims/${seedData.scrim}/`)
  await fillAndSubmit(`(() => {
    const f = [...document.querySelectorAll('form')].find(form => form.action.includes('/signup/'));
    f.setAttribute('data-journey', '1');
  })()`)
  step("报了内战", await pageSays("报名成功"))

  // 申请战队
  await go(`/teams/${seedData.team}/apply/`)
  await fillAndSubmit(`(() => {
    const f = document.querySelector('main form');
    f.setAttribute('data-journey', '1');
  })()`)
  step("申请了战队", await pageSays("申请已提交"))

  // 回首页看近期内战
  await go("/")
  step("首页有这场内战", await pageSays("截图内战"))
} else if (mode === "pages") {
  // === 全站页面遍历巡检 ===
  const publicRoutes = [
    "/",
    "/news/",
    "/tournaments/",
    "/scrims/",
    "/teams/",
    "/members/",
    "/about/",
    "/terms/",
    "/privacy/",
    "/accounts/login/",
    "/accounts/signup/",
    "/accounts/confirm-email/",
  ]
  const memberRoutes = [
    "/me/",
    "/me/game-accounts/",
    "/me/contacts/",
    "/me/registrations/",
    "/me/teams/",
    "/me/scrims/",
    `/teams/${seedData.team}/`,
    `/scrims/${seedData.scrim}/`,
    `/tournaments/${seedData.cup}/`,
  ]
  const adminRoutes = [
    "/admin/",
    "/admin/tournaments/",
    "/admin/scrims/",
    "/admin/users/",
    "/admin/teams/",
    "/admin/articles/",
    "/admin/categories/",
    "/admin/home-pins/",
    "/admin/images/",
    "/admin/roles/",
  ]

  // 1. 访客视角
  await setSessionCookie(null)
  for (const r of publicRoutes) {
    await go(r)
    const domOk = await evaluate("document.body.children.length > 0")
    step(`[访客] 页面正常: ${r}`, domOk)
  }

  // 2. 成员视角
  await setSessionCookie(seedData.member)
  for (const r of memberRoutes) {
    await go(r)
    const domOk = await evaluate("document.body.children.length > 0")
    step(`[成员] 页面正常: ${r}`, domOk)
  }

  // 3. 超管视角
  await setSessionCookie(seedData.officer)
  for (const r of adminRoutes) {
    await go(r)
    const domOk = await evaluate("document.body.children.length > 0")
    step(`[超管] 页面正常: ${r}`, domOk)
  }
} else if (mode === "admin") {
  // === 干部那一晚 ===
  await setSessionCookie(seedData.officer)
  await go("/admin/scrims/")
  step("管理员进入内战管理后台", await pageSays("内战管理"))

  await go("/admin/tournaments/")
  step("管理员进入赛事管理后台", await pageSays("赛事管理"))

  await go("/admin/users/")
  step("管理员进入用户管理后台", await pageSays("用户管理"))

  await go("/admin/teams/")
  step("管理员进入战队管理后台", await pageSays("战队管理"))
}

// 检查所有浏览器控制台报错与未捕获异常
const relevantErrors = events.filter((e) => {
  if (e.method === "Log.entryAdded" && e.params?.entry?.level === "error") {
    const text = e.params.entry.text || ""
    if (/favicon|\/img\/placeholders\//i.test(text)) return false
    return true
  }
  if (e.method === "Runtime.exceptionThrown") return true
  if (e.method === "Runtime.consoleAPICalled" && e.params?.type === "error") return true
  return false
})

if (relevantErrors.length > 0) {
  for (const err of relevantErrors) {
    console.error("  浏览器错误:", JSON.stringify(err))
  }
  fail("浏览器报告错误", `(${relevantErrors.length} 条)`)
} else {
  step("浏览器零控制台报错与零未捕获异常", true)
}

cleanup()
if (failures.length > 0) {
  console.error(`\n共 ${failures.length} 项测试失败。`)
  process.exit(1)
} else {
  console.log(`\n🎉 全部测试顺利通过！`)
  process.exit(0)
}

function cleanup() {
  for (const c of children) {
    try {
      c.kill("SIGTERM")
    } catch {}
  }
}
