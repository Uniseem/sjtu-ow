import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"

const root = resolve(import.meta.dirname, "../../..")
const require = createRequire(join(process.env.POLISH_PLAYWRIGHT || join(root, "web"), "package.json"))
const { chromium, webkit } = require("playwright")
const config = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { base, data, sessions, phase, output } = config
const baseline = phase === "baseline"
const probeOnly = process.env.UI_PROBE_ONLY === "1"
const engine = process.env.UI_ENGINE || "chromium"
const shots = join(output, engine)
mkdirSync(shots, { recursive: true })
const browser = await (engine === "webkit" ? webkit.launch({ headless: true }) : chromium.launch({ executablePath: "/usr/bin/chromium", headless: true }))
const results = [], diagnostics = [], errors = [], samples = []
function check(name, pass, details) {
  diagnostics.push({ name, pass, details })
  console.log(`${pass ? "PASS" : baseline ? "BASELINE-GAP" : "FAIL"} ${name}: ${JSON.stringify(details)}`)
  if (!baseline) assert(pass, `${name}: ${JSON.stringify(details)}`)
}
const front = [
  ["home", "/"], ["news", "/news/"], ["article", "/news/screens-guide/"], ["search", "/search/?q=截图"],
  ["teams", "/teams/"], ["team", `/teams/${data.team}/`], ["members", "/members/"], ["member", `/members/${data.member}/`],
  ["tournaments", "/tournaments/"], ["tournament", `/tournaments/${data.cup}/`], ["scrims", "/scrims/"], ["scrim", `/scrims/${data.scrim}/`],
  ["login", "/accounts/login/"], ["signup", "/accounts/signup/"],
  ["profile", "/me/", "member"], ["game-accounts", "/me/game-accounts/", "member"], ["contacts", "/me/contacts/", "member"], ["security", "/me/security/", "member"],
  ["my-teams", "/me/teams/", "captain"], ["my-registrations", "/me/registrations/", "captain"], ["my-scrims", "/me/scrims/", "member"],
  ["team-manage", `/teams/${data.team}/manage/`, "captain"],
]
const admin = [
  ["dashboard", "/admin/"], ["articles", "/admin/articles/"], ["article-editor", `/admin/articles/${data.article}/`], ["article-new", "/admin/articles/new/"],
  ["categories", "/admin/categories/"], ["category", `/admin/categories/${data.category}/`], ["pages", "/admin/pages/"], ["images", "/admin/images/"],
  ["settings", "/admin/settings/site/"], ["users", "/admin/users/"], ["user", `/admin/users/${data.member}/`], ["roles", "/admin/roles/"],
  ["groups", "/admin/member-groups/"], ["group", `/admin/member-groups/${data.group}/`], ["teams", "/admin/teams/"],
  ["tournaments", "/admin/tournaments/"], ["scrims", "/admin/scrims/"], ["split", `/admin/scrims/${data.scrim}/split/`], ["team-board", `/admin/tournaments/${data.cup}/teams/`],
  ["registrations", "/admin/registrations/"], ["moderation", "/admin/moderation/"], ["avatars", "/admin/avatars/"], ["comments", "/admin/comments/"],
  ["activity", "/admin/activity/"], ["fonts", "/admin/settings/fonts/"], ["typography", "/admin/settings/typography/"], ["log", "/admin/log/"], ["manual", "/admin/manual/"],
].map(([name, path]) => [`admin-${name}`, path, "officer"])
async function identity(context, who) {
  await context.clearCookies()
  if (who) { assert(sessions[who], `Missing session ${who}`); await context.addCookies([{ name: "ow_session", value: sessions[who], url: base }]) }
}
async function settle(page) {
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(300)
}
async function snap(page, name) {
  // WebKit's screenshot preparation injects an inline body{} stylesheet.
  // Keep its strict-CSP interaction pass free of that tool-generated violation.
  if (engine === "webkit") return null
  const file = `${name}.png`
  await page.screenshot({ path: join(shots, file), fullPage: true })
  return file
}
function observe(page) {
  page.on("pageerror", error => errors.push(String(error)))
  page.on("console", message => { if (message.type() === "error" || /hydration|mismatch/i.test(message.text())) errors.push(message.text()) })
}
async function motionFrame(page, selector, name) {
  const states = await page.locator(selector).evaluate(node => node.getAnimations({ subtree: true }).filter(animation => typeof animation.animationName === "string" && animation.animationName.startsWith("c-")).map(animation => {
    const duration = Number(animation.effect.getTiming().duration)
    animation.pause()
    animation.currentTime = duration / 2
    return { name: animation.animationName, duration, midpoint: animation.currentTime }
  }))
  assert(states.length, `${name}: no active CSS animation`)
  await page.waitForTimeout(30)
  const bounds = await page.locator(selector).boundingBox()
  assert(bounds, name)
  if (engine !== "webkit") await page.screenshot({ path: join(shots, name + "-midpoint.png"), clip: bounds })
  console.log(`MOTION-MIDPOINT ${name} ${JSON.stringify(states)}`)
  await page.locator(selector).evaluate(node => node.getAnimations({ subtree: true }).forEach(animation => animation.play()))
}
async function probe(page, label, reduced = false) {
  assert.equal((await page.goto(base + "/_styleguide/interactions/")).status(), 200)
  await page.locator('[data-control="check"]').waitFor()
  await settle(page)
  await page.locator('[data-control="select"]').focus()
  await page.keyboard.press("Tab")
  const focus = await page.locator('[data-control="check"]').evaluate(node => ({ focused: document.activeElement === node, visible: node.matches(":focus-visible"), outline: getComputedStyle(node).outlineStyle, width: getComputedStyle(node).outlineWidth }))
  check(`${label} checkbox keyboard focus`, focus.focused && focus.visible && focus.outline !== "none" && parseFloat(focus.width) >= 2, focus)
  const control = await page.locator('[data-control="text"]').evaluate(node => ({ height: node.getBoundingClientRect().height, font: parseFloat(getComputedStyle(node).fontSize) }))
  check(`${label} text target/readability`, control.height >= 44 && control.font >= 16, control)
  const contrast = await page.evaluate(() => {
    const canvas = document.createElement("canvas")
    canvas.width = canvas.height = 1
    const ctx = canvas.getContext("2d")
    const rgb = value => { ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = value; ctx.fillRect(0, 0, 1, 1); return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map(channel => { const value = channel / 255; return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4 }) }
    const luminance = value => { const c = rgb(value); return c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722 }
    const ratio = (a, b) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05) }
    return ["primary", "text", "readonly", "invalid", "select"].map(key => {
      const node = document.querySelector(`[data-control="${key}"]`), style = getComputedStyle(node)
      return { key, text: ratio(style.color, style.backgroundColor), border: key === "primary" ? null : ratio(style.borderColor, style.backgroundColor), foreground: style.color, background: style.backgroundColor }
    })
  })
  check(`${label} text contrast`, contrast.every(item => item.text >= 4.5), contrast)
  check(`${label} control boundary contrast`, contrast.every(item => item.border === null || item.border >= 3), contrast)
  const quiet = await page.locator('[data-polish="buttons"] .c-btn--sm').evaluate(node => ({ coarse: matchMedia("(pointer: coarse)").matches, height: node.getBoundingClientRect().height, width: node.getBoundingClientRect().width }))
  check(`${label} compact touch target`, !quiet.coarse || quiet.height >= 44 && quiet.width >= 44, quiet)
  const mixed = await page.locator('[data-control="mixed"]').evaluate(node => ({ mixed: node.indeterminate, mark: getComputedStyle(node).backgroundImage }))
  check(`${label} indeterminate mark`, mixed.mixed && mixed.mark !== "none", mixed)
  await page.locator('[data-control="menu"] summary').click()
  await page.locator('[data-control="menu"] .c-menu__panel').waitFor({ state: "visible" })
  const motion = await page.locator('[data-control="menu"] .c-menu__panel').evaluate(node => ({ duration: getComputedStyle(node).animationDuration, name: getComputedStyle(node).animationName, active: node.getAnimations().length }))
  check(`${label} menu motion preference`, reduced ? parseFloat(motion.duration) < 0.001 : motion.name !== "none" && parseFloat(motion.duration) > 0.1, motion)
  if (!baseline && !reduced) await motionFrame(page, '[data-control="menu"] .c-menu__panel', label + "-menu")
  await page.waitForTimeout(250)
  await snap(page, label + "-menu-open")
  await page.keyboard.press("Escape")
  check(`${label} menu Escape`, await page.locator('[data-control="menu"]').evaluate(node => !node.open), {})
  await page.locator('[data-control="dialog-open"]').click()
  await page.locator('[data-control="dialog"]').waitFor()
  const dialog = await page.locator('[data-control="dialog"]').evaluate(node => ({ open: node.open, focused: node.contains(document.activeElement), height: node.getBoundingClientRect().height, viewport: innerHeight, duration: getComputedStyle(node).animationDuration }))
  check(`${label} dialog focus/bounds`, dialog.open && dialog.focused && dialog.height <= dialog.viewport, dialog)
  if (!baseline && !reduced) await motionFrame(page, '[data-control="dialog"]', label + "-dialog")
  await page.waitForTimeout(260)
  await snap(page, label + "-dialog")
  await page.keyboard.press("Escape")
  check(`${label} dialog Escape`, await page.locator('[data-control="dialog"]').evaluate(node => !node.open), {})
  check(`${label} dialog returns focus`, await page.locator('[data-control="dialog-open"]').evaluate(node => node === document.activeElement), {})
  if (label === "1280-light" || label === "1280-light-reduced") {
    await page.locator('[data-control="save"]').click()
    check(`${label} busy feedback`, await page.locator('[data-control="save"]').getAttribute("aria-busy") === "true" && (await page.locator("[data-autosave-status]").innerText()).includes("正在保存"), {})
    await page.waitForTimeout(700)
    check(`${label} completed feedback`, (await page.locator("[data-autosave-status]").innerText()).includes("已保存"), {})
    await page.evaluate(() => {
      window.polishMessages = []
      const tracked = new Map()
      const observer = new MutationObserver(() => {
        for (const node of document.querySelectorAll(".c-toast")) {
          if (!tracked.has(node)) {
            const entry = { text: node.textContent, appeared: performance.now() }
            tracked.set(node, entry)
            window.polishMessages.push(entry)
            setTimeout(() => {
              const style = getComputedStyle(node)
              entry.readableAtFourSeconds = node.isConnected && !node.classList.contains("is-leaving") && style.visibility === "visible" && Number(style.opacity) >= 0.99
            }, 4000)
          }
          const entry = tracked.get(node)
          if (node.classList.contains("is-leaving") && entry.leaving === undefined) {
            entry.leaving = performance.now()
            entry.exitDuration = getComputedStyle(node).animationDuration
          }
        }
        for (const [node, entry] of tracked) if (!node.isConnected && entry.removed === undefined) entry.removed = performance.now()
        if (window.polishMessages.length === 2 && window.polishMessages.every(entry => entry.removed !== undefined)) observer.disconnect()
      })
      observer.observe(document.querySelector(".c-toasts"), { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] })
    })
    await page.locator('[data-control="toast"]').click()
    await page.locator('[data-control="flash"]').click()
    await page.waitForFunction(() => window.polishMessages.length === 2 && window.polishMessages.every(entry => entry.removed !== undefined), null, { timeout: 8000 })
    const messages = await page.evaluate(() => window.polishMessages)
    check(`${label} messages retain reading time`, messages.length === 2 && messages.every(entry => entry.readableAtFourSeconds && entry.leaving - entry.appeared >= 4480), messages)
    check(`${label} messages exit before removal`, messages.length === 2 && messages.every(entry => entry.removed - entry.leaving >= 190 && (reduced ? parseFloat(entry.exitDuration) < 0.001 : parseFloat(entry.exitDuration) >= 0.18)), messages)
    check(`${label} messages removed`, await page.locator(".c-toast").count() === 0, messages)
    if (engine === "chromium" && !reduced) {
      await page.emulateMedia({ forcedColors: "active" })
      const forced = await page.locator('[data-control="check"]').evaluate(node => ({ active: matchMedia("(forced-colors: active)").matches, appearance: getComputedStyle(node).appearance }))
      check("forced colors retain native check control", forced.active && forced.appearance !== "none", forced)
      await snap(page, label + "-forced-colors")
      await page.emulateMedia({ forcedColors: "none" })
    }
  }
  await page.locator("h1").click()
  await snap(page, label + "-controls")
}
try {
  const widths = engine === "webkit" ? [375, 1280] : [375, 768, 1280]
  for (const width of widths) for (const theme of ["light", "dark"]) {
    const label = `${width}-${theme}`
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, hasTouch: width < 1000, reducedMotion: "no-preference" })
    await context.addInitScript(choice => { localStorage.setItem("ow-theme", choice); window.polishCsp = []; document.addEventListener("securitypolicyviolation", event => window.polishCsp.push(event.violatedDirective)) }, theme)
    const page = await context.newPage()
    observe(page)
    await identity(context, "officer")
    await probe(page, label)
    await page.emulateMedia({ reducedMotion: "reduce" })
    await probe(page, label + "-reduced", true)
    await page.emulateMedia({ reducedMotion: "no-preference" })
    if (engine === "chromium" && !probeOnly) {
      assert.equal((await page.goto(base + "/_styleguide/components/")).status(), 200)
      await settle(page)
      for (const sample of await page.locator("[data-sample]").all()) {
        const id = await sample.getAttribute("data-sample")
        const name = await sample.locator("h2").first().innerText()
        await sample.screenshot({ path: join(shots, `${label}-component-${id}.png`) })
        samples.push({ label, id, name, image: `${label}-component-${id}.png` })
      }
      for (const [name, path, who] of [...front, ...admin]) {
        await identity(context, who)
        const response = await page.goto(base + path)
        assert.equal(response.status(), 200, `${label} ${path}`)
        await page.locator("main h1, .b-head h1").first().waitFor()
        await settle(page)
        const state = await page.evaluate(() => ({ title: document.title, width: innerWidth, scroll: document.documentElement.scrollWidth, csp: window.polishCsp, broken: [...document.images].filter(image => image.complete && !image.naturalWidth).map(image => image.src) }))
        assert.deepEqual(state.csp, [], path)
        assert.deepEqual(state.broken, [], path)
        check(`${label} ${name} bounds`, state.scroll <= state.width + 1, state)
        const image = await snap(page, label + "-" + name)
        results.push({ label, name, path, ...state, image })
      }
    }
    await context.close()
  }
  const context = await browser.newContext({ javaScriptEnabled: false, reducedMotion: "reduce", viewport: { width: 375, height: 900 } })
  const page = await context.newPage()
  assert.equal((await page.goto(base + "/accounts/login/")).status(), 200)
  await page.waitForTimeout(300)
  const early = await page.locator(".c-nojs").evaluate(node => ({ visibility: getComputedStyle(node).visibility, delay: getComputedStyle(node).animationDelay }))
  check("reduced motion keeps no-script grace period", early.visibility === "hidden" && parseFloat(early.delay) >= 8, early)
  await page.waitForTimeout(8000)
  check("no-script notice eventually appears", await page.locator(".c-nojs").isVisible(), {})
  await context.close()
  assert.deepEqual(errors, [], "Runtime, network or hydration errors")
  writeFileSync(join(shots, "results.json"), JSON.stringify({ phase, engine, pages: results.length, samples, results, diagnostics }, null, 2))
  console.log(`POLISH-${phase.toUpperCase()} ${engine}: ${results.length} page views, ${diagnostics.length} checks, ${diagnostics.filter(item => !item.pass).length} target gaps`)
} finally { await browser.close() }
