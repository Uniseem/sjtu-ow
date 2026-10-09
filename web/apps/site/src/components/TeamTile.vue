<script setup lang="ts">
import { computed } from "vue"
import { initial, hue } from "../initial"

const props = defineProps<{
  team: {
    id: number
    name: string
    logo_image_id?: number | null
    member_count: number
    is_recruiting: boolean
    wanted_roles?: string
    created_at_month: string
  }
}>()

const rolesText = computed(() => {
  if (!props.team.wanted_roles) return ""
  return props.team.wanted_roles
    .split(",")
    .map((r) => {
      const trimmed = r.trim()
      if (trimmed === "tank") return "重装"
      if (trimmed === "damage") return "输出"
      if (trimmed === "support") return "支援"
      return trimmed
    })
    .filter(Boolean)
    .join("、")
})
</script>
<template>
  <li class="c-teams__item">
    <span :class="['c-teams__logo', `c-hue-${hue(team.id)}`]">
      <img v-if="team.logo_image_id" :src="`/api/images/${team.logo_image_id}`" alt="" loading="lazy" />
      <template v-else>{{ initial(team.name) }}</template>
    </span>
    <span class="c-teams__body">
      <a :href="`/teams/${team.id}/`" class="c-stretch c-teams__name" :title="team.name">{{ team.name }}</a>
      <span class="c-teams__meta font-numeric">{{ team.member_count }} 人 · {{ team.created_at_month }} 成立</span>
      <span v-if="team.is_recruiting" class="c-teams__status">
        <span class="c-status c-status--live">招募中</span>
        <span v-if="rolesText" class="c-teams__wanted">缺 {{ rolesText }}</span>
      </span>
      <span v-else class="c-teams__status">
        <span class="c-status">暂不招募</span>
      </span>
    </span>
  </li>
</template>
