<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const id = ctx?.params?.id ?? ""
  let team: any = null
  try {
    const res = await f(`${base}/api/teams/${id}`)
    if (res.ok) {
      team = await res.json()
    }
  } catch {}

  return {
    title: team?.name ?? "战队详情",
    team,
  }
}
</script>
<script setup lang="ts">
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import { initial, hue } from "../initial"

const data = inject<any>("page-data")
const team = computed(() => data?.team)
useHead({ title: team.value?.name ? `${team.value.name} - 战队 - SJTU-OW` : "战队详情 - SJTU-OW" })
</script>
<template>
  <main id="main" class="flex-1">
    <div v-if="team">
      <header class="c-stage c-stage--team">
        <div class="l-container l-container--narrow c-stage__body">
          <nav class="c-crumbs" aria-label="位置">
            <a href="/">首页</a><span class="c-crumbs__sep">/</span>
            <a href="/teams/">战队</a><span class="c-crumbs__sep">/</span>
            <span>{{ team.name }}</span>
          </nav>
          <div class="c-stage__team flex items-center gap-6 mt-4">
            <span :class="['c-teams__logo', 'c-teams__logo--lg', `c-hue-${hue(team.id)}`]">
              <img v-if="team.logo_image_id" :src="`/api/images/${team.logo_image_id}`" :alt="team.name" />
              <template v-else>{{ initial(team.name) }}</template>
            </span>
            <div class="min-w-0">
              <p class="c-stage__tags">
                <span v-if="team.disbanded_at" class="c-status">已解散</span>
                <span v-else-if="team.is_recruiting" class="c-status c-status--live">招募中</span>
                <span v-else class="c-status">暂不招募</span>
              </p>
              <h1 class="c-stage__title text-3xl font-bold mt-2">{{ team.name }}</h1>
              <dl class="c-stage__facts flex gap-6 mt-3 text-stone-300 text-sm">
                <div><dt class="inline text-stone-400">成员：</dt><dd class="inline">{{ team.members?.length ?? 0 }} 人</dd></div>
                <div><dt class="inline text-stone-400">成立：</dt><dd class="inline">{{ team.created_at?.slice(0, 10) }}</dd></div>
              </dl>
            </div>
          </div>
        </div>
      </header>

      <div class="l-container l-container--narrow l-section py-10">
        <div class="space-y-10">
          <!-- 简介 -->
          <section v-if="team.description">
            <h2 class="text-xl font-bold mb-3">简介</h2>
            <p class="text-stone-300 whitespace-pre-line leading-7">{{ team.description }}</p>
          </section>

          <!-- 现役成员 -->
          <section>
            <h2 class="text-xl font-bold mb-4">现役成员</h2>
            <ul v-if="team.members && team.members.length > 0" class="c-squad grid sm:grid-cols-2 gap-4">
              <li v-for="m in team.members" :key="m.user_id" class="c-squad__item flex items-center gap-3 p-3 rounded bg-stone-900/40 border border-stone-800">
                <span class="c-avatar c-avatar--sm" :class="`c-hue-${hue(m.user_id)}`">{{ initial(m.nickname) }}</span>
                <div>
                  <a :href="`/members/${m.user_id}/`" class="font-semibold">{{ m.nickname }}</a>
                  <span v-if="m.role === 'captain'" class="ml-2 text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary-text">队长</span>
                </div>
              </li>
            </ul>
            <div v-else class="text-stone-500">暂无队员信息</div>
          </section>

          <!-- 操作按钮 -->
          <section v-if="!team.disbanded_at" class="pt-4 flex gap-4">
            <a v-if="team.is_recruiting" :href="`/teams/${team.id}/apply/`" class="c-btn c-btn--primary">申请加入</a>
            <a href="/teams/" class="c-btn c-btn--secondary">返回战队列表</a>
          </section>
        </div>
      </div>
    </div>
    <div v-else class="l-container py-20 text-center text-stone-400">
      <p class="text-xl">战队不存在或已被解散</p>
      <a href="/teams/" class="c-btn c-btn--quiet mt-4">返回战队列表</a>
    </div>
  </main>
</template>
