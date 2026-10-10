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
  // Vue's SSR inserts fragment comments around v-for/v-if text (233): tests
  // that match prose read `plain`, comments stripped.
  return { ...result, asked, plain: String(result.body).replace(/<!--.*?-->/g, "") }
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

// --- 275: the article page (with comments), the news list, the home page ----

const article = {
  id: 7,
  slug: "screens-guide",
  title: "截图指南",
  category_name: "攻略",
  category_slug: "guides",
  summary: "新人入门的截图方法。",
  body_html: "<p>先打开游戏。</p><h2 id='h-1'>第一步</h2><p>按截图键。</p>",
  char_count: 120,
  reading_time: 2,
  author_name: "小满",
  comments_enabled: true,
  first_published_at: "2026-10-10T12:00:00Z",
  headings: [{ level: 2, text: "第一步", id: "h-1" }],
}

const commentRow = (over: Record<string, unknown> = {}) => ({
  id: 3, article_id: 7, user_id: 2, author_name: "小满", content: "写得好", is_pinned: false, is_hidden: false,
  is_deleted: false, like_count: 1, liked_by_me: false, version: 1, created_at: "2026-10-10T13:00:00Z", updated_at: "2026-10-10T13:00:00Z",
  ...over,
})
const thread = (comments: unknown[], total = comments.length) => ({ total, page: 1, page_size: 20, comments })
const memberSession = { ...member, id: 5, nickname: "夜蛾" }

test("an article: cover head with the category link, facts, prose; a visitor reads only", async () => {
  const { status, plain: body } = await page("/news/screens-guide/", { "/api/page/news/screens-guide": { body: article } })
  expect(status).toBe(200)
  expect(body).toContain("<title>截图指南 · SJTU-OW</title>")
  expect(body).toContain('<nav class="c-crumbs" aria-label="位置"><a href="/">首页</a>')
  expect(body).toContain('<a href="/news/?category=guides">攻略</a>')
  expect(body).toContain('<a href="/news/?category=guides" class="c-tag c-tag--accent">攻略</a>')
  expect(body).toContain("<h1 class=\"c-cover__title\">截图指南</h1>")
  expect(body).toContain("<p class=\"c-cover__summary\">新人入门的截图方法。</p>")
  expect(body).toContain('<span class="c-article__author">小满</span>')
  expect(body).toContain("约 <span class=\"font-numeric\">2</span> 分钟")
  expect(body).toContain("<span class=\"font-numeric\">120</span> 字")
  expect(body).toContain('>0</span> 条评论')
  expect(body).toContain('<div class="c-prose"><p>先打开游戏。</p>')
  // One heading is below the three the contents needs (design-details 6.5).
  expect(body).not.toContain("c-toc")
  // Read-only section: the login link, no forms, no like buttons.
  expect(body).toContain('<a href="/accounts/login/?next=/news/screens-guide/"')
  expect(body).toContain("还没有评论。")
  expect(body).not.toContain("发表评论")
  expect(body).not.toContain("<textarea")
})

test("the SEO title and description, and the update line only past a day", async () => {
  const { plain: body } = await page("/news/screens-guide/", {
    "/api/page/news/screens-guide": { body: { ...article, seo_title: "截图教学", search_description: "怎么截图", last_published_at: "2026-10-13T12:00:00Z" } },
  })
  expect(body).toContain("<title>截图教学 · SJTU-OW</title>")
  expect(body).toContain('<meta name="description" content="怎么截图">')
  expect(body).toContain("更新于 <time class=\"font-numeric\"")
  const fresh = await page("/news/screens-guide/", {
    "/api/page/news/screens-guide": { body: { ...article, last_published_at: "2026-10-10T15:00:00Z" } },
  })
  expect(fresh.plain).not.toContain("更新于")
})

test("a signed-in member gets the composer; the sort row and comment count follow the thread", async () => {
  const { plain: body, asked } = await page(
    "/news/screens-guide/",
    {
      "/api/page/news/screens-guide": { body: article },
      "/api/articles/7/comments": { body: thread([commentRow({ is_pinned: true }), commentRow({ id: 4, user_id: 9, author_name: "阿白", content: "赞", reply_count: 0 })], 2) },
    },
    memberSession,
  )
  expect(body).toContain("<title>截图指南 · SJTU-OW</title>")
  expect(body).toContain("2 条评论")
  expect(body).toContain('<nav class="c-comments__sort" aria-label="评论排序">')
  expect(body).toContain('<a href="/news/screens-guide/?sort=new#comments" aria-current="true">最新</a>')
  expect(body).toContain('<a href="/news/screens-guide/?sort=top#comments">最热</a>')
  expect(body).toContain('<textarea name="body" rows="3" maxlength="500" required class="c-input" placeholder="说点什么…（最多 500 字）">')
  expect(body).toContain("发出即显示；违规内容会被内容编辑隐藏。")
  expect(body).toContain(">发表评论</button>")
  expect(body).toContain('id="comment-3" class="c-comment is-pinned"')
  expect(body).toContain('<span class="c-tag c-tag--accent">置顶</span>')
  expect(body).toContain("写得好")
  // One call to the thread, the same session as the paint (A5).
  expect(asked.filter((p) => p === "/api/articles/7/comments")).toHaveLength(1)
  // The pinned comment's reply fold, per the old item template.
  expect(body).not.toContain("条回复")
})

