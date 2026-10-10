<script setup lang="ts">
import { owMonthNum, owDay, owWeekday, owTime } from "@sjtu-ow/shared/time"
import CSeats from "./CSeats.vue"
defineProps<{ scrim: { id: number; title: string; starts_at: string; format_label: string; status: string; signup_open: boolean; players_needed: number }; signups?: number; href?: string }>()
</script>
<template>
  <li class="c-row" :id="`scrim-${scrim.id}`" data-scrim-row>
    <span class="c-date"><small>{{ owMonthNum(new Date(scrim.starts_at)) }}月</small><b>{{ owDay(new Date(scrim.starts_at)) }}</b></span>
    <div class="c-row__main">
      <h3 class="c-row__title"><a :href="href ?? `/scrims/${scrim.id}/`" class="c-stretch">{{ scrim.title }}</a></h3>
      <p class="c-row__meta">{{ owWeekday(new Date(scrim.starts_at)) }} {{ owTime(new Date(scrim.starts_at)) }} · {{ scrim.format_label }} · 已报 {{ signups ?? 0 }} / {{ scrim.players_needed }}</p>
      <CSeats :taken="signups ?? 0" :total="scrim.players_needed" />
    </div>
    <span v-if="scrim.status === 'cancelled'" class="c-status">已取消</span>
    <span v-else-if="scrim.status === 'finished'" class="c-status">已结束</span>
    <span v-else-if="scrim.signup_open" class="c-status c-status--live">报名中</span>
    <span v-else class="c-status">报名已截止</span>
  </li>
</template>
