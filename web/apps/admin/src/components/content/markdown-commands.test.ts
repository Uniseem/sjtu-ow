import { expect, test } from "vitest"
import { EditorState } from "@codemirror/state"
import { commandEdit, insertVideo, type TextEdit } from "./markdown-commands"

function apply(source: string, edit: TextEdit): string {
  return EditorState.create({ doc: source }).update({
    changes: { from: edit.from, to: edit.to, insert: edit.insert },
    selection: { anchor: edit.anchor, head: edit.head ?? edit.anchor },
  }).state.doc.toString()
}

test("third-level heading replaces a second-level heading and toggles off through actual editor transactions", () => {
  const source = "开头\n## 小标题\n正文"
  const edit = commandEdit("heading3", { text: source, from: 6, to: 9 })
  const third = apply(source, edit)
  expect(third).toBe("开头\n### 小标题\n正文")
  const second = apply(third, commandEdit("heading", { text: third, from: 7, to: 10 }))
  expect(second).toBe(source)
  expect(apply(third, commandEdit("heading3", { text: third, from: 7, to: 10 }))).toBe("开头\n小标题\n正文")
})

test("third-level heading applies to selected complete lines without swallowing surrounding text", () => {
  const source = "之前\n一\n二\n之后"
  expect(apply(source, commandEdit("heading3", { text: source, from: 3, to: 6 }))).toBe("之前\n### 一\n### 二\n之后")
})

test("Bilibili button replaces the selected placeholder with a standalone URL and preserves the rest of the document", () => {
  const source = "之前占位之后"
  const edit = insertVideo({ text: source, from: 2, to: 4 }, "  https://www.bilibili.com/video/BV1xx411c7mD/  ")
  expect(edit).not.toBeNull()
  expect(apply(source, edit!)).toBe("之前\n\nhttps://www.bilibili.com/video/BV1xx411c7mD/\n\n之后")
  expect(insertVideo({ text: source, from: 2, to: 4 }, null)).toBeNull()
  expect(insertVideo({ text: source, from: 2, to: 4 }, "   ")).toBeNull()
})
