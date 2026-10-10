import { createSSRApp, createStaticVNode, h, type Component } from "vue"
import { renderToString } from "vue/server-renderer"
import { expect, test } from "vitest"
import { readFileSync } from "node:fs"
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

const components: Record<string, Component> = { CAvatar, CEmpty, CField, CPager, CRank, CRoleIcon, CPlay, CProfileGaps, CStatus, CRegStatus, CSeats }
interface Fixture { component: string; props: Record<string, unknown>; html: string; control?: string; help?: string }
const fixtures: Fixture[] = JSON.parse(readFileSync(new URL("./testdata/legacy-ui.json", import.meta.url), "utf8"))

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
