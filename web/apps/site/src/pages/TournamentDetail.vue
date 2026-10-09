<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const id = ctx?.params?.id ?? ""
  let tournament: any = null
  try {
    const res = await f(`${base}/api/tournaments/${id}`)
    if (res.ok) {
      tournament = await res.json()
    }
  } catch {}

  return {
    title: tournament?.title ?? "赛事详情",
    tournament,
  }
}
</script>
<script setup lang="ts">
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import { VIEWER, type Viewer } from "../viewer"

const data = inject<any>("page-data")
const viewer = inject<Viewer>(VIEWER)
const tournament = computed(() => data?.tournament)
useHead({ title: tournament.value?.title ? `${tournament.value.title} - SJTU-OW` : "赛事详情 - SJTU-OW" })
</script>
<template>
  <main id="main" class="flex-1">
    <div v-if="tournament">
      <header class="c-cover">
        <div class="c-cover__body">
          <nav class="c-crumbs" aria-label="位置">
            <a href="/">首页</a><span class="c-crumbs__sep">/</span>
            <a href="/tournaments/">赛事</a><span class="c-crumbs__sep">/</span>
            <span>{{ tournament.title }}</span>
          </nav>
          <p>
            <span v-if="tournament.status === 'open'" class="c-status c-status--live">报名中</span>
            <span v-else-if="tournament.status === 'upcoming'" class="c-status c-status--info">即将开放</span>
            <span v-else class="c-status">已截止</span>
          </p>
          <h1 class="c-cover__title">{{ tournament.title }}</h1>
          <p v-if="tournament.description" class="c-cover__summary">{{ tournament.description }}</p>
        </div>
      </header>

      <div class="l-container py-12">
        <div class="max-w-3xl space-y-8">
          <section>
            <h2 class="text-xl font-bold mb-4">比赛规程</h2>
            <div class="c-prose bg-stone-900/40 p-6 rounded-lg border border-stone-800">
              <p>{{ tournament.rules || '暂无特殊规则说明。请遵守上海交大守望先锋社区参赛守则与竞技精神。' }}</p>
            </div>
          </section>

          <section class="flex flex-wrap gap-4 pt-4">
            <template v-if="tournament.status === 'open'">
              <a
                v-if="tournament.takes_individuals"
                :href="`/tournaments/${tournament.id}/signup/`"
                class="c-btn c-btn--primary"
              >个人报名参赛</a>
              <a
                v-else
                :href="`/tournaments/${tournament.id}/register/`"
                class="c-btn c-btn--primary"
              >战队报名参赛</a>
            </template>
            <a href="/tournaments/" class="c-btn c-btn--secondary">返回赛事列表</a>
          </section>
        </div>
      </div>
    </div>
    <div v-else class="l-container py-20 text-center text-stone-400">
      <p class="text-xl">赛事不存在或已被取消</p>
      <a href="/tournaments/" class="c-btn c-btn--quiet mt-4">返回赛事列表</a>
    </div>
  </main>
</template>
