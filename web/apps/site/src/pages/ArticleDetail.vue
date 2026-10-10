<script lang="ts">
import {
  deleteApiCommentsId,
  getApiPageNewsSlug,
  patchApiCommentsId,
  postApiArticlesIdComments,
  postApiCommentsIdHide,
  postApiCommentsIdLike,
  postApiCommentsIdPin,
} from "@sjtu-ow/api"
import type { LoadCtx } from "../router"
import { commentThread, type ArticleDetail, type CommentThread } from "../pending-api"

// content/templates/content/article_page.html (design-details 6): the cover
// with the words on it, one reading column with the contents beside it on
// wide screens, the author, the article before and after, comments, and more
// from the category. Go's 404 (missing, not live, no permission) stays a 404.
export async function load(ctx: LoadCtx) {
  const article: ArticleDetail = await getApiPageNewsSlug(ctx.api, ctx.params.slug!)
  const sort = ctx.query.sort === "top" ? "top" : "new"
  const page = Math.max(1, Number.parseInt(ctx.query.comments ?? "", 10) || 1)
  // A draft (visible to its author here, comments API answers 404) paints an
  // empty section as the old thread() did for an unpublished page.
  let thread: CommentThread = { total: 0, page, pageSize: 20, comments: [] }
  try {
    thread = await commentThread(ctx.api, article.id, { sort, page })
  } catch (err) {
    if (typeof err !== "object" || err === null || !("status" in err) || Number(err.status) !== 404) throw err
  }
  return {
    title: article.seo_title || article.title,
    description: article.search_description || article.summary,
    article,
    thread,
    sort,
  }
}
</script>
<script setup lang="ts">
import { computed, inject, ref } from "vue"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CComments from "@sjtu-ow/ui/CComments.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CTournamentCard from "@sjtu-ow/ui/CTournamentCard.vue"
import PostCard from "@sjtu-ow/ui/PostCard.vue"
import { imageUrl } from "@sjtu-ow/shared/media"
import { coverPlaceholder } from "@sjtu-ow/shared/pictures"
import { owDate, owISO, owMd } from "@sjtu-ow/shared/time"
import { useApi } from "../api"
import { usePageMeta } from "../meta"
import type { ArticleCard, CommentAbility } from "../pending-api"
import { VIEWER } from "../viewer"
import { toast } from "../toasts"

// The page-data object sheds the previous page's keys on navigation before
// the old component unmounts, so everything reads optional (StandardPage).
const data = inject<{
  title?: string
  article?: ArticleDetail
  thread?: CommentThread
  sort?: string
}>("page-data")
const viewer = inject(VIEWER, { user: null })
const api = useApi()
usePageMeta(() => ({ title: data?.title, description: data?.description }))

const article = computed(() => data?.article)
const pageUrl = computed(() => (article.value ? `/news/${article.value.slug}/` : "/news/"))
// The old section template interpolates page.url raw (no urlencode).
const loginUrl = computed(() => `/accounts/login/?next=${pageUrl.value}`)
// The old template links the category through the parent (the news list).
const categoryHref = computed(() => (article.value?.category_slug ? `/news/?category=${article.value.category_slug}` : "/news/"))
// Design-details 6.2: changed more than a day after it first went out.
const updated = computed(() => {
  const first = article.value?.first_published_at
  const last = article.value?.last_published_at
  if (!first || !last) return null
  return (new Date(last).getTime() - new Date(first).getTime()) / 86400000 > 1 ? new Date(last) : null
})
// Three headings or more get a table of contents (design-details 6.5).
const toc = computed(() => ((article.value?.headings?.length ?? 0) >= 3 ? article.value?.headings ?? [] : []))
const thread = ref<CommentThread>(data?.thread ?? { total: 0, page: 1, pageSize: 20, comments: [] })
const sort = ref(data?.sort ?? "new")
// A member's section is interactive; a feature ban (can_comment, BE-7) shows
// the old post_problems notice once Go sends the flag. The back-office caps
// are a different system (AGENTS), so comments.moderate names the moderators.
const canModerate = computed(() => !!viewer.user && (viewer.user.superuser || viewer.user.caps.includes("comments.moderate")))
const canComment = (user: typeof viewer.user): boolean => (user as (typeof viewer.user & CommentAbility) | null)?.can_comment !== false
const canPost = computed(() => !!viewer.user && !!article.value?.comments_enabled && canComment(viewer.user))
const postProblems = computed(() => (viewer.user && !canComment(viewer.user) ? ["你暂时无法使用此功能，如有疑问请联系管理员"] : []))

