<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiTournamentsId as loadTournamentPage } from "@sjtu-ow/api"
import { requireTournament as loadedTournament } from "../event-domain"
export async function load(ctx:LoadCtx){const page=await loadTournamentPage(ctx.api,ctx.params.id);return{title:loadedTournament(page.tournament).title,page}}
</script>
<script setup lang="ts">
import { computed, inject, reactive, ref } from "vue"
import { useHead } from "@unhead/vue"
import { getApiTournamentsId } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import TournamentActions from "../components/TournamentActions.vue"
import { requirePageData } from "../personal"
import { useApi } from "../api"
import { eventCover,eventDate,eventDateTime,eventShortTime,requireTournament,modeLabel,modeSummary,type TournamentPage } from "../event-domain"
const data=requirePageData(inject<{page:TournamentPage}>("page-data"))
const page=reactive(structuredClone(data.page))
const tournament=computed(()=>requireTournament(page.tournament))
const api=useApi()
const error=ref("")
useHead(computed(()=>({title:tournament.value.title+" · 赛事 · SJTU-OW"})))
async function refresh():Promise<void>{try{Object.assign(page,await getApiTournamentsId(api,tournament.value.id));error.value=""}catch(failure){error.value=failure instanceof Error?failure.message:"操作已完成，但页面未能刷新。"}}
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-stage">
      <img class="c-stage__img" :src="eventCover(tournament.id,'tournament',tournament.cover_image_id || page.default_cover_image_id)" width="2400" height="900" alt="">
      <div class="l-container l-container--narrow c-stage__body">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/tournaments/">赛事</a><span class="c-crumbs__sep">/</span><span>{{ tournament.title }}</span></nav>
        <p class="c-stage__tags"><span :class="['c-status',{'c-status--live':page.phase==='open','c-status--info':page.phase==='upcoming'}]">{{ page.phase_label }}</span><span v-if="tournament.sjtu_only" class="c-tag">仅限交大</span><span class="c-tag" data-mode-tag>{{ modeLabel(tournament.registration_mode) }}</span></p>
        <h1 class="c-stage__title">{{ tournament.title }}</h1>
        <p v-if="tournament.summary" class="c-stage__lede">{{ tournament.summary }}</p>
        <dl class="c-stage__facts" data-key-facts><div><dt>报名截止</dt><dd>{{ eventShortTime(tournament.registration_closes_at) }}</dd></div><div><dt>比赛时间</dt><dd>{{ eventShortTime(tournament.starts_at) }}</dd></div><div><dt>每队人数</dt><dd>{{ tournament.roster_min }}–{{ tournament.roster_max }} 人</dd></div><div v-if="tournament.registration_mode==='individual'"><dt>等待编队</dt><dd>{{ page.pool?.total || 0 }} 人</dd></div><div><dt>{{ tournament.registration_mode==='individual'?'已编成':'已通过' }}</dt><dd>{{ page.approved_teams.length }} 队</dd></div></dl>
      </div>
    </header>
    <div class="l-container l-container--narrow l-section">
      <div v-if="tournament.status==='cancelled'" class="c-notice c-notice--warn mb-10" role="status"><CIcon name="alert" /><div class="c-notice__body">这项赛事已取消。</div></div>
      <p v-if="error" class="c-notice c-notice--warn" role="status">{{ error }}</p>
      <div class="l-split"><div class="flex min-w-0 flex-col gap-12">
        <section class="c-panel" aria-label="报名"><TournamentActions :page="page" @changed="refresh" /></section>
        <section v-if="page.body_html" aria-labelledby="t-rules"><SectionHead title="赛事说明" heading-id="t-rules" /><div class="c-prose l-prose" v-html="page.body_html" /></section>
        <section aria-labelledby="t-teams"><SectionHead :title="tournament.registration_mode==='individual'?'已编成的队伍':'已通过的战队'" heading-id="t-teams" />
          <table v-if="page.approved_teams.length" class="c-table"><thead><tr><th scope="col" class="w-12">序号</th><th scope="col">队伍</th><th scope="col" class="is-num">人数</th></tr></thead><tbody><tr v-for="(entry,index) in page.approved_teams" :key="entry.registration_id"><td class="font-numeric text-fg-3">{{ String(index+1).padStart(2,'0') }}</td><td><template v-if="entry.is_adhoc"><span class="font-semibold">{{ entry.team_name }}</span><span class="c-tag ml-2">临时队伍</span></template><a v-else :href="'/teams/' + entry.team_id + '/'" class="font-semibold hover:text-primary-text">{{ entry.team_name }}</a></td><td class="is-num font-numeric">{{ entry.member_count }} 人</td></tr></tbody></table>
          <p v-else class="text-fg-2">{{ tournament.registration_mode==='individual'?'还没有编队。':'暂时还没有通过审核的战队。' }}</p>
        </section>
        <section v-if="page.pool && tournament.registration_mode==='individual'" aria-labelledby="t-pool"><SectionHead title="等待编队" heading-id="t-pool" /><p class="text-fg-2">共 {{ page.pool.total }} 人：坦克 {{ page.pool.tank }}、输出 {{ page.pool.damage }}、支援 {{ page.pool.support }}</p>
          <ul v-if="page.pool.entries.length" class="c-roster mt-4" data-pool><li v-for="entry in page.pool.entries" :key="entry.signup_id" class="c-roster__item"><CAvatar :person="{id:entry.user_id,nickname:entry.nickname}" size="md" /><span class="min-w-0"><span class="c-roster__name" :title="entry.nickname">{{ entry.nickname }}</span><span class="mt-1.5 block"><CRoleIcon :tank="entry.roles.includes('tank')" :damage="entry.roles.includes('damage')" :support="entry.roles.includes('support')" /></span></span></li></ul><p v-else class="mt-4 text-fg-2">还没有人个人报名。</p>
        </section>
      </div><aside class="flex flex-col gap-10">
        <dl class="c-facts c-panel"><dt>报名开放</dt><dd class="font-numeric">{{ eventDateTime(tournament.registration_opens_at) }}</dd><dt>报名截止</dt><dd class="font-numeric">{{ eventDateTime(tournament.registration_closes_at) }}</dd><dt>比赛时间</dt><dd class="font-numeric">{{ eventDateTime(tournament.starts_at) }}</dd><dt>每队人数</dt><dd>{{ tournament.roster_min }}–{{ tournament.roster_max }} 人</dd><dt>报名方式</dt><dd data-mode>{{ modeLabel(tournament.registration_mode) }}<span class="block text-fg-2">{{ modeSummary(tournament.registration_mode) }}</span></dd><dt>参赛条件</dt><dd>{{ tournament.sjtu_only?'仅限交大':'不限学校' }}</dd></dl>
        <section v-if="page.articles?.length" aria-labelledby="t-articles"><div class="c-sectionhead"><h2 id="t-articles">相关文章</h2></div><ol class="c-rows"><li v-for="article in page.articles" :key="article.id" class="c-row c-row--plain"><div class="c-row__main"><h3 class="c-row__title"><a :href="'/news/' + article.slug + '/'" class="c-stretch">{{ article.title }}</a></h3><p v-if="article.first_published_at" class="c-row__meta"><time :datetime="article.first_published_at">{{ eventDate(article.first_published_at) }}</time></p></div></li></ol></section>
      </aside></div>
    </div>
  </main>
</template>
