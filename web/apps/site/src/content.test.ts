import { expect, test } from "vitest"
import { handle } from "../server"
import { createSiteRouter } from "./router"

// F4 content pages through the real SSR handler, with Go stubbed per path.
type Answer = { status?: number; body: unknown }
async function page(url: string, answers: Record<string, Answer>, user: unknown = null) {
  const asked: string[] = []
  const result = await handle({ method: "GET", url, headers: { get: () => null } }, {
    apiBase: "http://api.test",
    fetch: async (input) => {
      const path = new URL(String(input)).pathname
      asked.push(path)
      if (path === "/api/session") return Response.json({ user })
      const answer = answers[path]
      if (!answer) return Response.json({ error: { code: "not_found", message: "页面不存在" } }, { status: 404 })
      return Response.json(answer.body, { status: answer.status ?? 200 })
    },
  })
  return { ...result, asked }
}

const terms = {
  slug: "terms",
  title: "用户协议",
  body_html: "<p>生效日期：2026 年 10 月 5 日</p>",
  seo_title: "",
  search_description: "",
  // 20:15 in Shanghai on the 10th; 12:15 UTC.
  last_published_at: "2026-10-10T12:15:00Z",
}

test("an about page: three tabs with the current one marked, title, last update in Shanghai time, body", async () => {
  const { status, body } = await page("/terms/", { "/api/page/terms": { body: terms } })
  expect(status).toBe(200)
  expect(body).toContain("<title>用户协议 · SJTU-OW</title>")
  expect(body).toMatch(/<nav class="c-tabs" aria-label="关于本站">/)
  expect(body).toContain('<a href="/terms/" aria-current="page">用户协议</a>')
  expect(body).toContain('<a href="/about/">关于我们</a>')
  expect(body).toContain('<a href="/privacy/">隐私政策</a>')
  expect(body).toContain('<h1 class="c-article__title">用户协议</h1>')
  expect(body).toContain('最后更新 <time class="font-numeric" datetime="2026-10-10T20:15:00+08:00">2026.10.10</time>')
  expect(body).toContain('<div class="c-prose"><p>生效日期：2026 年 10 月 5 日</p></div>')
})

test("the SEO title and description win when the editor set them; no update line without a date", async () => {
  const { body } = await page("/about/", {
    "/api/page/about": { body: { ...terms, slug: "about", title: "关于我们", seo_title: "关于 SJTU-OW", search_description: "社团介绍", last_published_at: null } },
  })
  expect(body).toContain("<title>关于 SJTU-OW · SJTU-OW</title>")
  expect(body).toContain('<meta name="description" content="社团介绍">')
  expect(body).toContain('<h1 class="c-article__title">关于我们</h1>')
  expect(body).not.toContain("最后更新")
})

test("any other page under the home page is served at /<slug>/, and Go's 404 stays a 404", async () => {
  const found = await page("/join-us/", { "/api/page/join-us": { body: { ...terms, slug: "join-us", title: "加入我们" } } })
  expect(found.status).toBe(200)
  expect(found.body).toContain('<h1 class="c-article__title">加入我们</h1>')
  // None of the three tabs is current on another page.
  expect(found.body).not.toContain('aria-current="page">关于我们')
  const missing = await page("/no-such-page/", {})
  expect(missing.status).toBe(404)
  expect(missing.asked).toContain("/api/page/no-such-page")
})

test("a Unicode slug reaches Go encoded once", async () => {
  const { status, asked } = await page("/%E5%8A%A0%E5%85%A5/", { "/api/page/%E5%8A%A0%E5%85%A5": { body: { ...terms, title: "加入" } } })
  expect(asked).toContain("/api/page/%E5%8A%A0%E5%85%A5")
  expect(status).toBe(200)
})

test("addresses Wagtail never served as pages stay 404 without asking Go", async () => {
  for (const url of ["/wp-login.php/", "/a/b/", "/.env/"]) {
    const { status, asked } = await page(url, {})
    expect(status, url).toBe(404)
    expect(asked.filter((p) => p.startsWith("/api/page/")), url).toEqual([])
  }
})

test("fixed routes outrank the page slug", async () => {
  const router = createSiteRouter(true)
  for (const url of ["/news/", "/teams/", "/members/", "/search/", "/me/", "/admin/", "/_styleguide/"]) {
    expect(router.resolve(url).matched[0]?.path, url).not.toContain(":slug")
  }
  expect(router.resolve("/join-us/").matched[0]?.path).toContain(":slug")
})

const member = { id: 7, nickname: "成员", email: "m@example.com", admin: false, superuser: false, caps: [] as string[], email_verified: true, is_sjtu: true }

