export type EditorSelection = { text: string; from: number; to: number }
export type TextEdit = { from: number; to: number; insert: string; anchor: number; head?: number }
export type MarkdownCommand = "bold" | "italic" | "strike" | "heading" | "heading3" | "quote" | "unordered" | "ordered" | "code" | "rule" | "link" | "image" | "table"

export function surround(selection: EditorSelection, before: string, after: string, fallback: string): TextEdit {
  const selected = selection.text.slice(selection.from, selection.to)
  const content = selected || fallback
  const previous = selection.text.slice(Math.max(0, selection.from - before.length), selection.from)
  const following = selection.text.slice(selection.to, selection.to + after.length)
  if (selected && previous === before && following === after) {
    return {
      from: selection.from - before.length,
      to: selection.to + after.length,
      insert: content,
      anchor: selection.from - before.length,
      head: selection.to - before.length,
    }
  }
  return {
    from: selection.from,
    to: selection.to,
    insert: before + content + after,
    anchor: selection.from + before.length,
    head: selection.from + before.length + content.length,
  }
}

export function lines(selection: EditorSelection, prefix: (index: number) => string): TextEdit {
  const start = selection.text.lastIndexOf("\n", selection.from - 1) + 1
  const next = selection.text.indexOf("\n", selection.to)
  const end = next < 0 ? selection.text.length : next
  const content = selection.text.slice(start, end)
  const insert = content.split("\n").map((line, index) => prefix(index) + line).join("\n")
  return { from: start, to: end, insert, anchor: start, head: start + insert.length }
}

/** Match the existing heading buttons: selecting an active level removes it;
 * another heading level is replaced rather than accumulating Markdown hashes. */
export function headingEdit(selection: EditorSelection, level: 2 | 3): TextEdit {
  const start = selection.from === 0 ? 0 : selection.text.lastIndexOf("\n", selection.from - 1) + 1
  const next = selection.text.indexOf("\n", selection.to)
  const end = next < 0 ? selection.text.length : next
  const current = selection.text.slice(start, end).split("\n")
  const prefix = "#".repeat(level) + " "
  const remove = current.every(line => line.startsWith(prefix))
  const insert = current.map(line => {
    const bare = line.replace(/^#{1,6}\s+/, "")
    return remove ? bare : prefix + bare
  }).join("\n")
  return { from: start, to: end, insert, anchor: start, head: start + insert.length }
}

/** The legacy video button inserts a URL on its own line; the server decides
 * how to render it, so the editor never creates HTML or embedded scripts. */
export function insertVideo(selection: EditorSelection, url: string | null): TextEdit | null {
  const link = url?.trim()
  if (!link) return null
  const insert = "\n\n" + link + "\n\n"
  return { from: selection.from, to: selection.to, insert, anchor: selection.from + insert.length }
}

export function commandEdit(command: MarkdownCommand, selection: EditorSelection): TextEdit {
  switch (command) {
    case "bold": return surround(selection, "**", "**", "加粗文字")
    case "italic": return surround(selection, "*", "*", "斜体文字")
    case "strike": return surround(selection, "~~", "~~", "删除文字")
    case "heading": return headingEdit(selection, 2)
    case "heading3": return headingEdit(selection, 3)
    case "quote": return lines(selection, () => "> ")
    case "unordered": return lines(selection, () => "- ")
    case "ordered": return lines(selection, (index) => `${index + 1}. `)
    case "code": {
      const selected = selection.text.slice(selection.from, selection.to)
      return selected.includes("\n")
        ? surround(selection, "\n```\n", "\n```\n", "代码")
        : surround(selection, "`", "`", "代码")
    }
    case "rule": return { from: selection.from, to: selection.to, insert: "\n\n---\n\n", anchor: selection.from + 7 }
    case "table": {
      const insert = "\n\n| 项目 | 说明 |\n| --- | --- |\n| 内容 | 内容 |\n\n"
      return { from: selection.from, to: selection.to, insert, anchor: selection.from + insert.length }
    }
    case "link": return surround(selection, "[", "](https://)", "链接文字")
    case "image": return surround(selection, "![", "](图片地址)", "图注")
  }
}

export function escapeImageCaption(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/\[/g, "\\[").replace(/\]/g, "\\]").replace(/\r?\n/g, " ")
}

export function insertImage(selection: EditorSelection, url: string, caption: string): TextEdit {
  const before = selection.from > 0 && selection.text[selection.from - 1] !== "\n" ? "\n\n" : ""
  const after = selection.to < selection.text.length && selection.text[selection.to] !== "\n" ? "\n\n" : "\n"
  const insert = `${before}![${escapeImageCaption(caption)}](${url})${after}`
  return { from: selection.from, to: selection.to, insert, anchor: selection.from + insert.length }
}

export const toolbarCommands: { command: MarkdownCommand; label: string; shortcut?: string }[] = [
  { command: "bold", label: "加粗", shortcut: "Ctrl+B" },
  { command: "italic", label: "斜体", shortcut: "Ctrl+I" },
  { command: "strike", label: "删除线" },
  { command: "heading", label: "二级标题" },
  { command: "heading3", label: "三级标题" },
  { command: "quote", label: "引用" },
  { command: "unordered", label: "无序列表" },
  { command: "ordered", label: "有序列表" },
  { command: "code", label: "代码" },
  { command: "rule", label: "分隔线" },
  { command: "link", label: "链接", shortcut: "Ctrl+K" },
  { command: "table", label: "表格" },
]
