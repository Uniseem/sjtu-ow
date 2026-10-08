// What the right-click menu offers, as a pure plan (design 13.2.6, v6.65):
// groups of entries, each a label, an optional keyboard hint, and how to
// run it. The component below collects the context from the DOM and maps
// the kinds onto window and clipboard.
export type MenuContext = {
  href: string | null // the closest link, javascript: links excluded
  imageSrc: string | null // the closest image
  selection: string // the trimmed text selection
  scrolled: boolean // the page is scrolled down
  pageUrl: string // this page, for 复制本页链接
}

export type MenuKind = "open-url" | "copy" | "search" | "back" | "forward" | "reload" | "scroll-top"

export type MenuEntry = { label: string; hint?: string; kind: MenuKind; arg?: string }

export function shorten(text: string, most: number): string {
  const flat = text.replace(/\s+/g, " ").trim()
  return flat.length > most ? flat.slice(0, most) + "…" : flat
}

export function planGroups(target: MenuContext): MenuEntry[][] {
  const groups: MenuEntry[][] = []
  if (target.href !== null) {
    groups.push([
      { label: "在新标签页打开", kind: "open-url", arg: target.href },
      { label: "复制链接", kind: "copy", arg: target.href },
    ])
  }
  if (target.imageSrc !== null) {
    groups.push([
      { label: "在新标签页打开图片", kind: "open-url", arg: target.imageSrc },
      { label: "复制图片地址", kind: "copy", arg: target.imageSrc },
    ])
  }
  if (target.selection !== "") {
    groups.push([
      { label: "复制", hint: "Ctrl+C", kind: "copy", arg: target.selection },
      { label: `在站内搜索“${shorten(target.selection, 10)}”`, kind: "search", arg: shorten(target.selection, 60) },
    ])
  }
  groups.push([
    { label: "后退", hint: "Alt+←", kind: "back" },
    { label: "前进", hint: "Alt+→", kind: "forward" },
    { label: "刷新", hint: "F5", kind: "reload" },
  ])
  const more: MenuEntry[] = [{ label: "复制本页链接", kind: "copy", arg: target.pageUrl }]
  if (target.scrolled) {
    more.push({ label: "回到顶部", kind: "scroll-top" })
  }
  groups.push(more)
  return groups
}
