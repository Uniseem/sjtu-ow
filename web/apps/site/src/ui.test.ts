import { createSSRApp, createStaticVNode, h, type Component } from "vue"
import { renderToString } from "vue/server-renderer"
import { expect, test } from "vitest"
import { readFileSync } from "node:fs"
import { ICONS } from "./icons"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import CPager from "@sjtu-ow/ui/CPager.vue"
import CRank from "@sjtu-ow/ui/CRank.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import CPlay from "@sjtu-ow/ui/CPlay.vue"
import CProfileGaps from "@sjtu-ow/ui/CProfileGaps.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CRegStatus from "@sjtu-ow/ui/CRegStatus.vue"
import CSeats from "@sjtu-ow/ui/CSeats.vue"

import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import PostCard from "@sjtu-ow/ui/PostCard.vue"
import TeamTile from "@sjtu-ow/ui/TeamTile.vue"
import CTournamentCard from "@sjtu-ow/ui/CTournamentCard.vue"
import CScrimRow from "@sjtu-ow/ui/CScrimRow.vue"
import CStartsAt from "@sjtu-ow/ui/CStartsAt.vue"
import CTeamLogo from "@sjtu-ow/ui/CTeamLogo.vue"
import AuthWhy from "@sjtu-ow/ui/AuthWhy.vue"
import AuthBack from "@sjtu-ow/ui/AuthBack.vue"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import MeLayout from "@sjtu-ow/ui/MeLayout.vue"
import CComments from "@sjtu-ow/ui/CComments.vue"
import CCommentItem from "@sjtu-ow/ui/CCommentItem.vue"
import CCommentReply from "@sjtu-ow/ui/CCommentReply.vue"
import CCommentComposer from "@sjtu-ow/ui/CCommentComposer.vue"

const components: Record<string, Component> = { CAvatar, CEmpty, CField, CPager, CRank, CRoleIcon, CPlay, CProfileGaps, CStatus, CRegStatus, CSeats, CPagehead, PostCard, TeamTile, CTournamentCard, CScrimRow, CStartsAt, CTeamLogo, AuthWhy, AuthBack, AuthLayout, MeLayout, CComments, CCommentItem, CCommentReply, CCommentComposer }
interface Fixture { component: string; props: Record<string, unknown>; html: string; control?: string; help?: string }
const fixtures: Fixture[] = [
  ...JSON.parse(readFileSync(new URL("./testdata/legacy-ui.json", import.meta.url), "utf8")),
  ...JSON.parse(readFileSync(new URL("./testdata/legacy-cards.json", import.meta.url), "utf8")),
  ...JSON.parse(readFileSync(new URL("./testdata/legacy-comments.json", import.meta.url), "utf8")),
]

