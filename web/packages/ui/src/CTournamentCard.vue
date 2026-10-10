<script setup lang="ts">
import { coverPlaceholder } from "@sjtu-ow/shared/pictures"
import { imageUrl } from "@sjtu-ow/shared/media"
import { owDate, owMd, owTime } from "@sjtu-ow/shared/time"
defineProps<{
  tournament: { id: number; title: string; phase: string; starts_at?: string | null; registration_closes_at?: string | null; registration_opens_at?: string | null; cover_image_id?: number | null; default_cover_image_id?: number | null; roster_min: number; roster_max: number; registration_mode_label: string; takes_individuals: boolean; sjtu_only: boolean }
  approved?: number | null
}>()
function md(value?: string | null): string { return value ? owMd(new Date(value)) : '' }
function time(value?: string | null): string { return value ? owTime(new Date(value)) : '' }
</script>
<template>
  <article class="c-media" data-tournament-card>
    <div class="c-media__pic">
      <img v-if="tournament.cover_image_id" :src="imageUrl(tournament.cover_image_id, 'fill-960x540')" alt="" loading="lazy">
      <img v-else-if="tournament.default_cover_image_id" :src="imageUrl(tournament.default_cover_image_id, 'fill-960x540')" width="960" height="540" :class="`c-drift c-drift--${tournament.id % 4 + 1}`" loading="lazy" alt="">
      <img v-else :src="coverPlaceholder(tournament.id, 'tournament')" width="960" height="540" loading="lazy" alt="">
    </div>
    <p class="c-media__meta">
      <template v-if="tournament.phase === 'open'"><span class="c-status c-status--live">报名中</span><span>{{ md(tournament.registration_closes_at) }} {{ time(tournament.registration_closes_at) }} 截止</span><span v-if="tournament.starts_at" data-card-starts>{{ md(tournament.starts_at) }} 比赛</span></template>
      <template v-else-if="tournament.phase === 'upcoming'"><span class="c-status c-status--info">即将开始报名</span><span>{{ md(tournament.registration_opens_at) }} {{ time(tournament.registration_opens_at) }} 开放</span><span v-if="tournament.starts_at" data-card-starts>{{ md(tournament.starts_at) }} 比赛</span></template>
      <span v-else-if="tournament.phase === 'cancelled'" class="c-status">已取消</span>
      <template v-else-if="tournament.phase === 'finished'"><span class="c-status">已结束</span><span v-if="tournament.starts_at">{{ owDate(new Date(tournament.starts_at)) }}</span></template>
      <template v-else><span class="c-status">报名已截止</span><span v-if="tournament.starts_at">{{ md(tournament.starts_at) }} 比赛</span></template>
    </p>
    <h3 class="c-media__title"><a :href="`/tournaments/${tournament.id}/`" class="c-stretch">{{ tournament.title }}</a></h3>
    <p class="c-media__facts">{{ tournament.registration_mode_label }} · {{ tournament.roster_min }}–{{ tournament.roster_max }} 人一队<template v-if="approved != null"> · {{ tournament.takes_individuals ? '已编成' : '已通过' }} {{ approved }} 队</template><template v-if="tournament.sjtu_only"> · 仅限交大</template></p>
  </article>
</template>
