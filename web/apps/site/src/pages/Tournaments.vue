<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiTournaments } from "@sjtu-ow/api"
export async function load(ctx: LoadCtx) { return { title: "赛事", list: await getApiTournaments(ctx.api) } }
</script>
<script setup lang="ts">
import { computed, inject } from "vue"
import { useHead } from "@unhead/vue"
import CPagehead from "@sjtu-ow/ui/CPagehead.vue"
import CTournamentCard from "@sjtu-ow/ui/CTournamentCard.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import { requirePageData } from "../personal"
import { eventDate, type TournamentList } from "../event-domain"
const data=requirePageData(inject<{ list: TournamentList }>("page-data"))
const groups=computed(()=>data.list.groups.filter(group=>group.tournaments.length))
// The legacy sparse approved-count lookup omits the suffix for an absent group.
// Its table uses zero; the picture card passes no approved value in that case.
function cardApproved(count:number):number|null { return count > 0 ? count : null }
useHead({title:"赛事 · SJTU-OW"})
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead c-pagehead--picture">
      <CPagehead section="tournaments" :image-id="data.list.banner_image_id" />
      <div class="l-container"><h1>赛事</h1><p class="c-pagehead__lede">社团自己办的比赛。一般是每人自己报名，由赛事组编成队伍；标着「整队报名」的，由队长为整支战队报名。</p></div>
    </header>
    <div class="l-container pt-10 pb-16 lg:pt-14 lg:pb-24">
      <div class="grid gap-14">
        <section v-for="group in groups" :key="group.phase" :aria-labelledby="'phase-' + group.phase" :data-phase="group.phase">
          <div class="c-sectionhead"><h2 :id="'phase-' + group.phase">{{ group.label }}</h2></div>
          <div v-if="group.phase === 'open' || group.phase === 'upcoming'" class="c-media-grid c-media-grid--3"><CTournamentCard v-for="tournament in group.tournaments" :key="tournament.id" :tournament="tournament" :approved="cardApproved(tournament.approved_count)" /></div>
          <table v-else class="c-table c-table--stack">
            <thead><tr><th scope="col">赛事</th><th scope="col">比赛时间</th><th scope="col">人数</th><th scope="col" class="is-num">已通过</th></tr></thead>
            <tbody><tr v-for="tournament in group.tournaments" :key="tournament.id" class="relative"><td data-label="赛事"><a :href="'/tournaments/' + tournament.id + '/'" class="font-semibold hover:text-primary-text">{{ tournament.title }}</a></td><td data-label="比赛时间" class="font-numeric">{{ eventDate(tournament.starts_at) }}</td><td data-label="人数" class="font-numeric">{{ tournament.roster_min }}–{{ tournament.roster_max }} 人</td><td data-label="已通过" class="is-num font-numeric">{{ tournament.approved_count }} 队</td></tr></tbody>
          </table>
        </section>
        <CEmpty v-if="!groups.length" title="暂无赛事" message="赛事发布后会出现在这里。" />
      </div>
    </div>
  </main>
</template>