test("the contents arrive at three headings, in a fold and a side nav", async () => {
  const headings = [
    { level: 2, text: "第一步", id: "h-1" },
    { level: 3, text: "第二步", id: "h-2" },
    { level: 2, text: "第三步", id: "h-3" },
  ]
  const { plain: body } = await page("/news/screens-guide/", { "/api/page/news/screens-guide": { body: { ...article, headings } } })
  expect(body).toContain('<details class="c-toc c-toc--fold">')
  expect(body).toContain('<nav class="c-toc c-toc--side" aria-label="目录">')
  expect(body).toContain('<li class="c-toc__item c-toc__item--h3"><a href="#h-2">第二步</a></li>')
})

test("a replies fold shows the count and the @ reply", async () => {
  const { plain: body } = await page("/news/screens-guide/", {
    "/api/page/news/screens-guide": { body: article },
    "/api/articles/7/comments": { body: thread([commentRow({
      id: 3,
      replies: [commentRow({ id: 9, parent_id: 3, author_name: "阿白", reply_to_user_name: "小满", content: "同问", like_count: 0 })],
      reply_count: 1,
    })], 1) },
  })
  expect(body).toContain("<summary>1 条回复")
  expect(body).toContain('<span class="c-comment__at">@小满</span> 同问')
  expect(body).toContain('class="c-comment c-comment--reply"')
})

test("Go's 404 for an unknown, unpublished or forbidden article stays a 404", async () => {
  const { status } = await page("/news/no-such/", {})
  expect(status).toBe(404)
})

test("the news list: tabs with the current one marked, the intro, cards, pager", async () => {
  const data = {
    total: 14, page: 2, page_size: 12,
    categories: [{ slug: "guides", name: "攻略" }, { slug: "notice", name: "公告" }],
    intro_html: "<p>社区的文章栏目。</p>",
    items: [{ id: 1, slug: "screens-guide", title: "截图指南", category_name: "攻略", summary: "新人入门的截图方法。", reading_time: 2, author_name: "小满", first_published_at: "2026-10-10T12:00:00Z", cover_image_id: 9, pinned: false }],
  }
  const { status, plain: body } = await page("/news/?category=guides&page=2", { "/api/page/news": { body: data } })
  expect(status).toBe(200)
  expect(body).toContain("<title>资讯 · SJTU-OW</title>")
  // The column banner waits for Go (BE-5): the scene placeholders paint, as
  // the old pagehead_picture.html does without one.
  expect(body).toContain('src="/static/img/placeholders/section-news-light.svg"')
  expect(body).toContain('<div class="c-pagehead__lede"><p>社区的文章栏目。</p></div>')
  expect(body).toContain('<a href="/news/" aria-current="undefined">全部</a>'.replace(" aria-current=\"undefined\"", ""))
  expect(body).toContain('<a href="/news/?category=guides" aria-current="page">攻略</a>')
  expect(body).toContain('<a href="/news/?category=notice">公告</a>')
  expect(body).toContain('<a href="/submit/" class="c-btn c-btn--secondary">')
  expect(body).toContain("截图指南")
  expect(body).toContain('href="?category=guides&amp;page=1" rel="prev"')
  expect(body).toContain("<strong>2</strong> / 2</span>")
})

test("the news list without the column data (BE-5 pending) still lists; an empty category is the empty state", async () => {
  const bare = await page("/news/", { "/api/page/news": { body: { total: 0, page: 1, page_size: 12, items: [] } } })
  expect(bare.body).toContain('aria-current="page">全部</a>')
  expect(bare.body).not.toContain("c-pagehead__lede")
  expect(bare.body).toContain('<p class="c-empty__title">暂无文章</p><p class="c-empty__text">这个分类还没有已发布的文章。</p>')
  expect(bare.body).not.toContain("c-pager")
})

const EMPTY_HOME = { stats: null, scrims: [], news: [], notices: [], teams: [] }

