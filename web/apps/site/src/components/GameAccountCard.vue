<script setup lang="ts">
import { computed, inject } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CRank from "@sjtu-ow/ui/CRank.vue"
import { PLAY_ROLES } from "../personal"
import type { GameAccount } from "../pending-api"

const props = defineProps<{ account: GameAccount; pending?: boolean }>()
const page = inject<{ renderedAt?: number }>("page-data", {})
defineEmits<{ remove: [id: number] }>()


// The loader serializes one reference instant for SSR and its hydration. Match
// Django's timesince calendar-month pivot and its two adjacent Chinese units.
const updated = computed(() => {
  if (typeof page.renderedAt !== "number" || !Number.isFinite(page.renderedAt)) return null
  const then = new Date(props.account.ranks_updated_at)
  const now = new Date(page.renderedAt)
  if (!Number.isFinite(then.getTime())) return null
  if (Math.floor((now.getTime() - then.getTime()) / 1000) <= 0) return "0 分钟"
  let totalMonths = (now.getUTCFullYear() - then.getUTCFullYear()) * 12 + now.getUTCMonth() - then.getUTCMonth()
  const thenTime = then.getUTCHours() * 3600000 + then.getUTCMinutes() * 60000 + then.getUTCSeconds() * 1000 + then.getUTCMilliseconds()
  const nowTime = now.getUTCHours() * 3600000 + now.getUTCMinutes() * 60000 + now.getUTCSeconds() * 1000 + now.getUTCMilliseconds()
  if (then.getUTCDate() > now.getUTCDate() || then.getUTCDate() === now.getUTCDate() && thenTime > nowTime) totalMonths--
  const years = Math.floor(totalMonths / 12)
  const months = totalMonths % 12
  let pivot = then.getTime()
  if (years || months) {
    const shifted = then.getUTCMonth() + months
    const year = then.getUTCFullYear() + years + Math.floor(shifted / 12)
    const month = shifted % 12
    const monthDays = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    pivot = Date.UTC(year, month, Math.min(monthDays[month], then.getUTCDate()), then.getUTCHours(), then.getUTCMinutes(), then.getUTCSeconds())
  }
  let remaining = (now.getTime() - pivot) / 1000
  const counts = [years, months]
  for (const seconds of [604800, 86400, 3600, 60]) {
    const count = Math.floor(remaining / seconds)
    counts.push(count)
    remaining -= count * seconds
  }
  const first = counts.findIndex(count => count !== 0)
  if (first < 0) return "0 分钟"
  const units = ["年", "月", "周", "日", "小时", "分钟"]
  const parts: string[] = []
  for (let index = first; index < counts.length && parts.length < 2 && counts[index] !== 0; index++) parts.push(`${counts[index]} ${units[index]}`)
  return parts.join("，")
})

const labels = {
  tank: "tank_label",
  damage: "damage_label",
  support: "support_label",
} as const
</script>

<template>
  <article :id="'game-account-' + account.id" class="c-panel" data-game-account>
    <div class="c-panel__head">
      <h2 class="font-code text-lg">{{ account.battletag }}</h2>
      <slot name="updated"><p v-if="updated !== null" class="text-sm text-fg-3">段位更新于 {{ updated }}前</p></slot>
    </div>
    <dl class="mt-4 grid grid-cols-3 border-y border-line">
      <div
        v-for="(role, index) in PLAY_ROLES"
        :key="role.value"
        :class="index === 0 ? 'py-3 pr-3' : 'border-l border-line py-3 pl-3'"
      >
        <dt class="inline-flex items-center gap-1.5 text-sm text-fg-2">
          <CIcon :name="role.icon" class="size-4" />{{ role.label }}
        </dt>
        <dd class="mt-1"><CRank :label="account[labels[role.value]]" /></dd>
      </div>
    </dl>
    <div class="c-panel__actions">
      <a :href="'/me/game-accounts/' + account.id + '/'" class="c-btn c-btn--secondary c-btn--sm">
        <CIcon name="edit" />编辑
      </a>
      <form
        method="post"
        :action="'/me/game-accounts/' + account.id + '/delete/'"
        @submit.prevent="$emit('remove', account.id)"
      >
        <button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="pending">
          <CIcon name="trash" />删除
        </button>
      </form>
    </div>
  </article>
</template>