function coverSrc(): string {
  const { cover_image_id: cover, default_cover_image_id: pool, id } = article.value ?? { id: 0 }
  if (cover) return imageUrl(cover, "fill-2400x1200")
  if (pool) return imageUrl(pool, "fill-2400x1200")
  return coverPlaceholder(id)
}
// The pool picture drifts, as cover_fallback drew it (13.2.5).
const coverClass = computed(() =>
  (article.value && (article.value.cover_image_id || !article.value.default_cover_image_id))
    ? "c-cover__img"
    : ["c-cover__img", "c-drift", `c-drift--${article.value.id % 4 + 1}`],
)

// One action failing tells the reader and keeps the section: the comment
// itself never changed (I5).
function act(request: Promise<unknown>, page = thread.value.page) {
  request
    .then(async () => {
      thread.value = await commentThread(api, article.value!.id, { sort: sort.value, page })
    })
    .catch((err) => toast(err?.message ?? "操作失败，请重试", "error"))
}
function more(next: number) {
  commentThread(api, article.value!.id, { sort: sort.value, page: next })
    .then((fresh) => {
      const seen = new Set(thread.value.comments.map((c) => c?.id))
      thread.value = { ...fresh, comments: [...thread.value.comments, ...fresh.comments.filter((c) => !seen.has(c?.id))] }
    })
    .catch((err) => toast(err?.message ?? "加载失败，请重试", "error"))
}
const onLike = (id: number) => act(postApiCommentsIdLike(api, id))
const onCreate = (payload: { content: string }) => act(postApiArticlesIdComments(api, article.value!.id, { content: payload.content }))
const onReply = (payload: { parentId: number; content: string }) =>
  act(postApiArticlesIdComments(api, article.value!.id, { content: payload.content, parent_id: payload.parentId }))
const onEdit = (payload: { id: number; content: string }) => act(patchApiCommentsId(api, payload.id, { content: payload.content }))
const onRemove = (id: number) => act(deleteApiCommentsId(api, id))
const onHide = (change: { id: number; hidden: boolean }) => act(postApiCommentsIdHide(api, change.id, { hidden: change.hidden }))
const onPin = (change: { id: number; pinned: boolean }) => act(postApiCommentsIdPin(api, change.id, { article_id: article.value!.id, pinned: change.pinned }))