// Attribute order, self-closing syntax, boolean attribute notation, fragment
// comments and whitespace are serializer details. Keep every tag, attribute,
// class, value and visible character otherwise (including ARIA and links).
function canonical(html: string): string {
  return html.replace(/<!--.*?-->/gs, "").replace(/<path([^>]*?)\s*\/>/g, "<path$1></path>").replace(/&amp;/g, "&").replace(/&#x27;|&#39;/g, "'")
    .replace(/<([\w-]+)((?:[^>"']|"[^"]*"|'[^']*')*)>/g, (_, tag, body: string) => {
      const attrs = [...body.replace(/\/$/, "").matchAll(/([\w:-]+)(?:="([^"]*)"|='([^']*)')?/g)]
        .map((m) => [m[1], m[2] ?? m[3] ?? ""])
        .map(([name, value]) => `${name.toLowerCase()}=${value.replace(/\s+/g, " ").trim()}`).sort()
      return `<${tag}${attrs.length ? " " + attrs.join(" ") : ""}>`
    }).replace(/\s+/g, " ").replace(/> </g, "><").replace(/>\s+/g, ">").replace(/\s+</g, "<").trim()
}
async function paint(component: Component, props: Record<string, unknown>, fixture?: Fixture): Promise<string> {
  const slots = fixture?.control ? { default: () => createStaticVNode(fixture.control!, 1), ...(fixture.help ? { help: () => fixture.help } : {}) } : undefined
  return renderToString(createSSRApp({ render: () => h(component, props, slots) }))
}
for (const [i, fixture] of fixtures.entries()) {
  test(`old template parity ${i}: ${fixture.component} ${JSON.stringify(fixture.props)}`, async () => {
    expect(canonical(await paint(components[fixture.component], fixture.props, fixture))).toBe(canonical(fixture.html))
  })
}
test("private or stopped avatars fall back; large and small avatars use their allowed rendition", async () => {
  const own = await paint(CAvatar, { person: { id: 7, nickname: "小", avatar_image_id: 99 }, size: "lg" })
  expect(own).toContain('/media/r/99/fill-176x176.webp')
  const pool = await paint(CAvatar, { person: { id: 7, nickname: "小", default_avatar_image_id: 88 }, size: "xs" })
  expect(pool).toContain('/media/r/88/fill-88x88.webp')
  const stopped = await paint(CAvatar, { person: { id: 7, nickname: "小", is_active: false, avatar_image_id: 99, default_avatar_image_id: 88 } })
  expect(stopped).not.toContain('<img')
  expect(stopped.replace(/<!--.*?-->/g, '')).toContain('>小</span>')
})
test("fields show only the first error and page numbers replace an existing query value", async () => {
  const html = await paint(CField, { label: "队名", errors: ["第一个错", "第二个错"] })
  expect(html).toContain('role="alert"')
  expect(html).toContain('第一个错')
  expect(html).not.toContain('第二个错')
  const pager = await paint(CPager, { page: 2, pages: 3, extraQuery: "q=x%26y&page=90" })
  expect(pager).not.toContain('page=90')
  expect(pager).toContain('q=x%26y&amp;page=3')
})
test("unknown image accounts and private ranks are never invented by display components", async () => {
  const html = await paint(CPlay, { profile: { roles: [], main_rank: null } })
  expect(html).not.toContain('c-rank')
  expect(html).not.toContain('c-play')
})

test("comment tools follow the viewer: like state, own edits, moderator pins and hides", async () => {
  const base = { id: 3, user_id: 2, author_name: "小满", content: "写得好", is_pinned: false, is_hidden: false, is_deleted: false, like_count: 1, liked_by_me: true, created_at: "2026-10-10T13:00:00Z", updated_at: "2026-10-10T13:00:00Z" }
  const visitor = await paint(CCommentItem, { item: base, interactive: false, canPost: false, canModerate: false })
  expect(visitor).toContain('>赞 <span class="font-numeric" data-like-count>1</span>')
  expect(visitor).not.toContain("<button")
  const own = await paint(CCommentItem, { item: { ...base, user_id: 7 }, interactive: true, canPost: true, canModerate: false, viewerId: 7 })
  expect(own).toContain('aria-pressed="true"')
  expect(own).toContain("已赞")
  expect(own).toContain(">编辑</summary>")
  expect(own).toContain("保存修改")
  expect(own).toContain("删除")
  expect(own).toContain("c-act--danger")
  expect(own).not.toContain("置顶</button>")
  const mod = await paint(CCommentItem, { item: { ...base }, interactive: true, canPost: true, canModerate: true, viewerId: 9 })
  expect(mod).toContain("置顶")
  // The hide button's eye-off glyph; the confirm text lives in the click
  // handler and never reaches the SSR string.
  expect(mod).toContain(ICONS["eye-off"][0])
  expect(mod).not.toContain("保存修改")
  const hidden = await paint(CCommentItem, { item: { ...base, is_hidden: true }, interactive: true, canPost: true, canModerate: true, viewerId: 9 })
  expect(hidden).toContain('<span class="c-status c-status--off">已隐藏</span>')
  expect(hidden).toContain("恢复")
  const tombstone = await paint(CCommentItem, { item: { ...base, is_deleted: true, replies: [{ ...base, id: 9 }] } })
  expect(tombstone).toContain("评论已删除。")
  expect(tombstone).toContain("<summary>1 条回复")
})

test("the section shows the composer only where the old one would render", async () => {
  const thread = { total: 0, page: 1, page_size: 20, comments: [] }
  const visitor = await paint(CComments, {
    commentsEnabled: true, thread, sort: "new", interactive: false, canPost: false,
    postProblems: [], canModerate: false, pageUrl: "/news/w/", loginUrl: "/accounts/login/?next=/news/w/",
  })
  expect(visitor).toContain("<h2 id=\"comments\">评论</h2>")
  expect(visitor).toContain("登录后评论")
  expect(visitor).not.toContain("<textarea")
  const member = await paint(CComments, {
    commentsEnabled: true, thread, sort: "new", interactive: true, canPost: true,
    postProblems: [], canModerate: false, viewerId: 7, pageUrl: "/news/w/", loginUrl: "/accounts/login/?next=/news/w/",
  })
  expect(member).toContain("说点什么…（最多 500 字）")
  expect(member).toContain(">发表评论</button>")
  const banned = await paint(CComments, {
    commentsEnabled: true, thread, sort: "new", interactive: true, canPost: false,
    postProblems: ["你暂时无法使用此功能，如有疑问请联系管理员"], canModerate: false, viewerId: 7,
    pageUrl: "/news/w/", loginUrl: "/accounts/login/?next=/news/w/",
  })
  expect(banned).toContain("你暂时无法使用此功能，如有疑问请联系管理员")
  expect(banned).not.toContain("<textarea")
  const closed = await paint(CComments, {
    commentsEnabled: false, thread: { ...thread, total: 2 }, sort: "new", interactive: true, canPost: false,
    postProblems: [], canModerate: false, viewerId: 7, pageUrl: "/news/w/", loginUrl: "/accounts/login/?next=/news/w/",
  })
  expect(closed).toContain("这篇文章关闭了评论。")
  // 25 top-level comments at 20 a page leave a load-more to page 2.
  const more = await paint(CComments, {
    commentsEnabled: true, thread: { total: 25, page: 1, page_size: 20, comments: [] }, sort: "new",
    interactive: false, canPost: false, postProblems: [], canModerate: false,
    pageUrl: "/news/w/", loginUrl: "/accounts/login/?next=/news/w/",
  })
  expect(more).toContain('href="/news/w/?comments=2&amp;sort=new#comments"')
  expect(more).toContain("加载更多")
  const last = await paint(CComments, {
    commentsEnabled: true, thread: { total: 20, page: 1, page_size: 20, comments: [] }, sort: "new",
    interactive: false, canPost: false, postProblems: [], canModerate: false,
    pageUrl: "/news/w/", loginUrl: "/accounts/login/?next=/news/w/",
  })
  expect(last).not.toContain("加载更多")
})
