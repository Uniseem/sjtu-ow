<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const slug = ctx?.params?.slug ?? ""
  let article: any = null
  try {
    const res = await f(`${base}/api/page/news/${encodeURIComponent(slug)}`)
    if (res.ok) {
      article = await res.json()
    }
  } catch {}

  return {
    title: article?.title ?? "文章详情",
    article,
  }
}
</script>
<script setup lang="ts">
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import CIcon from "../components/CIcon.vue"
import { initial, hue } from "../initial"

const data = inject<any>("page-data")
const article = computed(() => data?.article)
useHead({ title: article.value?.title ? `${article.value.title} - SJTU-OW` : "文章详情 - SJTU-OW" })

const dateText = computed(() => {
  if (!article.value?.first_published_at) return ""
  const d = new Date(article.value.first_published_at)
  if (isNaN(d.getTime())) return ""
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
})
</script>
<template>
  <main id="main" class="flex-1">
    <div v-if="article">
      <header class="c-cover">
        <div class="c-cover__body">
          <nav class="c-crumbs" aria-label="位置">
            <a href="/">首页</a><span class="c-crumbs__sep">/</span>
            <a href="/news/">资讯</a><span class="c-crumbs__sep">/</span>
            <span>{{ article.category_name }}</span>
          </nav>
          <p><span class="c-tag c-tag--accent">{{ article.category_name }}</span></p>
          <h1 class="c-cover__title">{{ article.title }}</h1>
          <p v-if="article.summary" class="c-cover__summary">{{ article.summary }}</p>
          <ul class="c-cover__facts c-article__meta" aria-label="文章信息">
            <li v-if="article.author_name">
              <span class="c-avatar c-avatar--xs" :class="`c-hue-${hue(article.author_id)}`">{{ initial(article.author_name) }}</span>
              <span class="c-article__author">{{ article.author_name }}</span>
            </li>
            <li v-if="dateText">
              <CIcon name="calendar" />
              <time class="font-numeric">{{ dateText }}</time>
            </li>
            <li v-if="article.reading_time">
              <CIcon name="clock" />
              约 <span class="font-numeric">{{ article.reading_time }}</span> 分钟
            </li>
          </ul>
        </div>
      </header>

      <div class="c-reading">
        <article class="c-article">
          <div class="c-prose" v-html="article.body_html"></div>
        </article>
      </div>
    </div>
    <div v-else class="l-container py-20 text-center text-stone-400">
      <p class="text-xl">文章不存在或尚未发布</p>
      <a href="/news/" class="c-btn c-btn--quiet mt-4">返回资讯列表</a>
    </div>
  </main>
</template>
