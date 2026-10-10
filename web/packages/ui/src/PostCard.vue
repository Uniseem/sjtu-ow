<script setup lang="ts">
import { imageUrl } from "@sjtu-ow/shared/media"
import { coverPlaceholder } from "@sjtu-ow/shared/pictures"
import { owMd, owISO } from "@sjtu-ow/shared/time"
import CAvatar from "./CAvatar.vue"
import type { AvatarPerson } from "./types"
defineProps<{
  article: { id: number; slug: string; title: string; category_name?: string; cover_image_id?: number | null; default_cover_image_id?: number | null; summary?: string; reading_time?: number; author_name?: string; author?: AvatarPerson | null; first_published_at?: string | null; pinned?: boolean }
  summary?: boolean; pinned?: boolean
}>()
</script>
<template>
  <article class="c-media">
    <div class="c-media__pic">
      <img v-if="article.cover_image_id" :src="imageUrl(article.cover_image_id, 'fill-960x540')" alt="" loading="lazy">
      <img v-else-if="article.default_cover_image_id" :src="imageUrl(article.default_cover_image_id, 'fill-960x540')" width="960" height="540" :class="`c-drift c-drift--${article.id % 4 + 1}`" loading="lazy" alt="">
      <img v-else :src="coverPlaceholder(article.id)" width="960" height="540" loading="lazy" alt="">
    </div>
    <p class="c-media__meta"><span v-if="article.category_name" class="c-tag">{{ article.category_name }}</span><span v-if="pinned || article.pinned" class="c-tag c-tag--accent">置顶</span><time :datetime="article.first_published_at ? owISO(new Date(article.first_published_at)) : undefined">{{ article.first_published_at ? owMd(new Date(article.first_published_at)) : '' }}</time></p>
    <h3 class="c-media__title"><a :href="`/news/${article.slug}/`" class="c-stretch" :title="article.title">{{ article.title }}</a></h3>
    <p v-if="summary && article.summary" class="c-media__summary">{{ article.summary }}</p>
    <p v-if="article.author || article.author_name" class="c-media__byline"><CAvatar :person="article.author ?? { nickname: article.author_name }" size="xs" /><span class="c-media__author">{{ article.author?.nickname ?? article.author_name }}</span><span aria-hidden="true">·</span><span>约 <span class="font-numeric">{{ article.reading_time ?? 0 }}</span> 分钟</span></p>
  </article>
</template>
