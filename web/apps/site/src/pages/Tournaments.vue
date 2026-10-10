<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let tournaments: any[] = []
  try {
    const res = await f(`${base}/api/tournaments`)
    if (res.ok) {
      const data = await res.json()
      tournaments = data.tournaments ?? data.items ?? []
    }
  } catch {}

  return {
    title: "赛事",
    tournaments,
  }
}
</script>
<script setup lang="ts">
import { imageUrl } from "../media"
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"

const data = inject<any>("page-data")
useHead({ title: data?.title ? `${data.title} - SJTU-OW` : "赛事 - SJTU-OW" })

const tournaments = computed(() => data?.tournaments ?? [])
const openTournaments = computed(() =>
  tournaments.value.filter((t: any) => t.status === "open" || t.phase === "open" || t.status === "upcoming" || t.phase === "upcoming")
)
const pastTournaments = computed(() =>
  tournaments.value.filter((t: any) => !openTournaments.value.includes(t))
)
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <div class="l-container">
        <h1>赛事</h1>
        <p class="c-pagehead__lede text-stone-300">社团自己办的比赛。一般是每人自己报名，由赛事组编成队伍；标着「整队报名」的，由队长为整支战队报名。</p>
      </div>
    </header>

    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div v-if="tournaments.length > 0" class="grid gap-14">
        <!-- 进行中与报名中的赛事 -->
        <section v-if="openTournaments.length > 0">
          <div class="c-sectionhead">
            <h2>报名与进行中</h2>
          </div>
          <div class="c-media-grid c-media-grid--3">
            <article v-for="t in openTournaments" :key="t.id" class="c-media">
              <div class="c-media__pic">
                <img
                  v-if="t.cover_image_id"
                  :src="imageUrl(t.cover_image_id, 'fill-960x540')"
                  alt=""
                  loading="lazy"
                />
                <img
                  v-else
                  :src="`/static/img/placeholders/cover-${String((t.id % 8) + 1).padStart(2, '0')}.svg`"
                  alt=""
                  loading="lazy"
                />
              </div>
              <p class="c-media__meta">
                <span v-if="t.status === 'open' || t.phase === 'open'" class="c-status c-status--live">报名中</span>
                <span v-else class="c-status c-status--info">即将开放</span>
              </p>
              <h3 class="c-media__title">
                <a :href="`/tournaments/${t.id}/`" class="c-stretch">{{ t.title }}</a>
              </h3>
              <p class="c-media__summary">{{ t.description || '上海交大守望先锋赛事' }}</p>
            </article>
          </div>
        </section>

        <!-- 往届赛事 -->
        <section v-if="pastTournaments.length > 0">
          <div class="c-sectionhead">
            <h2>往届赛事</h2>
          </div>
          <table class="c-table c-table--stack">
            <thead>
              <tr>
                <th scope="col">赛事</th>
                <th scope="col">比赛时间</th>
                <th scope="col">赛制模式</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in pastTournaments" :key="t.id" class="relative">
                <td data-label="赛事">
                  <a :href="`/tournaments/${t.id}/`" class="font-semibold hover:text-primary-text">{{ t.title }}</a>
                </td>
                <td data-label="比赛时间" class="font-numeric">{{ t.starts_at?.slice(0, 10) || '已结束' }}</td>
                <td data-label="赛制模式">{{ t.registration_mode === 'team' ? '整队报名' : '个人报名' }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <div v-else class="text-center py-16 text-stone-400">
        <p class="text-lg">暂无赛事</p>
        <p class="text-sm mt-1">赛事发布后会出现在这里。</p>
      </div>
    </div>
  </main>
</template>
