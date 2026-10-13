// Invoke on a fresh, writable seeded editor page. Exercises real Vue/CodeMirror
// controls and the server preview; it intentionally changes the draft body.
export async function exerciseMarkdownEditor(page) {
  const beganAsNew = new URL(page.url()).pathname === "/admin/articles/new/"
  const editor = page.locator("div[data-markdown-editor]").first()
  const source = editor.locator(".cm-content")
  await source.waitFor({ state: "visible" })
  const writingSession = await editor.elementHandle()
  const backing = editor.locator("textarea[data-markdown-source]")
  await source.fill("小标题")
  await editor.locator('[data-markdown-command="heading3"]').click()
  if (await backing.inputValue() !== "### 小标题") throw new Error("三级标题没有写进真实编辑正文")
  await editor.locator('[data-markdown-command="heading"]').click()
  if (await backing.inputValue() !== "## 小标题") throw new Error("二级标题没有替换既有三级标题")

  await source.fill("视频占位")
  await source.press(process.platform === "darwin" ? "Meta+A" : "Control+A")
  page.expectedMarkdownPrompt = "粘贴 B 站视频链接（bilibili.com/video/… 或 b23.tv/…）："
  page.once("dialog", async dialog => {
    if (dialog.type() !== "prompt" || dialog.message() !== page.expectedMarkdownPrompt) throw new Error("B站视频没有打开链接输入")
    await dialog.accept("https://www.bilibili.com/video/BV1xx411c7mD/")
    delete page.expectedMarkdownPrompt
  })
  await editor.locator('[data-markdown-command="video"]').click()
  if (!(await backing.inputValue()).includes("https://www.bilibili.com/video/BV1xx411c7mD/")) throw new Error("视频链接没有写进真实编辑正文")

  await source.fill("并排初始正文")
  await editor.locator('[data-markdown-command="side-by-side"]').click()
  await editor.locator("iframe").waitFor({ state: "visible" })
  if (!(await source.isVisible())) throw new Error("并排预览隐藏了正文编辑区")
  await editor.frameLocator("iframe").getByText("并排初始正文", { exact: false }).first().waitFor({ state: "visible" })
  await source.fill("并排修改后的正文")
  if (await backing.inputValue() !== "并排修改后的正文") throw new Error("并排编辑没有更新实际Markdown源字段")
  try {
    await editor.frameLocator("iframe").getByText("并排修改后的正文", { exact: false }).first().waitFor({ state: "visible" })
  } catch (cause) {
    const state = await editor.evaluate(node => ({
      sideBySide: node.querySelector('[data-markdown-command="side-by-side"]')?.getAttribute("aria-pressed"),
      frame: Boolean(node.querySelector("iframe")),
      message: node.querySelector('[aria-label="正文预览"]')?.textContent,
    })).catch(() => null)
    throw new Error("并排预览没有更新：" + JSON.stringify({ path: new URL(page.url()).pathname, state }), { cause })
  }
  if (beganAsNew) {
    await page.waitForURL(/\/admin\/articles\/\d+\/$/)
    if (!writingSession || !await writingSession.evaluate(node => node.isConnected)) throw new Error("新稿更新网址销毁了当前Markdown编辑实例")
    if (await editor.locator('[data-markdown-command="side-by-side"]').getAttribute("aria-pressed") !== "true") throw new Error("新稿更新网址丢失了并排预览模式")
    await editor.frameLocator("iframe").getByText("并排修改后的正文", { exact: false }).first().waitFor({ state: "visible" })
  }
  await editor.locator('[data-markdown-command="side-by-side"]').click()

  const fullscreen = editor.locator('[data-markdown-command="fullscreen"]')
  await fullscreen.click()
  const geometry = await editor.evaluate(node => {
    const rect = node.getBoundingClientRect()
    return { fixed: getComputedStyle(node).position === "fixed", x: rect.x, y: rect.y,
      width: rect.width, height: rect.height, viewportWidth: document.documentElement.clientWidth, viewportHeight: innerHeight }
  })
  if (!geometry.fixed || geometry.x !== 0 || geometry.y !== 0 || Math.abs(geometry.width - geometry.viewportWidth) > 1 || Math.abs(geometry.height - geometry.viewportHeight) > 1) {
    throw new Error("全屏没有覆盖实际视口：" + JSON.stringify(geometry))
  }
  await source.press("Escape")
  if (await fullscreen.getAttribute("aria-pressed") !== "false") throw new Error("Escape没有退出全屏")
  if (!(await fullscreen.evaluate(node => document.activeElement === node))) throw new Error("退出全屏没有将焦点返回原按钮")
  if (await editor.evaluate(node => node.querySelectorAll("[style]").length)) throw new Error("编辑器模式切换引入Light DOM内联style")
}
