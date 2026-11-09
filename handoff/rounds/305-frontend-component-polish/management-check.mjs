import assert from "node:assert/strict"
import { createRequire } from "node:module"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { join } from "node:path"
const { base, output, sessions, data } = JSON.parse(readFileSync(process.argv[2], "utf8"))
const { chromium } = createRequire(join(process.argv[3], "web/package.json"))("playwright")
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true })
const out = join(output, "chromium")
mkdirSync(out, { recursive: true })
const results = [], errors = []
try {
  for (const width of [375, 768, 1280]) for (const theme of ["light", "dark"]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme, hasTouch: width < 1000 })
    await context.addInitScript(choice => localStorage.setItem("ow-theme", choice), theme)
    await context.addCookies([{ name: "ow_session", value: sessions.officer, url: base }])
    const page = await context.newPage()
    page.on("pageerror", error => errors.push(String(error)))
    await page.goto(base + "/admin/users/")
    const roles = page.locator('td[data-label="角色"]')
    await roles.first().waitFor()
    await page.evaluate(() => document.fonts.ready)
    const state = await roles.evaluateAll(nodes => nodes.map(node => ({ text: node.textContent, tags: [...node.querySelectorAll(".c-tag")].map(tag => ({ left: tag.getBoundingClientRect().left, right: tag.getBoundingClientRect().right, top: tag.getBoundingClientRect().top })) })))
    assert(state.some(row => row.text.trim() === "—"), "System-only roles must have a visible empty value")
    for (const row of state) for (let index = 1; index < row.tags.length; index++) {
      const previous = row.tags[index - 1], current = row.tags[index]
      if (Math.abs(previous.top - current.top) < 1) assert(current.left - previous.right <= 5, "Related role tags must stay grouped")
    }
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    await page.screenshot({ path: join(out, `${width}-${theme}-users.png`), fullPage: true })
    const themeMenu = page.locator("details.c-theme")
    await themeMenu.locator("summary").click()
    await themeMenu.getByRole("button", { name: theme === "light" ? "浅色" : "深色", exact: true }).click()
    assert(await themeMenu.evaluate(node => !node.open && node.querySelector("summary") === document.activeElement), "Admin theme returns focus")

    await page.goto(base + `/admin/articles/${data.article}/`)
    const editor = page.locator(".cm-editor").first()
    await editor.waitFor()
    const code = await editor.evaluate(node => {
      const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d")
      canvas.width = canvas.height = 1
      const luminance = color => {
        ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1)
        const rgb = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map(value => { const c = value / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4 })
        return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722
      }
      const background = luminance(getComputedStyle(node).backgroundColor)
      return { font: getComputedStyle(node.querySelector(".cm-content")).fontFamily, minHeight: parseFloat(getComputedStyle(node).minHeight), syntax: [...node.querySelectorAll(".cm-line span")].map(span => { const foreground = luminance(getComputedStyle(span).color); return { text: span.textContent, ratio: (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05) } }) }
    })
    assert(code.syntax.length > 0 && code.syntax.every(span => span.ratio >= 4.5), JSON.stringify(code))
    assert(code.font.includes("monospace"), code.font)
    assert.equal(code.minHeight, width <= 768 ? 288 : 384)
    const toolbar = page.locator(".markdown-editor__toolbar").first()
    const targets = await toolbar.locator("button:visible").evaluateAll(nodes => nodes.map(node => ({ width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height })))
    if (width < 1000) assert(targets.every(target => target.height >= 44 && target.width >= 44), JSON.stringify(targets))
    await page.screenshot({ path: join(out, `${width}-${theme}-editor.png`), fullPage: true })
    results.push({ width, theme, roleRows: state.length, code, targets })
    console.log(`PASS MANAGEMENT ${width} ${theme}: grouped roles; theme focus; editor contrast/font/size/targets`)
    if (width >= 768) {
      await page.goto(base + "/")
      const menu = page.locator("details.c-theme").first()
      await menu.locator("summary").click()
      await menu.getByRole("button", { name: theme === "light" ? "浅色" : "深色", exact: true }).click()
      assert(await menu.evaluate(node => !node.open && node.querySelector("summary") === document.activeElement), "Site theme returns focus")
    }
    await context.close()
  }
  assert.deepEqual(errors, [])
  writeFileSync(join(out, "management.json"), JSON.stringify(results, null, 2))
} finally { await browser.close() }
