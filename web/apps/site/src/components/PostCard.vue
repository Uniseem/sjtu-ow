<script setup lang="ts">
import { imageUrl } from "../media"
import { computed } from "vue"

const props = defineProps<{
  article: {
    id: number
    slug: string
    title: string
    category_name?: string
    cover_image_id?: number | null
    summary?: string
    reading_time?: number
    author_name?: string
    first_published_at?: string | null
    pinned?: boolean
  }
  summary?: boolean
}>()

const coverSrc = computed(() => {
  if (props.article.cover_image_id) {
    return imageUrl(props.article.cover_image_id, "fill-960x540")
  }
  const idx = String((props.article.id % 8) + 1).padStart(2, "0")
  return `/static/img/placeholders/cover-${idx}.svg`
})

const dateText = computed(() => {
  if (!props.article.first_published_at) return ""
  const d = new Date(props.article.first_published_at)
  if (isNaN(d.getTime())) return ""
  return `${d.getMonth() + 1}月${d.getDate()}日`
})
</script>
<template>
  <article class="c-media">
    <div class="c-media__pic">
      <img :src="coverSrc" alt="" loading="lazy" />
    </div>
    <p class="c-media__meta">
      <span v-if="article.category_name" class="c-tag">{{ article.category_name }}</span>
      <span v-if="article.pinned" class="c-tag c-tag--accent">置顶</span>
      <time v-if="dateText" :datetime="article.first_published_at ?? undefined">{{ dateText }}</time>
    </p>
    <h3 class="c-media__title">
      <a :href="`/news/${article.slug}/`" class="c-stretch" :title="article.title">{{ article.title }}</a>
    </h3>
    <p v-if="summary && article.summary" class="c-media__summary">{{ article.summary }}</p>
    <p v-if="article.author_name || article.reading_time" class="c-media__byline">
      <span v-if="article.author_name" class="c-media__author">{{ article.author_name }}</span>
      <template v-if="article.author_name && article.reading_time"><span aria-hidden="true">·</span></template>
      <span v-if="article.reading_time">约 <span class="font-numeric">{{ article.reading_time }}</span> 分钟</span>
    </p>
  </article>
</template>
