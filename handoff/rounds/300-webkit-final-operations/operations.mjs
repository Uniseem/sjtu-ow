import { readFileSync, writeFileSync } from "node:fs"
import { createRequire } from "node:module"
import { resolve } from "node:path"
const root = resolve(import.meta.dirname, "../../..")
const { webkit } = createRequire(resolve(root, "web/package.json"))("playwright")
const config = JSON.parse(readFileSync(process.argv[2], "utf8"))
const browser = await webkit.launch()
const context = await browser.newContext({ baseURL: config.base, viewport: { width: 1280, height: 900 }, reducedMotion: "reduce" })
await context.addCookies([{ name: "ow_session", value: config.sessions.officer, url: config.base }])
const errors = [], checks = [], results = []
await context.addInitScript(() => document.addEventListener("securitypolicyviolation", event => {
  console.error("OPERATIONS-CSP", event.violatedDirective, event.blockedURI)
}))
const page = await context.newPage()
page.setDefaultTimeout(15000)
page.on("pageerror", error => errors.push("runtime " + error.message))
page.on("console", message => {
  if (message.type() === "error" || /Hydration/i.test(message.text())) errors.push("console " + message.text())
})
page.on("response", response => {
  if (response.status() >= 500) errors.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`)
})
page.on("dialog", async dialog => {
  errors.push(`unexpected dialog ${dialog.type()}: ${dialog.message()}`)
  await dialog.dismiss()
})
const check = (name, condition) => {
  if (!condition) throw new Error(name)
  checks.push(name)
  console.log("PASS OPERATIONS " + name)
}
async function go(path) {
  const response = await page.goto(path)
  if (!response?.ok()) throw new Error("page status " + response?.status())
  await page.waitForFunction(() => document.readyState === "complete" && document.querySelector("#admin-app #main") && ![...document.querySelectorAll('[role=status]')].some(node => /^正在加载…$|^加载中…$/.test(node.textContent.trim())))
}
async function json(path) {
  const response = await context.request.get(path)
  if (!response.ok()) throw new Error(`API ${path}: ${response.status()}`)
  return response.json()
}
async function cleanSave() {
  await page.waitForFunction(() => {
    const nodes = [...document.querySelectorAll('[data-autosave-status]')]
    return nodes.length && nodes.every(node => node.dataset.state === "saved" && !node.textContent.includes("尚未保存"))
  })
}
async function operation(name, run) {
  if (config.only !== "all" && config.only !== name) return
  try { await run(); results.push({ name, passed: true }) }
  catch (error) {
    results.push({ name, passed: false, error: error.stack })
    console.error("FAIL OPERATIONS", name, error.stack)
    writeFileSync(resolve(config.work, `out/${name}-failure.json`), JSON.stringify({ path: new URL(page.url()).pathname, text: await page.locator('#main').innerText().catch(() => ''), editor: await page.locator('.cm-content').first().textContent().catch(() => null), source: await page.locator('textarea[data-markdown-source]').first().inputValue().catch(() => null), errors }, null, 2))
    await page.close()
    throw error
  }
}
try {
  await operation("split-copy", async () => {
    await go(`/admin/scrims/${config.data.scrim}/split/`)
    const choices = page.locator("table input[type=checkbox]")
    check("ten directly seeded scrim signups", await choices.count() === 10)
    for (const checkbox of await choices.all()) await checkbox.check()
    await page.getByRole("button", { name: "生成分队", exact: true }).click()
    await page.locator('[data-split-board] [data-team-panel=a]').waitFor()
    await page.getByRole("button", { name: "复制", exact: true }).click()
    await page.waitForFunction(() => {
      const source = document.querySelector('textarea[aria-label="分队结果"]')
      return document.querySelector('[data-split-copy]')?.innerText.includes('已复制') || Boolean(source?.value.length && source.selectionStart === 0 && source.selectionEnd === source.value.length)
    })
    const outcome = await page.evaluate(() => {
      const source = document.querySelector('textarea[aria-label="分队结果"]')
      return { copied: document.querySelector('[data-split-copy]')?.innerText.includes('已复制'), selected: Boolean(source?.value.length && source.selectionStart === 0 && source.selectionEnd === source.value.length), text: source?.value }
    })
    check("copy succeeds or selects entire nonempty result", Boolean((outcome.copied || outcome.selected) && outcome.text?.includes("操作队员")))
    console.log("COPY-RESULT " + JSON.stringify({ copied: outcome.copied, selected: outcome.selected, length: outcome.text.length }))
  })
  await operation("teams-letters", async () => {
    const path = `/admin/tournaments/${config.data.cup}/teams/`
    await go(path)
    const name = "操作检查队伍"
    await page.locator('[data-team-panel]').last().locator("input").fill(name)
    const signups = []
    for (let index = 0; index < 3; index++) {
      const card = page.locator('[data-board-zone=""] [data-signup]').first()
      signups.push(Number(await card.getAttribute("data-signup")))
      await card.getByRole("button", { name, exact: true }).click()
    }
    const saving = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/admin/tournaments/${config.data.cup}/board` && response.ok())
    await page.getByRole("button", { name: "保存编队", exact: true }).click()
    const receipt = await (await saving).json()
    check("real board save returned held letters", Boolean(receipt.letters?.batch && receipt.letters.count > 0))
    await page.waitForURL("**/admin/letters/**")
    check("held letters back path is saved board", new URL(page.url()).searchParams.get("back") === path)
    const held = await json(`/api/letters/${receipt.letters.batch}`)
    check("held batch covers all three members", held.letters.reduce((total, letter) => total + letter.count, 0) === 3)
    await page.locator("#main button[type=submit]").filter({ hasText: /发出|发送|决定|确认/ }).first().click()
    await page.waitForURL(url => url.pathname === path)
    const savedMembers = name => [...document.querySelectorAll('[data-team-panel]')].find(zone => zone.querySelector('input')?.value === name)?.querySelectorAll('[data-signup]').length
    await page.waitForFunction(name => [...document.querySelectorAll('[data-team-panel]')].some(zone => zone.querySelector('input')?.value === name && zone.querySelectorAll('[data-signup]').length === 3), name)
    check("confirmation returns with three saved members", await page.evaluate(savedMembers, name) === 3)
    await go(path)
    check("saved name and members survive document reload", await page.locator('[data-team-panel] input').evaluateAll((nodes, name) => nodes.some(node => node.value === name), name) && await page.locator('[data-team-panel] [data-signup]').count() === 3)
    const board = await json(`/api/admin/tournaments/${config.data.cup}/board`)
    const team = board.teams.find(team => team.name === name)
    check("server board contains exact saved signup IDs", Boolean(team && team.signup_ids.length === signups.length && signups.every(id => team.signup_ids.includes(id)) && signups.every(id => board.entries.some(entry => entry.signup_id === id && entry.registration_id === team.registration_id))))
  })
  await operation("new-article", async () => {
    await go("/admin/articles/new/")
    const editor = page.locator('div[data-markdown-editor]').first()
    const source = editor.locator('.cm-content')
    await source.waitFor({ state: "visible" })
    const writingSession = await editor.elementHandle()
    const firstBody = "自动保存改网址前的正文。"
    const finalBody = "改网址后继续编辑，保存并公开发布的最终正文。"
    const saving = page.waitForResponse(response => response.request().method() === "PATCH" && /^\/api\/articles\/\d+$/.test(new URL(response.url()).pathname) && response.ok())
    await source.click()
    await source.pressSequentially(firstBody)
    await page.waitForFunction(body => document.querySelector('textarea[data-markdown-source]')?.value === body, firstBody)
    await editor.locator('[data-markdown-command="side-by-side"]').click()
    await saving
    await page.waitForURL(/\/admin\/articles\/\d+\/$/)
    const id = Number(new URL(page.url()).pathname.split("/").filter(Boolean).at(-1))
    check("new autosave updates URL without replacing editor", Boolean(writingSession && await writingSession.evaluate(node => node.isConnected)))
    check("body and preview mode survive created URL", await editor.locator('textarea[data-markdown-source]').inputValue() === firstBody && await editor.locator('[data-markdown-command="side-by-side"]').getAttribute("aria-pressed") === "true")
    await editor.frameLocator('iframe').getByText(firstBody, { exact: false }).first().waitFor({ state: "visible" })
    const updated = page.waitForResponse(response => response.request().method() === "PATCH" && new URL(response.url()).pathname === `/api/articles/${id}` && response.ok())
    await page.locator('input[name=title]').fill("操作检查真实发布")
    await page.locator('select[name=category]').selectOption(String(config.data.category))
    await source.click()
    await source.press("Control+A")
    await source.pressSequentially(finalBody)
    await editor.frameLocator('iframe').getByText(finalBody, { exact: false }).first().waitFor({ state: "visible" })
    await updated
    await cleanSave()
    const current = await json(`/api/admin/articles/${id}`)
    check("continued editing actually saved final Markdown", current.revision?.body_md === finalBody)
    await page.getByRole("button", { name: "发布", exact: true }).click()
    const published = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === `/api/articles/${id}/publish` && response.ok())
    await page.getByRole("button", { name: "确认发布", exact: true }).click()
    const publication = await (await published).json()
    check("publish receipt contains final body", publication.article?.body_md === finalBody && publication.article?.live === true)
    const publicArticle = await json(`/api/page/news/${encodeURIComponent(publication.article.slug)}`)
    check("public article contains final saved body", JSON.stringify(publicArticle).includes(finalBody))
  })
  check("zero runtime console CSP hydration and HTTP500", errors.length === 0)
  console.log(`OPERATIONS-OK webkit ${results.length} operations ${checks.length} assertions`)
} catch (error) {
  console.error("OPERATIONS-FAILED", error.stack, JSON.stringify(errors))
  process.exitCode = 1
} finally {
  writeFileSync(resolve(config.work, "out/result.json"), JSON.stringify({ results, checks, errors }, null, 2))
  await context.close()
  await browser.close()
}
