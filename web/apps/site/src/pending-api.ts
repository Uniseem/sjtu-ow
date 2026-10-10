import { getApiSearch, type GetApiPageSlugOut, type Requester } from "@sjtu-ow/api"

// Fields the rewritten pages read that Go does not send yet. Each entry is a
// backend task in STATUS「交给后端」(the id in brackets). The page already
// renders them when present, as the old template did; when Go sends the field
// and apigen regenerates, delete the entry here and use the generated type.

/** [BE-1] GET /api/page/{slug}: content/models.py StandardPage + SeoPageMixin. */
export type SitePage = GetApiPageSlugOut & {
  seo_title?: string
  search_description?: string
  last_published_at?: string | null
}

/**
 * [BE-3] GET /api/session user: can_use(article_submit) on its own, before
 * the e-mail check (content/views.py submit_entry lists both reasons
 * separately). Until Go sends it, an unverified member is not told about a
 * ban on submitting as well.
 */
export type SubmitAbility = { can_submit_article?: boolean }

/**
 * [BE-2] GET /api/search?q= answers in search/services.py's groups: four
 * groups in this order (articles 文章, events 赛事与内战, teams 战队, members
 * 成员), each hit already carrying its address, the excerpt around the first
 * term (40 characters either side, … at cut ends) and the tag; at most 20 hits
 * a group with `truncated` when there were more. Go sends five flat lists
 * without excerpts today; the cast lives here only, and goes when it does.
 */
export type SearchHit = { title: string; url: string; excerpt: string; meta: string }
export type SearchGroup = { key: "articles" | "events" | "teams" | "members"; label: string; hits: SearchHit[]; truncated: boolean }
export type SearchResults = { query: string; groups: SearchGroup[] }

export async function searchSite(api: Requester, q: string): Promise<SearchResults> {
  return (await getApiSearch(api, { q })) as unknown as SearchResults
}
