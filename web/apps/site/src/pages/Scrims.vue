<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let scrims: any[] = []
  try {
    const res = await f(`${base}/api/scrims`)
    if (res.ok) {
      const data = await res.json()
      scrims = data.scrims ?? data.items ?? []
    }
  } catch {}

  return {
    title: "内战",
    scrims,
  }
}
</script>
<script setup lang="ts">
import { inject, computed } from "vue"
import { useHead } from "@unhead/vue"
import CSeats from "../components/CSeats.vue"

const data = inject<any>("page-data")
useHead({ title: data?.title ? `${data.title} - SJTU-OW` : "内战 - SJTU-OW" })

const scrims = computed(() => data?.scrims ?? [])
const upcoming = computed(() => scrims.value.filter((s: any) => s.status !== "finished" && s.status !== "cancelled"))
const finished = computed(() => scrims.value.filter((s: any) => s.status === "finished"))
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <div class="l-container l-container--narrow">
        <h1>内战</h1>
        <p class="c-pagehead__lede text-stone-300">社团成员之间的对局。报名后管理员会统一分队，分队结果发到群里。</p>
      </div>
    </header>

    <div class="l-container l-container--narrow pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div v-if="scrims.length > 0" class="grid gap-14">
        <!-- 即将开始的内战 -->
        <section v-if="upcoming.length > 0">
          <div class="c-sectionhead"><h2>即将开始</h2></div>
          <ol class="c-rows">
            <li v-for="scrim in upcoming" :key="scrim.id" class="c-row" data-next-up="scrim">
              <span class="c-date">
                <small>{{ scrim.month || scrim.starts_at?.slice(5, 7) }}月</small>
                <b>{{ scrim.day || scrim.starts_at?.slice(8, 10) }}</b>
              </span>
              <div class="c-row__main">
                <h3 class="c-row__title">
                  <a :href="`/scrims/${scrim.id}/`" class="c-stretch">{{ scrim.title }}</a>
                </h3>
                <p class="c-row__meta">{{ scrim.starts_at?.slice(0, 16) }} · 已报 {{ scrim.count ?? 0 }} / {{ scrim.capacity ?? 10 }}</p>
                <CSeats :taken="scrim.count ?? 0" :total="scrim.capacity ?? 10" />
              </div>
              <span v-if="scrim.signup_open ?? (scrim.status === 'open')" class="c-status c-status--live">报名中</span>
              <span v-else class="c-status">报名已截止</span>
            </li>
          </ol>
        </section>

        <!-- 往期内战 -->
        <section v-if="finished.length > 0">
          <div class="c-sectionhead"><h2>最近结束</h2></div>
          <table class="c-table c-table--stack">
            <thead>
              <tr>
                <th scope="col">内战</th>
                <th scope="col">时间</th>
                <th scope="col">规格</th>
                <th scope="col" class="is-num">报名</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="scrim in finished" :key="scrim.id">
                <td data-label="内战">
                  <a :href="`/scrims/${scrim.id}/`" class="font-semibold hover:text-primary-text">{{ scrim.title }}</a>
                </td>
                <td data-label="时间" class="font-numeric">{{ scrim.starts_at?.slice(0, 16) }}</td>
                <td data-label="规格">{{ scrim.format === 'rq_6v6' ? '6v6 职责预设' : '5v5 职责预设' }}</td>
                <td data-label="报名" class="is-num font-numeric">{{ scrim.count ?? 0 }} 人</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <div v-else class="text-center py-16 text-stone-400">
        <p class="text-lg">暂无内战</p>
        <p class="text-sm mt-1">内战发布后会出现在这里。</p>
      </div>
    </div>
  </main>
</template>
