<script setup lang="ts">
import CIcon from "./CIcon.vue"
import CRank from "./CRank.vue"
import { owDate } from "@sjtu-ow/shared/time"
import type { PublicPlay } from "./types"
defineProps<{ profile: PublicPlay; compact?: boolean }>()
function rankTitle(rank: NonNullable<PublicPlay['main_rank']>): string {
  return `${rank.role_label}段位${rank.updated_at ? '，更新于 ' + owDate(new Date(rank.updated_at)) : ''}`
}
</script>
<template>
  <span v-if="profile.roles.length || profile.main_rank" class="c-play">
    <template v-if="profile.is_flex && !compact">
      <template v-for="role in profile.roles" :key="role.code"><span v-if="role.main" class="c-role c-role--main"><CIcon :name="`role-${role.code}`" class="size-3.5" />{{ role.label }}</span></template>
      <span class="c-role">全能</span>
    </template>
    <template v-else>
      <template v-for="(role, i) in profile.roles" :key="role.code"><span v-if="!compact || i === 0" :class="['c-role', { 'c-role--main': role.main }]"><CIcon :name="`role-${role.code}`" class="size-3.5" />{{ role.label }}</span></template>
    </template>
    <span v-if="profile.main_rank" :class="['c-play__rank', { 'is-stale': profile.main_rank.stale }]" :title="rankTitle(profile.main_rank)"><CRank :label="profile.main_rank.label" /></span>
  </span>
</template>
