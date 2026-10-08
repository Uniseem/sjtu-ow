import { afterEach, beforeEach, expect, test, vi } from "vitest"
import { Loadbar, progressFromMatrix, type LoadbarRoot } from "./loadbar"
import { planGroups, shorten, type MenuContext } from "./contextmenu-entries"
import { toast, toasts } from "./toasts"

// ---- the route loadbar ------------------------------------------------------

function fakeRoot() {
  const classes = new Set<string>()
  const properties: Record<string, string> = {}
  const root: LoadbarRoot = {
    classList: {
      add: (name) => classes.add(name),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
    },
    style: { setProperty: (name, value) => (properties[name] = value) },
  }
  return { root, classes, properties }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

test("the bar crawls on start and finishes where it got to", () => {
  const { root, classes, properties } = fakeRoot()
  const bar = new Loadbar(root, () => 0.5)
  bar.start()
  expect(classes.has("is-loading")).toBe(true)
  bar.arrive()
  expect(classes.has("is-loading")).toBe(false)
  expect(classes.has("is-arriving")).toBe(true)
  expect(properties["--loadbar-from"]).toBe("0.5")
  vi.advanceTimersByTime(600)
  expect(classes.has("is-arriving")).toBe(false)
})

test("a stuck navigation stops crawling, and stop clears at once", () => {
  const { root, classes } = fakeRoot()
  const bar = new Loadbar(root, () => 0.2)
  bar.start()
  vi.advanceTimersByTime(15000)
  expect(classes.has("is-loading")).toBe(false)

  bar.start()
  bar.stop()
  expect(classes.size).toBe(0)
})

test("the crawl position is read from the transform matrix", () => {
  expect(progressFromMatrix("matrix(0.42, 0, 0, 1, 0, 0)")).toBe(0.42)
  expect(progressFromMatrix("none")).toBe(0)
  expect(progressFromMatrix(null)).toBe(0)
})

// ---- the right-click menu's plan --------------------------------------------

function context(over: Partial<MenuContext> = {}): MenuContext {
  return { href: null, imageSrc: null, selection: "", scrolled: false, pageUrl: "https://ow.example/teams/", ...over }
}

function labels(groups: ReturnType<typeof planGroups>): string[] {
  return groups.flat().map((entry) => entry.label)
}

test("a link offers opening and copying; an image its own group", () => {
  const groups = planGroups(context({ href: "https://ow.example/news/1/", imageSrc: "https://ow.example/img.png" }))
  expect(labels(groups)).toEqual([
    "在新标签页打开",
    "复制链接",
    "在新标签页打开图片",
    "复制图片地址",
    "后退",
    "前进",
    "刷新",
    "复制本页链接",
  ])
})

test("a selection can be copied and searched, truncated for the label", () => {
  const groups = planGroups(context({ selection: "  上海交通大学 守望先锋 社区  " }))
  expect(labels(groups)).toContain("复制")
  expect(labels(groups)).toContain("在站内搜索“上海交通大学 守望先…”")
  const search = groups.flat().find((entry) => entry.kind === "search")
  expect(search?.arg).toBe("上海交通大学 守望先锋 社区")
  expect(shorten("abcdefghij", 10)).toBe("abcdefghij")
})

test("scrolling adds 回到顶部; the page group is always there", () => {
  const flat = labels(planGroups(context({ scrolled: true })))
  expect(flat.at(-1)).toBe("回到顶部")
  expect(flat).toEqual(["后退", "前进", "刷新", "复制本页链接", "回到顶部"])
  const hints = planGroups(context({ scrolled: false }))
    .flat()
    .filter((entry) => entry.hint)
    .map((entry) => entry.hint)
  expect(hints).toEqual(["Alt+←", "Alt+→", "F5"])
})

// ---- toasts ------------------------------------------------------------------

test("a toast appears and leaves on its own", () => {
  toast("已保存", "success")
  toast("出错了", "error")
  expect(toasts.map((item) => item.text)).toEqual(["已保存", "出错了"])
  expect(toasts[0].kind).toBe("success")
  vi.advanceTimersByTime(4500)
  expect(toasts.length).toBe(0)
})
