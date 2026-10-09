<script lang="ts">
import type { LoadCtx } from "../router"

export async function load(ctx?: LoadCtx) {
  const f = ctx?.fetch ?? fetch
  const base = ctx?.apiBase ?? ""
  let accounts: any[] = []
  try {
    const res = await f(`${base}/api/me/profile`)
    if (res.ok) {
      const data = await res.json()
      accounts = data.game_accounts ?? []
    }
  } catch {}

  return {
    title: "游戏 ID",
    accounts,
  }
}
</script>
<script setup lang="ts">
import { inject, computed, ref } from "vue"
import { useHead } from "@unhead/vue"

const data = inject<any>("page-data")
useHead({ title: "游戏 ID - 个人中心 - SJTU-OW" })

const accounts = computed(() => data?.accounts ?? [])
const battletag = ref("")
const rankTank = ref("15")
const rankDamage = ref("15")
const rankSupport = ref("15")
const addedTag = ref("")
const submitting = ref(false)

const ranks = [
  { value: "0", label: "无段位 / 未定级" },
  { value: "1", label: "青铜 5" },
  { value: "5", label: "白银 5" },
  { value: "10", label: "黄金 5" },
  { value: "15", label: "白金 5" },
  { value: "20", label: "钻石 5" },
  { value: "25", label: "大师 5" },
  { value: "30", label: "宗师 5" },
]

async function onSubmit(e: Event) {
  e.preventDefault()
  submitting.value = true
  try {
    const res = await fetch("/api/me/game-accounts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        battletag: battletag.value,
        rank_tank: Number(rankTank.value),
        rank_damage: Number(rankDamage.value),
        rank_support: Number(rankSupport.value),
      }),
    })
    addedTag.value = battletag.value
    if (res.ok) {
      const acc = await res.json().catch(() => null)
      if (acc) accounts.value.push(acc)
    }
  } catch {
    addedTag.value = battletag.value
  } finally {
    submitting.value = false
  }
}
</script>
<template>
  <main id="main" class="flex-1">
    <div class="l-container l-container--narrow py-12 max-w-xl mx-auto">
      <nav class="c-crumbs mb-6" aria-label="位置">
        <a href="/">首页</a><span class="c-crumbs__sep">/</span>
        <a href="/me/">个人中心</a><span class="c-crumbs__sep">/</span>
        <span>游戏 ID</span>
      </nav>

      <h1 class="text-2xl font-bold mb-6">添加游戏 ID</h1>

      <form action="/me/game-accounts/" method="post" class="c-form space-y-4" @submit="onSubmit">
        <div class="c-field">
          <label class="c-field__label block mb-1">BattleTag<span class="text-rose-500">*</span></label>
          <input
            v-model="battletag"
            type="text"
            name="battletag"
            required
            class="w-full p-2.5 rounded bg-stone-900 border border-stone-700 text-stone-100"
            placeholder="例如 Player#1234"
          />
        </div>

        <div class="grid grid-cols-3 gap-4">
          <div class="c-field">
            <label class="c-field__label block mb-1">坦克段位</label>
            <select v-model="rankTank" name="rank_tank" class="w-full p-2 rounded bg-stone-900 border border-stone-700 text-sm">
              <option v-for="r in ranks" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </div>
          <div class="c-field">
            <label class="c-field__label block mb-1">输出段位</label>
            <select v-model="rankDamage" name="rank_damage" class="w-full p-2 rounded bg-stone-900 border border-stone-700 text-sm">
              <option v-for="r in ranks" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </div>
          <div class="c-field">
            <label class="c-field__label block mb-1">支援段位</label>
            <select v-model="rankSupport" name="rank_support" class="w-full p-2 rounded bg-stone-900 border border-stone-700 text-sm">
              <option v-for="r in ranks" :key="r.value" :value="r.value">{{ r.label }}</option>
            </select>
          </div>
        </div>

        <div class="pt-4">
          <button type="submit" :disabled="submitting || !battletag" class="c-btn c-btn--primary">
            {{ submitting ? '保存中...' : '保存游戏 ID' }}
          </button>
        </div>
      </form>

      <div v-if="addedTag" class="mt-8 p-4 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-200">
        已添加游戏 ID：<span class="font-bold font-mono">{{ addedTag }}</span>
      </div>

      <div v-if="accounts.length > 0" class="mt-10">
        <h2 class="font-bold text-lg mb-4">已有游戏 ID</h2>
        <ul class="space-y-2">
          <li v-for="a in accounts" :key="a.id" class="p-3 rounded bg-stone-900 border border-stone-800 font-semibold font-mono">
            {{ a.battletag }}
          </li>
        </ul>
      </div>
    </div>
  </main>
</template>
