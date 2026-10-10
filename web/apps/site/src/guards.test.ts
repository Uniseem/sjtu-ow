import { globSync, readFileSync } from "node:fs"
import { relative, resolve } from "node:path"
import { expect, test } from "vitest"

// Source guards (frontend-migration 9.1): what 260 got wrong, stopped at the
// source. Each rule lists the offending files; a file that is still waiting
// to be rewritten is in PENDING_REWRITE instead. That list only shrinks: a
// listed file that breaks no rule any more must come off it (the last test).

const SRC = resolve(import.meta.dirname)
const REPO = resolve(SRC, "../../../..")

// 260's pages and 253's back office, to be redone page family by page family
// (frontend-migration 3, 11). Do not add to this list.
const PENDING_REWRITE = new Set([
  "pages/ArticleDetail.vue",
  "pages/Contacts.vue",
  "pages/GameAccounts.vue",
  "pages/Home.vue",
  "pages/MemberDetail.vue",
  "pages/Members.vue",
  "pages/News.vue",
  "pages/Profile.vue",
  "pages/ScrimDetail.vue",
  "pages/Scrims.vue",
  "pages/TeamApply.vue",
  "pages/TeamDetail.vue",
  "pages/Teams.vue",
  "pages/TournamentDetail.vue",
  "pages/Tournaments.vue",
  "admin/AdminLayout.vue",
  "pages/admin/AdminActivity.vue",
  "pages/admin/AdminArticleEdit.vue",
  "pages/admin/AdminArticles.vue",
  "pages/admin/AdminAuditLog.vue",
  "pages/admin/AdminAvatars.vue",
  "pages/admin/AdminCategories.vue",
  "pages/admin/AdminComments.vue",
  "pages/admin/AdminHome.vue",
  "pages/admin/AdminHomePins.vue",
  "pages/admin/AdminImages.vue",
  "pages/admin/AdminLetters.vue",
  "pages/admin/AdminManual.vue",
  "pages/admin/AdminMemberGroups.vue",
  "pages/admin/AdminModeration.vue",
  "pages/admin/AdminRoles.vue",
  "pages/admin/AdminScrimBoard.vue",
  "pages/admin/AdminScrimEdit.vue",
  "pages/admin/AdminScrims.vue",
  "pages/admin/AdminSettings.vue",
  "pages/admin/AdminTeams.vue",
  "pages/admin/AdminTournamentBoard.vue",
  "pages/admin/AdminTournamentEdit.vue",
  "pages/admin/AdminTournamentReview.vue",
  "pages/admin/AdminTournaments.vue",
  "pages/admin/AdminUserDetail.vue",
  "pages/admin/AdminUsers.vue",
])

const siteFiles = globSync("**/*.{vue,ts}", { cwd: SRC }).filter((f) => !f.endsWith(".test.ts"))
const files = [...siteFiles, ...globSync("web/packages/{ui,shared}/src/**/*.{vue,ts}", { cwd: REPO }).filter((f) => !f.endsWith(".test.ts")).map((f) => relative(SRC, resolve(REPO, f)))]
const vue = files.filter((f) => f.endsWith(".vue"))
const read = (f: string) => readFileSync(resolve(SRC, f), "utf8")
const templateOf = (source: string) => {
  const start = source.indexOf("<template>")
  const end = source.lastIndexOf("</template>")
  return start >= 0 && end > start ? source.slice(start, end) : ""
}

// Every rule: name → files breaking it.
const rules: Record<string, (f: string) => boolean> = {}

// Tailwind's palette is switched off (input.css `--color-*: initial`, only
// white and black kept): these classes do not exist (AGENTS「前台组件是自己写的」).
const PALETTE =
  /\b(?:bg|text|border|ring|from|to|via|divide|outline|fill|stroke|placeholder|decoration|shadow|accent|caret)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d/
rules["palette class"] = (f) => PALETTE.test(read(f))

