<script setup lang="ts">
import { imageUrl } from "@sjtu-ow/shared/media"
import { initial, hue } from "@sjtu-ow/shared/initial"
import { shanghaiParts } from "@sjtu-ow/shared/time"
withDefaults(defineProps<{
  team: { id: number; name: string; logo_image_id?: number | null; description?: string; member_count: number; is_recruiting: boolean; wanted_roles?: string[] | string; created_at?: string; created_at_month?: string }
  capacity?: number; members?: number; about?: boolean; showClosed?: boolean
}>(), { showClosed: false })
const labels: Record<string, string> = { tank: "坦克", damage: "输出", support: "支援" }
function wanted(roles: string[] | string = []): string {
  return (Array.isArray(roles) ? roles : roles.split(',')).map((r) => labels[r.trim()] ?? r.trim()).filter(Boolean).join('、')
}
function month(date: string): string {
  const p = shanghaiParts(new Date(date))
  return `${p.year}.${p.month}`
}
</script>
<template>
  <li class="c-teams__item">
    <span :class="`c-teams__logo c-hue-${hue(team.id)}`"><img v-if="team.logo_image_id" :src="imageUrl(team.logo_image_id, 'fill-400x400')" alt="" loading="lazy"><template v-else>{{ initial(team.name) }}</template></span>
    <span class="c-teams__body">
      <a :href="`/teams/${team.id}/`" class="c-stretch c-teams__name" :title="team.name">{{ team.name }}</a>
      <span class="c-teams__meta font-numeric">{{ members || team.member_count }}<template v-if="capacity"> / {{ capacity }}</template> 人<template v-if="team.created_at_month || team.created_at"> · {{ team.created_at_month || month(team.created_at!) }} 成立</template></span>
      <span v-if="about && team.description" class="c-teams__about">{{ team.description }}</span>
      <span v-if="team.is_recruiting" class="c-teams__status"><span class="c-status c-status--live">招募中</span><span v-if="wanted(team.wanted_roles)" class="c-teams__wanted">缺 {{ wanted(team.wanted_roles) }}</span></span>
      <span v-else-if="showClosed" class="c-teams__status"><span class="c-status">暂不招募</span></span>
    </span>
  </li>
</template>
