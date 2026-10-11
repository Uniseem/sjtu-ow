export type RevisionLine = { kind: "same" | "added" | "removed"; text: string; before: number | null; after: number | null }

/**
 * The display compares bounded paragraphs, retaining all text when a full LCS
 * would exceed the editor's budget. It never interprets Markdown as HTML.
 */
export function revisionLines(before: string, after: string): RevisionLine[] {
  const left = before.replace(/\r\n/g, "\n").split("\n")
  const right = after.replace(/\r\n/g, "\n").split("\n")
  let prefix = 0
  while (prefix < left.length && prefix < right.length && left[prefix] === right[prefix]) prefix++
  let suffix = 0
  while (suffix < left.length - prefix && suffix < right.length - prefix
    && left[left.length - suffix - 1] === right[right.length - suffix - 1]) suffix++
  const output: RevisionLine[] = []
  for (let index = 0; index < prefix; index++) {
    output.push({ kind: "same", text: left[index] ?? "", before: index + 1, after: index + 1 })
  }
  const oldMiddle = left.slice(prefix, left.length - suffix)
  const newMiddle = right.slice(prefix, right.length - suffix)
  if (oldMiddle.length * newMiddle.length > 100000) {
    for (let index = 0; index < oldMiddle.length; index++) output.push({ kind: "removed", text: oldMiddle[index] ?? "", before: prefix + index + 1, after: null })
    for (let index = 0; index < newMiddle.length; index++) output.push({ kind: "added", text: newMiddle[index] ?? "", before: null, after: prefix + index + 1 })
  } else {
    const width = newMiddle.length + 1
    const lengths = new Uint32Array((oldMiddle.length + 1) * width)
    for (let i = oldMiddle.length - 1; i >= 0; i--) {
      for (let j = newMiddle.length - 1; j >= 0; j--) {
        lengths[i * width + j] = oldMiddle[i] === newMiddle[j]
          ? (lengths[(i + 1) * width + j + 1] ?? 0) + 1
          : Math.max(lengths[(i + 1) * width + j] ?? 0, lengths[i * width + j + 1] ?? 0)
      }
    }
    let i = 0
    let j = 0
    while (i < oldMiddle.length || j < newMiddle.length) {
      if (i < oldMiddle.length && j < newMiddle.length && oldMiddle[i] === newMiddle[j]) {
        output.push({ kind: "same", text: oldMiddle[i] ?? "", before: prefix + i + 1, after: prefix + j + 1 })
        i++
        j++
      } else if (j < newMiddle.length && (i >= oldMiddle.length || (lengths[i * width + j + 1] ?? 0) >= (lengths[(i + 1) * width + j] ?? 0))) {
        output.push({ kind: "added", text: newMiddle[j] ?? "", before: null, after: prefix + j + 1 })
        j++
      } else {
        output.push({ kind: "removed", text: oldMiddle[i] ?? "", before: prefix + i + 1, after: null })
        i++
      }
    }
  }
  for (let index = suffix; index > 0; index--) {
    const leftIndex = left.length - index
    const rightIndex = right.length - index
    output.push({ kind: "same", text: left[leftIndex] ?? "", before: leftIndex + 1, after: rightIndex + 1 })
  }
  return output
}