test("submit: a visitor is told to log in and sent back here afterwards", async () => {
  const { status, body } = await page("/submit/", {})
  expect(status).toBe(200)
  expect(body).toContain("<title>投稿 · SJTU-OW</title>")
  expect(body).toContain("<li>未登录</li>")
  expect(body).toContain('<a href="/accounts/login/?next=%2Fsubmit%2F" class="c-btn c-btn--primary">去登录</a>')
  expect(body).toContain('<nav class="c-crumbs" aria-label="位置"><a href="/">首页</a>')
})

test("submit: a contributor goes straight to the editor; others see every reason", async () => {
  const contributor = await page("/submit/", {}, { ...member, admin: true, caps: ["admin.enter", "articles.publish_own"] })
  expect([contributor.status, contributor.headers.location]).toEqual([302, "/admin/articles/new/"])
  // load() reads the same session the page is painted with: one call, not two.
  expect(contributor.asked.filter((p) => p === "/api/session")).toHaveLength(1)
  const plain = await page("/submit/", {}, member)
  expect(plain.body).toContain("<li>没有投稿权限</li>")
  expect(plain.body).not.toContain("邮箱未验证")
  expect(plain.body).toContain('<a href="/me/" class="c-btn c-btn--secondary">返回个人中心</a>')
  const unverified = await page("/submit/", {}, { ...member, email_verified: false })
  expect(unverified.body).toContain("<li>邮箱未验证</li>")
  expect(unverified.body).not.toContain("没有投稿权限")
  const banned = await page("/submit/", {}, { ...member, email_verified: false, can_submit_article: false })
  expect(banned.body).toContain("<li>邮箱未验证</li><li>没有投稿权限</li>")
})

const results = {
  query: "截图",
  groups: [
    { key: "articles", label: "文章", hits: [{ title: "截图攻略", url: "/news/screens-guide/", excerpt: "截图攻略 新人入门。", meta: "攻略" }], truncated: true },
    { key: "events", label: "赛事与内战", hits: [], truncated: false },
    { key: "teams", label: "战队", hits: [{ title: "截图战队", url: "/teams/1/", excerpt: "", meta: "招募中" }], truncated: false },
    { key: "members", label: "成员", hits: [], truncated: false },
  ],
}

test("search with nothing to look for explains itself and does not call Go", async () => {
  const { status, body, asked } = await page("/search/?q=%20%20", {})
  expect(status).toBe(200)
  expect(body).toContain("<title>站内搜索 · SJTU-OW</title>")
  expect(body).toContain("只搜公开内容：")
  expect(body).toContain('<input id="search-q" type="search" name="q" value="" maxlength="50"')
  expect(asked).not.toContain("/api/search")
})

test("search results: count, groups in order with the old ids, excerpt, tag, the 20-hit note", async () => {
  const { body } = await page("/search/?q=%E6%88%AA%E5%9B%BE", { "/api/search": { body: results } })
  expect(body).toContain("<title>搜索：截图 · 站内搜索 · SJTU-OW</title>")
  expect(body).toContain('<meta name="description" content="搜索文章、赛事与内战、战队和成员。">')
  expect(body).toContain("「截图」共 2 条结果")
  expect(body).toContain('<section aria-labelledby="search-1">')
  expect(body).toContain('<section aria-labelledby="search-3">')
  expect(body).not.toContain("search-2")
  expect(body).toContain('<h3 class="c-row__title"><a href="/news/screens-guide/" class="c-stretch">截图攻略</a></h3><p class="c-row__text">截图攻略 新人入门。</p>')
  expect(body).toContain('<span class="c-tag">招募中</span>')
  expect(body.match(/只显示前 20 条/g)).toHaveLength(1)
  expect(body.indexOf(">文章</h2>")).toBeLessThan(body.indexOf(">战队</h2>"))
})

test("search: no hits is the empty state; Go's limit is the 429 page; the query is cut to 50", async () => {
  const empty = await page("/search/?q=zz", { "/api/search": { body: { query: "zz", groups: results.groups.map((g) => ({ ...g, hits: [], truncated: false })) } } })
  expect(empty.body).toContain('<p class="c-empty__title">没有找到</p><p class="c-empty__text">没有找到和「zz」有关的内容。换个词试试。</p>')
  const limited = await page("/search/?q=zz", { "/api/search": { status: 429, body: { error: { code: "rate_limited", message: "太快了" } } } })
  expect(limited.status).toBe(429)
  const long = "长".repeat(60)
  const cut = await page("/search/?q=" + encodeURIComponent(long), { "/api/search": { body: { query: "", groups: [] } } })
  expect(cut.body).toContain(`<title>搜索：${"长".repeat(50)} · 站内搜索 · SJTU-OW</title>`)
})
