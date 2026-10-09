#!/usr/bin/env node
/**
 * 新栈全页面多端真实浏览器截图生成器（对照旧站 scripts/screens.py）。
 *
 * 用法：
 *   node scripts/screens.mjs [WIDTH] [dark]
 * 示例：
 *   node scripts/screens.mjs 1280        # 桌面端 1280 截图
 *   node scripts/screens.mjs 375         # 移动端 375 截图
 *   node scripts/screens.mjs 1280 dark   # 深色模式截图
 *
 * 输出：
 *   截图保存在 /tmp/sjtu-ow-screens/out/*.png
 */

import { spawn, execSync } from "node:child_process"
import { mkdtempSync, writeFileSync, existsSync, mkdirSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"

const width = parseInt(process.argv[2] ?? "1280", 10) || 1280
const isDark = process.argv.includes("dark")
const ROOT = resolve(import.meta.dirname, "..")
const OUT = "/tmp/sjtu-ow-screens/out"
mkdirSync(OUT, { recursive: true })

const chromeCandidates = [
  process.env.CHROME_BIN,
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
const chrome = chromeCandidates.find((c) => c && existsSync(c))
if (!chrome) {
  console.error("未找到 Chromium / Chrome 浏览器。")
  process.exit(1)
}

const workDir = mkdtempSync(join(tmpdir(), "sjtu-ow-screens-"))
const dataDir = join(workDir, "data")
mkdirSync(dataDir, { recursive: true })

const apiPort = 4800 + Math.floor(Math.random() * 200)
const ssrPort = 4200 + Math.floor(Math.random() * 200)
const apiBase = `http://127.0.0.1:${apiPort}`
const ssrBase = `http://127.0.0.1:${ssrPort}`

const children = []
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

console.log(`[1/3] 初始化测试数据 (${dataDir})...`)
const env = {
  ...process.env,
  DATA_DIR: dataDir,
  SITE_URL: ssrBase,
  SIGNING_KEY: "screens-test-signing-key-32-chars-long",
  FIELD_ENCRYPTION_KEY: "screens-test-field-key-32-chars-long1",
}
execSync("go run ./cmd/sjtuow migrate", { cwd: join(ROOT, "server"), env, stdio: "ignore" })
const seedRaw = execSync("go run ./cmd/sjtuow seed", { cwd: join(ROOT, "server"), env, encoding: "utf8" })
const seed = JSON.parse(seedRaw.trim().split("\n").pop())

console.log(`[2/3] 启动 Go API (: ${apiPort}) 与 SSR (: ${ssrPort})...`)
const apiProc = spawn("go", ["run", "./cmd/sjtuow", "serve"], {
  cwd: join(ROOT, "server"),
  env: { ...env, SJTUOW_HTTP_ADDR: `127.0.0.1:${apiPort}` },
  stdio: "ignore",
})
children.push(apiProc)

if (!existsSync(join(ROOT, "web/apps/site/dist/server/server.js"))) {
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
  stdio: "ignore",
})
children.push(ssrProc)

for (let i = 0; i < 50; i++) {
  try {
    const res = await fetch(`${ssrBase}/`)
    if (res.ok) break
  } catch {}
  await sleep(200)
}

console.log(`[3/3] 启动无头浏览器截屏 (宽度: ${width}, 深色: ${isDark})...`)
const debugPort = 9400 + Math.floor(Math.random() * 400)
const browserProc = spawn(
  chrome,
  [
    "--headless=new",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${join(workDir, "chrome-profile")}`,
    "--no-first-run",
    "--no-sandbox",
    `--window-size=${width},900`,
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

const ws = new WebSocket(wsUrl)
await new Promise((r) => (ws.onopen = r))

let cdpId = 0
const waitingMap = new Map()
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data)
  if (msg.id && waitingMap.has(msg.id)) {
    waitingMap.get(msg.id)(msg)
    waitingMap.delete(msg.id)
  }
}

const send = (method, params = {}) =>
  new Promise((r) => {
    const i = ++cdpId
    waitingMap.set(i, r)
    ws.send(JSON.stringify({ id: i, method, params }))
  })

await send("Runtime.enable")
await send("Page.enable")
await send("Network.enable")
await send("Emulation.setDeviceMetricsOverride", {
  width,
  height: 900,
  deviceScaleFactor: 1,
  mobile: width < 600,
})

const PAGES = [
  { name: "home-visitor", role: "visitor", path: "/" },
  { name: "home-member", role: "member", path: "/" },
  { name: "news-list", role: "visitor", path: "/news/" },
  { name: "tournaments-list", role: "visitor", path: "/tournaments/" },
  { name: "tournament-detail", role: "member", path: `/tournaments/${seed.cup}/` },
  { name: "scrims-list", role: "visitor", path: "/scrims/" },
  { name: "scrim-detail", role: "member", path: `/scrims/${seed.scrim}/` },
  { name: "teams-list", role: "visitor", path: "/teams/" },
  { name: "team-detail", role: "member", path: `/teams/${seed.team}/` },
  { name: "members-list", role: "visitor", path: "/members/" },
  { name: "member-profile", role: "member", path: "/members/1/" },
  { name: "me-profile", role: "member", path: "/me/" },
  { name: "me-game-accounts", role: "member", path: "/me/game-accounts/" },
  { name: "me-contacts", role: "member", path: "/me/contacts/" },
  { name: "accounts-login", role: "visitor", path: "/accounts/login/" },
  { name: "accounts-signup", role: "visitor", path: "/accounts/signup/" },
  { name: "admin-home", role: "officer", path: "/admin/" },
  { name: "admin-scrims", role: "officer", path: "/admin/scrims/" },
  { name: "admin-tournaments", role: "officer", path: "/admin/tournaments/" },
  { name: "admin-users", role: "officer", path: "/admin/users/" },
  { name: "admin-teams", role: "officer", path: "/admin/teams/" },
  { name: "admin-articles", role: "officer", path: "/admin/articles/" },
  { name: "admin-categories", role: "officer", path: "/admin/categories/" },
]

for (const p of PAGES) {
  // 设置身份 Cookie
  await send("Network.clearBrowserCookies")
  if (p.role === "member") {
    await send("Network.setCookie", { name: "ow_session", value: seed.member, domain: "127.0.0.1", path: "/" })
  } else if (p.role === "captain") {
    await send("Network.setCookie", { name: "ow_session", value: seed.captain, domain: "127.0.0.1", path: "/" })
  } else if (p.role === "officer") {
    await send("Network.setCookie", { name: "ow_session", value: seed.officer, domain: "127.0.0.1", path: "/" })
  }

  await send("Page.navigate", { url: ssrBase + p.path })
  await sleep(600)

  if (isDark) {
    await send("Runtime.evaluate", { expression: "document.documentElement.setAttribute('data-theme', 'dark')" })
    await sleep(200)
  }

  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true })
  if (shot.result?.data) {
    const filename = `${p.name}-${width}${isDark ? "-dark" : ""}.png`
    writeFileSync(join(OUT, filename), Buffer.from(shot.result.data, "base64"))
    console.log(`  📸 [${p.role}] ${p.path} -> ${filename}`)
  }
}

console.log(`\n🎉 截图已全量保存至 ${OUT}`)
for (const c of children) {
  try {
    c.kill("SIGTERM")
  } catch {}
}
process.exit(0)
