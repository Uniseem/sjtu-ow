<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const urlObj = new URL(ctx?.url ?? "/news/", "http://site")
  const cat = urlObj.searchParams.get("category") ?? ""
  const page = parseInt(urlObj.searchParams.get("page") ?? "1", 10) || 1

  let articles: any[] = []
  let categories: any[] = []
  let total = 0

  try {
    const [newsRes, catRes] = await Promise.all([
      f(`${base}/api/page/news?category=${encodeURIComponent(cat)}&page=${page}&page_size=12`),
      f(`${base}/api/categories`),
    ])
    if (newsRes.ok) {
      const data = await newsRes.json()
      articles = data.items ?? []
      total = data.total ?? 0
    }
    if (catRes.ok) {
      const cData = await catRes.json()
      categories = cData.categories ?? []
    }
  } catch {}

  return {
    title: "资讯",
    articles,
    categories,
    total,
    page,
    pageSize: 12,
    activeCategory: cat,
  }
}
</script>
<script setup lang="ts">
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import PostCard from "../components/PostCard.vue"
import CIcon from "../components/CIcon.vue"

const data = inject<any>("page-data")
useHead({ title: data?.title ?? "资讯" })

const articles = computed(() => data?.articles ?? [])
const categories = computed(() => data?.categories ?? [])
const activeCategory = computed(() => data?.activeCategory ?? "")
const total = computed(() => data?.total ?? 0)
const page = computed(() => data?.page ?? 1)
const pageSize = computed(() => data?.pageSize ?? 12)
const totalPages = computed(() => Math.ceil(total.value / pageSize.value))
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <div class="l-container">
        <div class="c-pagehead__row">
          <div>
            <h1>资讯</h1>
            <p class="c-pagehead__lede text-stone-300">交大守望先锋社区的最新消息、赛事战报与深度文章。</p>
          </div>
          <div class="c-pagehead__actions">
            <a href="/submit/" class="c-btn c-btn--secondary"><CIcon name="pen" />我要投稿</a>
          </div>
        </div>
        <!-- 分类选项卡 -->
        <nav class="c-tabs mt-8" aria-label="文章分类">
          <a href="/news/" :aria-current="!activeCategory ? 'page' : undefined">全部</a>
          <a
            v-for="cat in categories"
            :key="cat.slug"
            :href="`/news/?category=${cat.slug}`"
            :aria-current="activeCategory === cat.slug ? 'page' : undefined"
          >{{ cat.name }}</a>
        </nav>
      </div>
    </header>

    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div v-if="articles.length > 0" class="c-media-grid c-media-grid--3">
        <PostCard v-for="art in articles" :key="art.id" :article="art" :summary="true" />
      </div>
      <div v-else class="text-center py-16 text-stone-400">
        <p class="text-lg">暂无文章</p>
        <p class="text-sm mt-1">这个分类还没有已发布的文章。</p>
      </div>

      <!-- 分页导航 -->
      <nav v-if="totalPages > 1" class="c-pager mt-12 flex justify-center gap-2" aria-label="分页导航">
        <a
          v-if="page > 1"
          :href="`/news/?category=${activeCategory}&page=${page - 1}`"
          class="c-btn c-btn--quiet"
        >上一页</a>
        <span class="px-4 py-2 text-sm text-stone-400">第 {{ page }} / {{ totalPages }} 页</span>
        <a
          v-if="page < totalPages"
          :href="`/news/?category=${activeCategory}&page=${page + 1}`"
          class="c-btn c-btn--quiet"
        >下一页</a>
      </nav>
    </div>
  </main>
</template>