test("the home page: hero, figures, sections; a visitor has no agenda", async () => {
  const { status, plain: body } = await page("/", { "/api/page/home": { body: EMPTY_HOME } })
  expect(status).toBe(200)
  expect(body).toContain("<title>首页 · SJTU-OW</title>")
  expect(body).toContain('<h1 id="hero-title" class="c-hero__title"><span>上海交通大学</span><span>守望先锋社区</span></h1>')
  expect(body).toContain('<a href="/accounts/signup/" class="c-btn c-btn--primary">加入社区</a>')
  expect(body).toContain("注册成员</dt><dd>0</dd>")
  expect(body).toContain("全部内战")
  expect(body).not.toContain("我的安排")
})

test("the home page paints the real blocks and the member's agenda", async () => {
  const home = {
    stats: { member_count: 41, team_count: 6, scrims_held: 128, founded_on: "2020-10-25", age: { years: 6, days: 350 }, hero_image_id: null, qq_group_url: "https://qm.qq.com/x" },
    feature_tournament: { id: 3, title: "秋季赛", phase: "open", phase_label: "报名中", registration_mode: "team", takes_individuals: false, approved_teams: 4, registration_closes_at: "2026-10-15T12:00:00Z", facts: "整队报名 · 报名截止 2026.10.15 20:00 · 已通过 4 队" },
    scrims: [{ id: 8, title: "周五内战", starts_at: "2026-10-16T12:00:00Z", month: "10", day: "16", weekday: "周五", time: "20:00", count: 7, capacity: 10, signup_open: true }],
    news: [{ id: 1, slug: "screens-guide", title: "截图指南", category_name: "攻略", summary: "新人入门的截图方法。", reading_time: 2, author_name: "小满", first_published_at: "2026-10-10T12:00:00Z", pinned: true }],
    notices: [{ id: 2, slug: "site-open", title: "网站开放注册", month: "10", day: "11", published_at_raw: "2026-10-11T00:00:00Z" }],
    teams: [{ id: 4, name: "思源", logo_image_id: null, member_count: 6, is_recruiting: true, wanted_roles: "tank", created_at_month: "2026.09" }],
  }
  const agenda = { items: [{ kind: "内战", title: "周五内战", url: "/scrims/8/", when: "2026-10-16T12:00:00Z", note: "已报名" }] }
  const { plain: body } = await page("/", { "/api/page/home": { body: home }, "/api/me/agenda": { body: agenda } }, memberSession)
  expect(body).toContain("<dt>注册成员</dt><dd>41</dd>")
  expect(body).toContain("6 年 350 天")
  expect(body).toContain('<a href="https://qm.qq.com/x" class="c-btn c-btn--secondary" rel="noopener" data-quick="qq">加入 QQ 群</a>')
  expect(body).toContain('<span class="c-status c-status--live">报名中</span>')
  expect(body).toContain("整队报名 · 报名截止 2026.10.15 20:00 · 已通过 4 队")
  expect(body).toContain("已报 7 / 10")
  expect(body).toContain("我的安排")
  expect(body).toContain('<a href="/scrims/8/" class="c-stretch">周五内战</a>')
  expect(body).toContain("内战 · 周五 20:00 · 已报名")
  // News with its pinned tag, the notice row, the team tile.
  expect(body).toContain('<span class="c-tag c-tag--accent">置顶</span>')
  expect(body).toContain('<a href="/news/site-open/" class="c-stretch">网站开放注册</a>')
  expect(body).toContain('<a href="/teams/" class="c-btn c-btn--quiet">全部 6 支战队')
  expect(body).toContain("思源</a>")
  expect(body).toContain("缺 坦克")
})

test("a draft the author can open here paints an empty comment section when Go's thread 404s", async () => {
  // The article gate lets its author through; the comments gate does not.
  // The old thread() rendered an empty list for such a page, not an error.
  const { status, body } = await page("/news/screens-guide/", {
    "/api/page/news/screens-guide": { body: article },
    "/api/articles/7/comments": { status: 404, body: { error: { code: "not_found", message: "文章不存在" } } },
  })
  expect(status).toBe(200)
  expect(body.replace(/<!--.*?-->/g, "")).toContain("还没有评论。")
})

test("article pagination uses the Go page_size contract at the full-page boundary", async () => {
  for (const total of [20, 21, 40, 41]) {
    const { status, plain: body } = await page("/news/screens-guide/?sort=top", {
      "/api/page/news/screens-guide": { body: article },
      "/api/articles/7/comments": { body: { total, page: 1, page_size: 20, comments: [commentRow()] } },
    })
    expect(status).toBe(200)
    expect(body.includes("加载更多"), `total=${total}`).toBe(total > 20)
    if (total > 20) expect(body).toContain('href="/news/screens-guide/?comments=2&amp;sort=top#comments"')
  }
})