const related = computed(() => (article.value?.related ?? []) as ArticleCard[])
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-cover">
      <img :src="coverSrc()" :class="coverClass" alt="" width="2400" height="1200">
      <div class="c-cover__body">
        <nav class="c-crumbs" aria-label="位置">
          <a href="/">首页</a><span class="c-crumbs__sep">/</span>
          <a href="/news/">资讯</a><span class="c-crumbs__sep">/</span>
          <a :href="categoryHref">{{ article.category_name }}</a>
        </nav>
        <p><a :href="categoryHref" class="c-tag c-tag--accent">{{ article.category_name }}</a></p>
        <h1 class="c-cover__title">{{ article.title }}</h1>
        <p v-if="article.summary" class="c-cover__summary">{{ article.summary }}</p>
        <ul class="c-cover__facts c-article__meta" aria-label="文章信息">
          <li>
            <CAvatar :person="{ id: article.author?.user_id, nickname: article.author?.nickname ?? article.author_name }" size="xs" plain />
            <span class="c-article__author">{{ article.author?.nickname ?? article.author_name }}</span>
          </li>
          <li v-if="article.first_published_at">
            <CIcon name="calendar" />
            <time class="font-numeric" :datetime="owISO(new Date(article.first_published_at))">{{ owDate(new Date(article.first_published_at)) }}</time>
          </li>
          <li v-if="updated">
            <CIcon name="edit" />更新于
            <time class="font-numeric" :datetime="owISO(updated)">{{ owMd(updated) }}</time>
          </li>
          <li>
            <CIcon name="clock" />约 <span class="font-numeric">{{ article.reading_time }}</span> 分钟
          </li>
          <li>
            <CIcon name="text" /><span class="font-numeric">{{ article.char_count }}</span> 字
          </li>
          <li>
            <a href="#comments"><CIcon name="chat" /><span class="font-numeric">{{ data.thread.total || article.comment_total || 0 }}</span> 条评论</a>
          </li>
        </ul>
      </div>
    </header>

    <div class="c-reading" :class="{ 'c-reading--toc': toc.length }">
      <template v-if="toc.length">
        <details class="c-toc c-toc--fold">
          <summary><CIcon name="list" />目录</summary>
          <ol class="c-toc__list">
            <li v-for="heading in toc" :key="heading.id" :class="`c-toc__item c-toc__item--h${heading.level}`"><a :href="`#${heading.id}`">{{ heading.text }}</a></li>
          </ol>
        </details>
        <nav class="c-toc c-toc--side" aria-label="目录">
          <p class="c-toc__head">目录</p>
          <ol class="c-toc__list">
            <li v-for="heading in toc" :key="heading.id" :class="`c-toc__item c-toc__item--h${heading.level}`"><a :href="`#${heading.id}`">{{ heading.text }}</a></li>
          </ol>
        </nav>
      </template>
      <article class="c-article">
        <!-- Go's Markdown renderer cleans body_html (content/markdown, I8). -->
        <div class="c-prose" v-html="article.body_html"></div>

        <aside v-if="article.author" class="c-author" aria-label="作者">
          <CAvatar :person="{ id: article.author.user_id, nickname: article.author.nickname, is_active: article.author.is_active, avatar_image_id: article.author.avatar_image_id }" size="md" />
          <div class="min-w-0">
            <p class="c-author__name">
              <a v-if="article.author.user_id" :href="`/members/${article.author.user_id}/`">{{ article.author.nickname }}</a>
              <template v-else>{{ article.author.nickname }}</template>
            </p>
            <p v-if="article.author.motto" class="c-author__motto">“{{ article.author.motto }}”</p>
            <p class="c-author__meta">在本站发表了 <span class="font-numeric">{{ article.author_article_count ?? 0 }}</span> 篇文章</p>
          </div>
        </aside>

        <section v-if="article.tournament" class="c-article__part" aria-labelledby="article-tournament">
          <h2 id="article-tournament" class="c-article__parthead">关联赛事</h2>
          <div class="c-media-grid">
            <CTournamentCard :tournament="article.tournament" />
          </div>
        </section>

        <nav v-if="article.older || article.newer" class="c-sequel" aria-label="上一篇和下一篇">
          <a v-if="article.older" :href="`/news/${article.older.slug}/`" class="c-sequel__item">
            <span class="c-sequel__dir"><CIcon name="arrow-left" />上一篇</span>
            <span class="c-sequel__title">{{ article.older.title }}</span>
          </a>
          <span v-else></span>
          <a v-if="article.newer" :href="`/news/${article.newer.slug}/`" class="c-sequel__item c-sequel__item--next">
            <span class="c-sequel__dir">下一篇<CIcon name="arrow-right" /></span>
            <span class="c-sequel__title">{{ article.newer.title }}</span>
          </a>
        </nav>

        <CComments
          :comments-enabled="article.comments_enabled"
          :thread="thread"
          :sort="sort"
          :interactive="!!viewer.user"
          :can-post="canPost"
          :post-problems="postProblems"
          :can-moderate="canModerate"
          :viewer-id="viewer.user?.id"
          :page-url="pageUrl"
          :login-url="loginUrl"
          @more="more"
          @create="onCreate"
          @reply="onReply"
          @edit="onEdit"
          @remove="onRemove"
          @hide="onHide"
          @pin="onPin"
        />
      </article>
    </div>

    <section v-if="related.length" class="l-container c-article__more" aria-labelledby="article-related">
      <div class="c-sectionhead">
        <h2 id="article-related">{{ article.category_name }}的更多文章</h2>
        <a :href="categoryHref" class="c-btn c-btn--quiet">全部<CIcon name="arrow-right" /></a>
      </div>
      <div class="c-media-grid c-media-grid--3">
        <PostCard v-for="item in related" :key="item.id" :article="item" />
      </div>
    </section>
  </main>
</template>
