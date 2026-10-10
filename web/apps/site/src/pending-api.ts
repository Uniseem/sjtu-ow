import {
  getApiArticlesIdComments,
  type GetApiPageNewsOut,
  type GetApiPageNewsSlugOut,
  type Requester,
} from "@sjtu-ow/api"

// Fields the rewritten pages read that Go does not send yet. Each entry is a
// backend task in STATUS「交给后端（GPT）」(the id in brackets). The page
// already renders them when present, as the old template did. This file is the
// frontend's (AGENTS「Claude 和 GPT 分开做」): when the backend marks an entry
// done and apigen has regenerated, the next frontend round deletes it here,
// uses the generated type and runs that page's parity.

/** One article card, as NewsItemOut comes back inside lists and page bodies. */
export type ArticleCard = NonNullable<GetApiPageNewsOut["items"][number]> & {
  /** [BE-5] the category's default cover, what cover_fallback drew. */
  default_cover_image_id?: number | null
}

/**
 * [BE-4] GET /api/page/news/{slug}: what content ArticlePage.get_context
 * reads besides GetApiPageNewsSlugOut — the author card (member link
 * /members/{user_id}/, face, motto, stopped accounts show no face), how many
 * published articles the author has, last_published_at for the update line
 * (shown when more than a day after first_published_at), the comment total
 * for the head facts, the article before and after in the same column, three
 * more from the category, the related tournament card, and the SEO fields.
 */
export type ArticleAuthor = {
  user_id: number
  nickname: string
  avatar_image_id?: number | null
  is_active?: boolean
  motto?: string
}

export type TournamentCard = {
  id: number
  title: string
  phase: string
  starts_at?: string | null
  registration_opens_at?: string | null
  registration_closes_at?: string | null
  cover_image_id?: number | null
  default_cover_image_id?: number | null
  roster_min: number
  roster_max: number
  registration_mode_label: string
  takes_individuals: boolean
  sjtu_only: boolean
}

export type ArticleDetail = GetApiPageNewsSlugOut & {
  /** [BE-4] category slug for the crumbs and tag link (?category=…). */
  category_slug?: string
  /** [BE-4] the category's default cover, what cover_fallback drew. */
  default_cover_image_id?: number | null
  author?: ArticleAuthor | null
  author_article_count?: number
  last_published_at?: string | null
  comment_total?: number
  older?: { slug: string; title: string } | null
  newer?: { slug: string; title: string } | null
  related?: ArticleCard[]
  tournament?: TournamentCard | null
  seo_title?: string
  search_description?: string
}

/**
 * [BE-5] GET /api/page/news: the named categories (sort_order, then name)
 * for the filter tabs and the rendered column intro (page.intro|markdown).
 */
export type NewsList = GetApiPageNewsOut & {
  categories?: { slug: string; name: string }[]
  intro_html?: string
}

/**
 * [BE-7] GET /api/session user: can_use("article_comment") on its own — the
 * comment section pre-renders the denial as the old post_problems did
 * (accounts/permissions.py FEATURE_DENIED_MESSAGE). The back-office caps are
 * a different system and cannot answer this.
 */
export type CommentAbility = { can_comment?: boolean }

// The recursive comment shape (server/internal/comments/model.go): apigen
// cannot express []*Comment yet and emits `replies` as unknown[], so the
// thread is narrowed here — the only cast, as SearchResults was. Delete with
// the generator's fix.
export type CommentNode = {
  id: number
  article_id: number
  user_id?: number | null
  author_name: string
  parent_id?: number | null
  reply_to_user_id?: number | null
  reply_to_user_name?: string
  content: string
  is_pinned: boolean
  is_hidden: boolean
  is_deleted: boolean
  is_tombstone?: boolean
  like_count: number
  liked_by_me?: boolean
  reply_count?: number
  replies?: CommentNode[]
  version: number
  created_at: string
  updated_at: string
}

export type CommentThread = {
  total: number
  page: number
  page_size: number
  comments: (CommentNode | null)[]
}

export async function commentThread(
  api: Requester,
  articleId: number | string,
  query: { sort?: string; page?: number } = {},
): Promise<CommentThread> {
  return (await getApiArticlesIdComments(api, articleId, query)) as unknown as CommentThread
}
