// Invoke on a fresh, writable seeded editor page. Exercises real Vue/CodeMirror
// controls and the server preview; it intentionally changes the draft body.
export async function exerciseMarkdownEditor(page) {
  const editor = page.locator("div[data-markdown-editor]").first()
  const source = editor.locator(".cm-content")
  await source.waitFor({ state: "visible" })
  const backing = editor.locator("textarea[data-markdown-source]")
  await source.fill("小标题")
  await editor.locator('[data-markdown-command="heading3"]').click()
  if (await backing.inputValue() !== "### 小标题") throw new Error("三级标题没有写进真实编辑正文")
  await editor.locator('[data-markdown-command="heading"]').click()
  if (await backing.inputValue() !== "## 小标题") throw new Error("二级标题没有替换既有三级标题")

  await source.fill("视频占位")
  await source.press(process.platform === "darwin" ? "Meta+A" : "Control+A")
  page.once("dialog", async dialog => {
    if (dialog.type() !== "prompt") throw new Error("B站视频没有打开链接输入")
    await dialog.accept("https://www.bilibili.com/video/BV1xx411c7mD/")
  })
  await editor.locator('[data-markdown-command="video"]').click()
  if (!(await backing.inputValue()).includes("https://www.bilibili.com/video/BV1xx411c7mD/")) throw new Error("视频链接没有写进真实编辑正文")

  await source.fill("并排初始正文")
  await editor.locator('[data-markdown-command="side-by-side"]').click()
  await editor.locator("iframe").waitFor({ state: "visible" })
  if (!(await source.isVisible())) throw new Error("并排预览隐藏了正文编辑区")
  await editor.frameLocator("iframe").getByText("并排初始正文", { exact: false }).first().waitFor({ state: "visible" })
  await source.fill("并排修改后的正文")
  await editor.frameLocator("iframe").getByText("并排修改后的正文", { exact: false }).first().waitFor({ state: "visible" })
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
