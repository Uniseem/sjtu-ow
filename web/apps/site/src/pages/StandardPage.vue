<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiPageSlug } from "@sjtu-ow/api"
import type { SitePage } from "../pending-api"

// content/templates/content/standard_page.html: /about/, /terms/, /privacy/
// and any other page an editor made under the home page (/<slug>/). Go's 404
// (missing or not live) goes through untouched: the router paints the 404 page.
export async function load(ctx: LoadCtx) {
  const slug = ctx.params.slug ?? new URL(ctx.url, "http://site").pathname.split("/").filter(Boolean)[0]
  const page: SitePage = await getApiPageSlug(ctx.api, slug)
  return { title: page.seo_title || page.title, page }
}
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import { useRoute } from "vue-router"
import { owDate, owISO } from "@sjtu-ow/shared/time"
import { usePageMeta } from "../meta"

const data = inject<{ title: string; page: SitePage }>("page-data")
const page = computed(() => data?.page)
const route = useRoute()
const updated = computed(() => (page.value?.last_published_at ? new Date(page.value.last_published_at) : null))
// The three about pages switch with one row of links (design 13.2.7).
const tabs = [
  { href: "/about/", title: "关于我们" },
  { href: "/terms/", title: "用户协议" },
  { href: "/privacy/", title: "隐私政策" },
]
usePageMeta(() => ({ title: data?.title ?? "", description: page.value?.search_description }))
</script>
<template>
  <main id="main" class="flex-1">
    <article v-if="page" class="c-article">
      <header class="c-article__head">
        <nav class="c-tabs" aria-label="关于本站">
          <a v-for="tab in tabs" :key="tab.href" :href="tab.href" :aria-current="route.path === tab.href ? 'page' : undefined">{{ tab.title }}</a>
        </nav>
        <h1 class="c-article__title">{{ page.title }}</h1>
        <p v-if="updated" class="c-article__meta">最后更新 <time class="font-numeric" :datetime="owISO(updated)">{{ owDate(updated) }}</time></p>
      </header>
      <!-- Go's Markdown renderer cleans body_html (content/markdown, I8). -->
      <div class="c-prose" v-html="page.body_html"></div>
    </article>
  </main>
</template>
