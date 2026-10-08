import { expect, test } from "vitest"
import { assetsFromManifest, documentHTML, type Assets } from "../server"
import { render } from "./entry-server"
import { sectionOf } from "./sections"
import { shanghaiYear } from "./time"
import { initial } from "./initial"
import { ICONS } from "./icons"

function at(user: unknown): Parameters<typeof render>[1] {
  return {
    apiBase: "http://api.test",
    fetch: async () => new Response(JSON.stringify({ user }), { headers: { "content-type": "application/json" } }),
    headers: { get: () => null },
  }
}

async function paint(url: string, user: unknown): Promise<string> {
  const out = await render(url, at(user))
  if (out.kind !== "page") throw new Error(`not a page: ${JSON.stringify(out.kind)}`)
  return out.html
}

// The masthead nav block only: the footer repeats 战队 and the brand repeats
// the home link, so anchors must be looked up where they mean something.
function navBlock(html: string): string {
  const block = html.match(/<nav class="c-nav[^"]*"[\s\S]*?<\/nav>/)
  if (!block) throw new Error("no masthead nav")
  return block[0]
}

function anchor(html: string, href: string, label: string): string {
  // Vue SSR 在插进来的文本两边放片段注释（<!--[-->首页<!--]-->），先剥掉再配
  const clean = html.replace(/<!--.*?-->/g, "")
  const found = [...clean.matchAll(new RegExp(`<a [^>]*href="${href}"[^>]*>${label}</a>`, "g"))].map((m) => m[0])
  if (found.length !== 1) throw new Error(`expected one ${href} ${label} anchor, got ${found.length}`)
  return found[0]
}

test("a visitor gets the masthead, the nav and the footer", async () => {
  const html = await paint("/", null)
  const nav = navBlock(html)
  for (const item of [
    ["首页", "/"],
    ["资讯", "/news/"],
    ["赛事", "/tournaments/"],
    ["内战", "/scrims/"],
    ["战队", "/teams/"],
    ["成员", "/members/"],
  ] as const) {
    const a = anchor(nav, item[1], item[0])
    // 在首页上，当前项是首页，其余都不是
    expect(a.includes('aria-current="page"')).toBe(item[1] === "/")
  }
  expect(html).toContain('action="/search/"')
  expect(html).toContain('href="/accounts/login/"')
  expect(html).toContain('href="/accounts/signup/"')
  // 抽屉的「更多」对访客也画个人中心（照旧站），成员专属的是这些：
  expect(html).not.toContain("账号菜单")
  expect(html).not.toContain("我的报名")
  expect(html).not.toContain('href="/accounts/logout/"')
  expect(html).toContain("SJTU-OW 是上海交通大学守望先锋玩家的社团网站")
  expect(html).toContain(`© ${shanghaiYear()} SJTU-OW · 学生社团自办网站`)
  expect(html).toContain("游戏图片版权归暴雪娱乐所有")
  // 搜索图标真的画出来了（components/icon.html 的 search 路径）
  expect(html).toContain("M10.5 17a6.5 6.5 0 1 0 0-13")
})

test("the current nav item follows the start of the path", async () => {
  const nav = navBlock(await paint("/teams/", null))
  expect(anchor(nav, "/teams/", "战队")).toContain('aria-current="page"')
  expect(anchor(nav, "/", "首页")).not.toContain("aria-current")
  expect(sectionOf("/registrations/3/")).toBe("tournaments")
  expect(sectionOf("/me/teams/")).toBe(null)
  expect(sectionOf("/news/文章/")).toBe("news")
  expect(sectionOf("/scrims/")).toBe("scrims")
})

test("a member sees their own account area and footer column", async () => {
  const html = await paint("/", { nickname: "夜蛾", admin: false })
  expect(html).toContain("夜蛾")
  expect(html).toContain('href="/me/"')
  expect(html).toContain('href="/me/registrations/"')
  expect(html).toContain('href="/me/teams/"')
  expect(html).toContain('href="/accounts/logout/"')
  expect(html).not.toContain("管理后台")
  expect(html).not.toContain('href="/accounts/signup/"')
})

test("an admin also gets the back office link", async () => {
  const html = await paint("/", { nickname: "站长", admin: true })
  expect(html).toContain('href="/admin/"')
})

test("a session without a nickname counts as a visitor", async () => {
  const html = await paint("/", { id: 7 })
  expect(html).not.toContain("账号菜单")
  expect(html).toContain('href="/accounts/login/"')
})

test("the theme menu and the WeChat banner are painted hidden", async () => {
  const html = await paint("/", null)
  expect(html).toMatch(/<details[^>]*class="c-theme[^"]*"[^>]*hidden/)
  expect(html).toMatch(/class="c-banner c-banner--hint"[^>]*hidden/)
  expect(html).toContain("跟随系统")
  expect(html).toContain("深色")
})

test("the built assets replace the source entry", () => {
  // Vite 真实写出的形状：入口键是 index.html（entry-client 并进同一个块）
  const manifest = {
    "index.html": { file: "assets/entry-a1.js", css: ["assets/entry-a1.css"], imports: ["_vue-9.js"], isEntry: true },
    "_vue-9.js": { file: "assets/vue-9.js", css: ["assets/vue-9.css"] },
  }
  const assets: Assets = assetsFromManifest(manifest)
  expect(assets).toEqual({
    entry: "/assets/entry-a1.js",
    css: ["/assets/entry-a1.css"],
    preloads: ["/assets/vue-9.js", "/assets/vue-9.css"],
  })
  // 源码模块作入口键时也一样认
  const bySource = assetsFromManifest({
    "src/entry-client.ts": { file: "assets/entry-b2.js" },
  })
  expect(bySource?.entry).toBe("/assets/entry-b2.js")
  const out = documentHTML({ head: "", html: "", state: { data: null, viewer: { user: null } }, assets })
  expect(out).toContain('<script type="module" src="/assets/entry-a1.js">')
  expect(out).toContain('<link rel="stylesheet" href="/assets/entry-a1.css">')
  expect(out).toContain('<link rel="modulepreload" href="/assets/vue-9.js">')
  expect(out).not.toContain("/src/entry-client.ts")
  // 开发态（没有清单）：仍指源码入口，交给 Vite 的中间件
  const dev = documentHTML({ head: "", html: "", state: { data: null, viewer: { user: null } }, assets: null })
  expect(dev).toContain('src="/src/entry-client.ts"')
  // 错误页（state null）：有样式、theme.js 还在，但没有数据块和入口脚本
  const bare = documentHTML({ head: "", html: "<main></main>", state: null, assets })
  expect(bare).toContain('<link rel="stylesheet" href="/assets/entry-a1.css">')
  expect(bare).toContain('src="/theme.js"')
  expect(bare).not.toContain('type="module"')
  expect(bare).not.toContain('id="ow-state"')
  expect(bare).not.toContain("c-nojs")
})

test("avatar initials skip symbols and emoji", () => {
  expect(initial("夜蛾")).toBe("夜")
  expect(initial("· 小翼")).toBe("小")
  expect(initial("wyrm")).toBe("W")
  expect(initial("🌫️")).toBe("?")
  expect(initial("")).toBe("?")
})

test("every icon this round has its paths", () => {
  for (const name of [
    "search",
    "menu",
    "close",
    "chevron-down",
    "sun",
    "moon",
    "monitor",
    "info",
    "check-circle",
    "x-circle",
    "alert",
  ]) {
    expect(ICONS[name]?.length, name).toBeGreaterThan(0)
    for (const path of ICONS[name] ?? []) expect(path).toMatch(/^M/)
  }
})