// c-/l-/b- classes must be in input.css or used by the old templates and
// their image helper (hook classes without styles are fine in the old site).
const known = new Set<string>()
const CLASS = /\b[cbl]-[a-z0-9]+(?:-[a-z0-9]+)*(?:__[a-z0-9]+(?:-[a-z0-9]+)*)?(?:--[a-z0-9]+(?:-[a-z0-9]+)*)?/g
for (const m of readFileSync(resolve(REPO, "web/packages/styles/input.css"), "utf8").matchAll(/\.([cbl]-[a-z0-9_-]+)/g)) {
  known.add(m[1])
}
for (const t of globSync("{templates,*/templates}/**/*.html", { cwd: REPO })) {
  for (const m of readFileSync(resolve(REPO, t), "utf8").matchAll(CLASS)) known.add(m[0])
}
for (const m of readFileSync(resolve(REPO, "core/templatetags/ow.py"), "utf8").matchAll(CLASS)) {
  known.add(m[0])
}
function unknownClasses(source: string): string[] {
  const out: string[] = []
  for (const m of templateOf(source).matchAll(CLASS)) {
    const after = templateOf(source).slice(m.index! + m[0].length, m.index! + m[0].length + 3)
    // c-hue-${n}: a prefix, fine when some class starts with it
    if (after.startsWith("-${") || after.startsWith("-$")) {
      if (![...known].some((k) => k.startsWith(m[0] + "-"))) out.push(m[0] + "-…")
      continue
    }
    if (!known.has(m[0])) out.push(m[0])
  }
  return out
}
rules["unknown component class"] = (f) => f.endsWith(".vue") && unknownClasses(read(f)).length > 0

// Pages talk to Go through the generated functions only (A3).
rules["raw /api/ call"] = (f) => f.endsWith(".vue") && /["'`}]\/api\//.test(read(f))

// No style attributes: the policy blocks them (12-architecture 6.3, I8).
rules["style binding"] = (f) => f.endsWith(".vue") && /(?:\s:style=|\sv-bind:style=|\sstyle=")/.test(templateOf(read(f)))

// v-html only for HTML Go rendered and sanitised (I8): each page that shows
// a body_html names itself here (the article page joins when it is
// rewritten). No generic "render this HTML" component: that would let any
// page pass any string through.
const V_HTML_ALLOWED = new Set<string>(["pages/StandardPage.vue"])
rules["v-html"] = (f) => f.endsWith(".vue") && !V_HTML_ALLOWED.has(f) && /\sv-html=/.test(read(f))

// Pages and components take their types from the generated API (A4). The
// plumbing (router.ts PageData) still carries 260's loose shape until the
// last of those pages is rewritten.
rules["any type"] = (f) => f.endsWith(".vue") && /(?::\s*any\b|<any>|\bas any\b|any\[\])/.test(read(f))

function offenders(rule: (f: string) => boolean): string[] {
  return files.filter((f) => !PENDING_REWRITE.has(f) && rule(f))
}

for (const [name, rule] of Object.entries(rules)) {
  test(`no ${name} outside the files waiting to be rewritten`, () => {
    expect(offenders(rule)).toEqual([])
  })
}

test("the guards see what they should (each rule catches a known case)", () => {
  expect(PALETTE.test('class="bg-stone-900"')).toBe(true)
  expect(PALETTE.test('class="text-white bg-surface"')).toBe(false)
  expect(unknownClasses('<template><p class="c-notice c-notice--err"></p></template>')).toEqual(["c-notice--err"])
  expect(unknownClasses('<template><p class="c-notice c-notice--error c-crumbs__sep"></p></template>')).toEqual([])
  expect(unknownClasses('<template><span :class="`c-hue-${n}`"></span></template>')).toEqual([])
  expect(unknownClasses('<template><img class="c-pagehead__img c-scene c-scene--light"></template>')).toEqual([])
  expect(rules["raw /api/ call"]("pages/admin/AdminLetters.vue")).toBe(true)
  expect(rules["any type"]("pages/TeamDetail.vue")).toBe(true)
})

test("routes do not grow new title-only placeholders", () => {
  const routes = readFileSync(resolve(SRC, "routes.ts"), "utf8")
  const placeholders = [...routes.matchAll(/^ {2}page\(([^,]+),/gm)].map((m) => m[1])
  // The 34 of 260 (frontend-migration S7), 18 left after 270. Each page
  // family's round replaces its entries with real pages and lowers this
  // number; nothing new goes in.
  expect(placeholders.length).toBeLessThanOrEqual(18)
})

test("every file on the pending list still needs rewriting (the list only shrinks)", () => {
  const clean = [...PENDING_REWRITE].filter((f) => !Object.values(rules).some((rule) => rule(f)))
  expect(clean, "these break no rule now: take them off PENDING_REWRITE").toEqual([])
  expect([...PENDING_REWRITE].filter((f) => !files.includes(f)), "listed but gone").toEqual([])
})

test("vue files are counted", () => {
  expect(vue.length).toBeGreaterThan(40)
  expect(relative(REPO, SRC)).toBe("web/apps/site/src")
})
