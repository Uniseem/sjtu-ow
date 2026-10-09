<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const urlObj = new URL(ctx?.url ?? "/teams/", "http://site")
  const role = urlObj.searchParams.get("role") ?? ""
  const recruiting = urlObj.searchParams.get("recruiting") === "1"

  let teams: any[] = []
  try {
    const res = await f(`${base}/api/teams`)
    if (res.ok) {
      const data = await res.json()
      teams = data.teams ?? data.items ?? []
    }
  } catch {}

  return {
    title: "战队",
    teams,
    role,
    recruiting,
  }
}
</script>
<script setup lang="ts">
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import TeamTile from "../components/TeamTile.vue"
import CIcon from "../components/CIcon.vue"

const data = inject<any>("page-data")
useHead({ title: data?.title ?? "战队" })

const allTeams = computed(() => data?.teams ?? [])
const activeRole = computed(() => data?.role ?? "")
const isRecruiting = computed(() => data?.recruiting ?? false)

const filteredTeams = computed(() => {
  return allTeams.value.filter((t: any) => {
    if (isRecruiting.value && !t.is_recruiting) return false
    if (activeRole.value) {
      const roles = (t.wanted_roles || t.recruiting_roles || "").toLowerCase()
      if (!roles.includes(activeRole.value.toLowerCase())) return false
    }
    return true
  })
})
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <div class="l-container">
        <div class="c-pagehead__row">
          <div>
            <h1>战队</h1>
            <p class="c-pagehead__lede text-stone-300">社团里的固定队伍，每队最多 12 人。找一支招募中的申请加入，或者自己建一支。</p>
          </div>
          <div class="c-pagehead__actions">
            <a href="/teams/new/" class="c-btn c-btn--primary"><CIcon name="plus" />创建战队</a>
          </div>
        </div>
        <nav class="c-tabs mt-8" aria-label="筛选">
          <a href="/teams/" :aria-current="!isRecruiting && !activeRole ? 'page' : undefined">全部<span class="c-tabs__count">{{ allTeams.length }}</span></a>
          <a href="/teams/?recruiting=1" :aria-current="isRecruiting ? 'page' : undefined">只看招募中</a>
          <a href="/teams/?role=tank" :aria-current="activeRole === 'tank' ? 'page' : undefined" data-role-tab="tank">缺重装</a>
          <a href="/teams/?role=damage" :aria-current="activeRole === 'damage' ? 'page' : undefined" data-role-tab="damage">缺输出</a>
          <a href="/teams/?role=support" :aria-current="activeRole === 'support' ? 'page' : undefined" data-role-tab="support">缺支援</a>
        </nav>
      </div>
    </header>

    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <ul v-if="filteredTeams.length > 0" class="c-teams c-teams--list">
        <TeamTile v-for="team in filteredTeams" :key="team.id" :team="team" />
      </ul>
      <div v-else class="text-center py-16 text-stone-400">
        <p class="text-lg">暂无符合条件的战队</p>
        <p class="text-sm mt-1">可以看看全部战队，或者自己建一支。</p>
        <a href="/teams/new/" class="c-btn c-btn--primary mt-4">创建战队</a>
      </div>
    </div>
  </main>
</template>
