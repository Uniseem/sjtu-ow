<script lang="ts">
import type { LoadCtx } from "../router"
import { searchSite, type SearchGroup } from "../pending-api"

// search/services.py: at most 50 characters, at most 5 words; nothing to look
// for means no call to Go at all (and nothing counted against the limit).
export const MAX_QUERY_LENGTH = 50
export function searchTerms(raw: string | undefined): { query: string; terms: string[] } {
  const query = (raw ?? "").trim().slice(0, MAX_QUERY_LENGTH)
  return { query, terms: query.split(/\s+/).filter(Boolean).slice(0, 5) }
}

// search/templates/search/results.html. Go's 429 is the 429 page, as before.
export async function load(ctx: LoadCtx) {
  const { query, terms } = searchTerms(ctx.query.q)
  const groups: SearchGroup[] = terms.length ? (await searchSite(ctx.api, query)).groups : []
  return { title: query ? `搜索：${query} · 站内搜索` : "站内搜索", query, searched: terms.length > 0, groups }
}
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { usePageMeta } from "../meta"

const data = inject<{ title: string; query: string; searched: boolean; groups: SearchGroup[] }>("page-data")
const groups = computed(() => data?.groups ?? [])
const total = computed(() => groups.value.reduce((sum, group) => sum + group.hits.length, 0))
usePageMeta(() => ({ title: data?.title ?? "站内搜索", description: "搜索文章、赛事与内战、战队和成员。" }))
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead">
      <div class="l-container l-container--narrow">
        <h1>站内搜索</h1>
        <form action="/search/" method="get" role="search" class="c-searchbar">
          <CIcon name="search" />
          <label class="sr-only" for="search-q">搜索词</label>
          <input id="search-q" type="search" name="q" :value="data?.query" maxlength="50" placeholder="文章、赛事、内战、战队、成员" autofocus>
          <button type="submit" class="c-btn c-btn--primary">搜索</button>
        </form>
      </div>
    </header>
    <div class="l-container l-container--narrow pb-16 lg:pb-24">
      <p v-if="!data?.searched" class="max-w-2xl text-fg-2">只搜公开内容：已发布的文章、赛事和内战、未解散的战队、成员展示页上的成员。多个词用空格隔开，每个词都要命中。</p>
      <CEmpty v-else-if="total === 0" title="没有找到" :message="`没有找到和「${data.query}」有关的内容。换个词试试。`" />
      <template v-else>
        <p class="mb-8 text-fg-2">「{{ data.query }}」共 {{ total }} 条结果</p>
        <div class="grid gap-10">
          <!-- Ids count every group, shown or not, as the old forloop.counter did. -->
          <template v-for="(group, index) in groups" :key="group.key">
            <section v-if="group.hits.length" :aria-labelledby="`search-${index + 1}`">
              <div class="c-sectionhead">
                <h2 :id="`search-${index + 1}`">{{ group.label }}</h2>
              </div>
              <ol class="c-rows">
                <li v-for="hit in group.hits" :key="hit.url" class="c-row c-row--plain">
                  <div class="c-row__main">
                    <h3 class="c-row__title"><a :href="hit.url" class="c-stretch">{{ hit.title }}</a></h3>
                    <p v-if="hit.excerpt" class="c-row__text">{{ hit.excerpt }}</p>
                  </div>
                  <span v-if="hit.meta" class="c-tag">{{ hit.meta }}</span>
                </li>
              </ol>
              <p v-if="group.truncated" class="mt-3 text-fg-3">只显示前 20 条，换个更具体的词。</p>
            </section>
          </template>
        </div>
      </template>
    </div>
  </main>
</template>
