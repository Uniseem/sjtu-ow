<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  const id = ctx?.params?.id ?? ""
  let member: any = null
  try {
    const res = await f(`${base}/api/members/${id}`)
    if (res.ok) {
      member = await res.json()
    }
  } catch {}

  return {
    title: member?.nickname ?? "成员个人页",
    member,
  }
}
</script>
<script setup lang="ts">
import { imageUrl } from "../media"
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import { initial, hue } from "../initial"
import CIcon from "../components/CIcon.vue"

const data = inject<any>("page-data")
const member = computed(() => data?.member)
useHead({ title: member.value?.nickname ? `${member.value.nickname} - 成员 - SJTU-OW` : "成员个人页 - SJTU-OW" })
</script>
<template>
  <main id="main" class="flex-1">
    <div v-if="member">
      <header class="c-stage c-stage--member">
        <div class="l-container l-container--narrow c-stage__body">
          <nav class="c-crumbs" aria-label="位置">
            <a href="/">首页</a><span class="c-crumbs__sep">/</span>
            <a href="/members/">成员</a><span class="c-crumbs__sep">/</span>
            <span>{{ member.nickname }}</span>
          </nav>
          <div class="flex items-center gap-6 mt-4">
            <span :class="['c-avatar', 'c-avatar--lg', `c-hue-${hue(member.id)}`]">
              <img v-if="member.avatar_image_id" :src="imageUrl(member.avatar_image_id, 'fill-288x288')" :alt="member.nickname" />
              <template v-else>{{ initial(member.nickname) }}</template>
            </span>
            <div>
              <div class="flex items-center gap-3">
                <h1 class="text-3xl font-bold">{{ member.nickname }}</h1>
                <span v-if="member.is_sjtu" class="c-tag c-tag--accent">上海交大认证</span>
              </div>
              <p v-if="member.motto" class="text-stone-300 mt-2 italic">“{{ member.motto }}”</p>
            </div>
          </div>
        </div>
      </header>

      <div class="l-container l-container--narrow l-section py-10">
        <div class="space-y-10">
          <!-- 游戏 ID 与段位 -->
          <section>
            <h2 class="text-xl font-bold mb-4">游戏账号</h2>
            <div v-if="member.game_accounts && member.game_accounts.length > 0" class="space-y-4">
              <div
                v-for="acc in member.game_accounts"
                :key="acc.id"
                class="p-4 rounded-lg bg-stone-900/60 border border-stone-800"
              >
                <div class="flex items-center justify-between">
                  <span class="font-bold text-lg text-primary-text">{{ acc.battletag }}</span>
                  <div class="flex gap-4 text-sm text-stone-300">
                    <span v-if="acc.rank_tank" class="flex items-center gap-1"><CIcon name="role-tank" class="size-4" />{{ acc.rank_tank }}</span>
                    <span v-if="acc.rank_damage" class="flex items-center gap-1"><CIcon name="role-damage" class="size-4" />{{ acc.rank_damage }}</span>
                    <span v-if="acc.rank_support" class="flex items-center gap-1"><CIcon name="role-support" class="size-4" />{{ acc.rank_support }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-stone-500">该成员暂未公开游戏 ID</div>
          </section>

          <!-- 所属战队 -->
          <section>
            <h2 class="text-xl font-bold mb-4">所属战队</h2>
            <div v-if="member.teams && member.teams.length > 0" class="flex flex-wrap gap-4">
              <a
                v-for="t in member.teams"
                :key="t.id"
                :href="`/teams/${t.id}/`"
                class="flex items-center gap-3 px-4 py-2 rounded-lg bg-stone-900/60 border border-stone-800 hover:border-stone-700"
              >
                <span class="font-semibold">{{ t.name }}</span>
                <span v-if="t.role === 'captain'" class="text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary-text">队长</span>
              </a>
            </div>
            <div v-else class="text-stone-500">自由人，暂未加入任何战队</div>
          </section>
        </div>
      </div>
    </div>
    <div v-else class="l-container py-20 text-center text-stone-400">
      <p class="text-xl">成员不存在</p>
      <a href="/members/" class="c-btn c-btn--quiet mt-4">返回成员列表</a>
    </div>
  </main>
</template>
