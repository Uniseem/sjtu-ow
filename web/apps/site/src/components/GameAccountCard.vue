<script setup lang="ts">
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CRank from "@sjtu-ow/ui/CRank.vue"
import { PLAY_ROLES } from "../personal"
import type { GameAccount } from "../pending-api"

defineProps<{ account: GameAccount; pending?: boolean }>()
defineEmits<{ remove: [id: number] }>()

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
      <slot name="updated" />
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
