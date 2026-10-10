<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let members: any[] = []
  let groups: any[] = []
  try {
    const res = await f(`${base}/api/members`)
    if (res.ok) {
      const data = await res.json()
      members = data.members ?? data.items ?? []
      groups = data.groups ?? []
    }
  } catch {}

  return {
    title: "成员",
    members,
    groups,
  }
}
</script>
<script setup lang="ts">
import { imageUrl } from "../media"
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import { initial, hue } from "../initial"

const data = inject<any>("page-data")
useHead({ title: data?.title ? `${data.title} - SJTU-OW` : "成员 - SJTU-OW" })

const members = computed(() => data?.members ?? [])
const groups = computed(() => data?.groups ?? [])
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <div class="l-container">
        <h1>成员</h1>
        <p class="c-pagehead__lede text-stone-300">交大守望先锋社区的活跃成员们。共 {{ members.length }} 位成员。</p>
      </div>
    </header>

    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div v-if="members.length > 0" class="c-people grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div
          v-for="m in members"
          :key="m.id"
          class="c-person flex items-center gap-4 p-4 rounded-lg bg-stone-900/60 border border-stone-800"
        >
          <span :class="['c-avatar', 'c-avatar--md', `c-hue-${hue(m.id)}`]">
            <img v-if="m.avatar_image_id" :src="imageUrl(m.avatar_image_id, 'fill-176x176')" alt="" />
            <template v-else>{{ initial(m.nickname) }}</template>
          </span>
          <div class="min-w-0 flex-1">
            <a :href="`/members/${m.id}/`" class="c-person__name font-semibold hover:text-primary-text block truncate">
              {{ m.nickname }}
            </a>
            <p v-if="m.motto" class="c-person__motto text-xs text-stone-400 truncate mt-1">“{{ m.motto }}”</p>
            <p class="text-xs text-stone-500 mt-1">
              <span v-if="m.is_sjtu" class="text-primary-text font-medium">交大</span>
              <span v-if="m.team_name" class="ml-1 text-stone-400">· {{ m.team_name }}</span>
            </p>
          </div>
        </div>
      </div>
      <div v-else class="text-center py-16 text-stone-400">
        <p class="text-lg">暂无成员数据</p>
      </div>
    </div>
  </main>
</template>
