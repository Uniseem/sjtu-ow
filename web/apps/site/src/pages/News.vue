<script lang="ts">
import { getApiPageNews } from "@sjtu-ow/api"
import type { LoadCtx } from "../router"
import type { NewsList } from "../pending-api"

// content/templates/content/article_index_page.html (design 13.2.7): head
// with the column intro, category filter, picture cards, pager. The filter is
// links, so the list stays a plain GET page (13.7). Go's 404 for an unknown
// category stays a 404.
export async function load(ctx: LoadCtx) {
  const category = (ctx.query.category ?? "").trim()
  const page = Math.max(1, Number.parseInt(ctx.query.page ?? "", 10) || 1)
  const data: NewsList = await getApiPageNews(ctx.api, { category: category || undefined, page })
  return {
    title: "资讯",
    data,
    category,
    page,
  }
}
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import CPager from "@sjtu-ow/ui/CPager.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import PostCard from "@sjtu-ow/ui/PostCard.vue"
import { usePageMeta } from "../meta"
import type { ArticleCard, NewsList } from "../pending-api"

// The page-data object sheds the previous page's keys on navigation before
// the old component unmounts, so the list falls back to an empty shape.
const data = inject<{ title: string; data?: NewsList; category?: string; page?: number }>("page-data")
usePageMeta(() => ({ title: "资讯" }))

const list = computed(() => data?.data ?? { total: 0, page: 1, page_size: 12, items: [] })
const categories = computed(() => list.value.categories ?? [])
const articles = computed(() => (list.value.items ?? []) as ArticleCard[])
// The old pager keeps the category filter (extra_query without page=).
const extraQuery = computed(() => (data?.category ? `category=${encodeURIComponent(data.category)}` : ""))
const intro = computed(() => (list.value.intro_html ?? "").trim())
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <CPagehead section="news" />
      <div class="l-container">
        <div class="c-pagehead__row">
          <div>
            <h1>资讯</h1>
            <div v-if="intro" class="c-pagehead__lede" v-html="intro"></div>
          </div>
          <div class="c-pagehead__actions">
            <a href="/submit/" class="c-btn c-btn--secondary"><CIcon name="pen" />我要投稿</a>
          </div>
        </div>
        <!-- Category filter: links, so the list stays a plain GET page (13.7). -->
        <nav class="c-tabs mt-8" aria-label="文章分类">
          <a href="/news/" :aria-current="!data.category ? 'page' : undefined">全部</a>
          <a v-for="cat in categories" :key="cat.slug" :href="`/news/?category=${cat.slug}`" :aria-current="data.category === cat.slug ? 'page' : undefined">{{ cat.name }}</a>
        </nav>
      </div>
    </header>

    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div v-if="articles.length" class="c-media-grid c-media-grid--3">
        <PostCard v-for="article in articles" :key="article.id" :article="article" :summary="true" />
      </div>
      <CEmpty v-else title="暂无文章" message="这个分类还没有已发布的文章。" />
      <CPager v-if="articles.length" :page="list.page" :pages="Math.max(1, Math.ceil(list.total / Math.max(1, list.page_size)))" :extra-query="extraQuery" />
    </div>
  </main>
</template>
