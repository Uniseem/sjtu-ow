<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiScrimsId as loadScrim,getApiMeProfile } from "@sjtu-ow/api"
import { httpError } from "../router"
export async function load(ctx:LoadCtx){
  const viewer=await ctx.viewer()
  const [page,profile]=await Promise.all([loadScrim(ctx.api,ctx.params.id),viewer.user?getApiMeProfile(ctx.api):Promise.resolve(null)])
  if(!page.scrim)throw httpError(404)
  return{title:page.scrim.title,page,accounts:profile?.game_accounts||[]}
}
</script>
<script setup lang="ts">
import { computed,inject,reactive,ref } from "vue"
import { useHead } from "@unhead/vue"
import { getApiScrimsId } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import CSeats from "@sjtu-ow/ui/CSeats.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import ScrimActions from "../components/ScrimActions.vue"
import { useApi } from "../api"
import { requirePageData } from "../personal"
import { eventCover,eventShortTime,eventDateTime,type ScrimPage } from "../event-domain"
const data=requirePageData(inject<{page:ScrimPage;accounts:Array<{id:number;battletag:string}>}>("page-data"))
const page=reactive(structuredClone(data.page))
const scrim=computed(()=>page.scrim!)
const status=computed(()=>page.card.status==='cancelled'?'已取消':page.card.status==='finished'?'已结束':page.card.signup_open?'报名中':'报名已截止')
const api=useApi()
const error=ref("")
useHead(computed(()=>({title:scrim.value.title+" · 内战 · SJTU-OW"})))
async function refresh():Promise<void>{try{Object.assign(page,await getApiScrimsId(api,scrim.value.id));error.value=""}catch(failure){error.value=failure instanceof Error?failure.message:"操作已完成，但页面未能刷新。"}}
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-stage">
      <img class="c-stage__img" :src="eventCover(scrim.id,'scrim',page.default_cover_image_id)" width="2400" height="900" alt="">
      <div class="l-container l-container--narrow c-stage__body">
        <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/scrims/">内战</a><span class="c-crumbs__sep">/</span><span>{{ scrim.title }}</span></nav>
        <p class="c-stage__tags"><span :class="['c-status',{'c-status--live':page.card.signup_open}]">{{ status }}</span><span class="c-tag">{{ page.card.format_label }}</span><span v-if="scrim.sjtu_only" class="c-tag">仅限交大</span></p>
        <h1 class="c-stage__title">{{ scrim.title }}</h1>
        <dl class="c-stage__facts"><div><dt>开始</dt><dd><time :datetime="scrim.starts_at || undefined">{{ eventShortTime(scrim.starts_at) }}</time></dd></div><div><dt>报名截止</dt><dd>{{ eventShortTime(page.card.signup_deadline,false) }}</dd></div><div><dt>已报名</dt><dd>{{ page.counts.total }} / {{ page.card.players_needed }} 人</dd></div></dl>
        <CSeats :taken="page.counts.total" :total="page.card.players_needed" extra="c-stage__meter" />
      </div>
    </header>
    <div class="l-container l-container--narrow l-section">
      <div v-if="scrim.status==='cancelled'" class="c-notice c-notice--warn mb-10" role="status"><CIcon name="alert" /><div class="c-notice__body">这场内战已取消。</div></div>
      <p v-if="error" class="c-notice c-notice--warn" role="status">{{ error }}</p>
      <div class="l-split"><div class="flex min-w-0 flex-col gap-12">
        <section class="c-panel" aria-label="报名"><ScrimActions :page="page"  :group-url="page.group_url" :accounts="data.accounts" @changed="refresh" /></section>
        <section v-if="page.body_html" aria-labelledby="s-about"><SectionHead title="说明" heading-id="s-about" /><div class="c-prose l-prose" v-html="page.body_html" /></section>
        <section aria-labelledby="s-signups"><SectionHead title="报名情况" heading-id="s-signups" />
          <dl class="c-rolestats"><div><dt><CIcon name="role-tank" class="size-5" />坦克</dt><dd>{{ page.counts.tank }}</dd></div><div><dt><CIcon name="role-damage" class="size-5" />输出</dt><dd>{{ page.counts.damage }}</dd></div><div><dt><CIcon name="role-support" class="size-5" />支援</dt><dd>{{ page.counts.support }}</dd></div></dl>
          <p class="mt-3 text-fg-2">共 {{ page.counts.total }} 人，一个人可以报多个位置。</p>
          <table v-if="page.signups.length" class="c-table mt-6"><thead><tr><th scope="col" class="w-12">序号</th><th scope="col">昵称</th><th scope="col">能打的位置</th></tr></thead><tbody><tr v-for="(signup,index) in page.signups" :key="index"><td class="font-numeric text-fg-3">{{ String(index+1).padStart(2,'0') }}</td><td class="font-semibold">{{ signup.nickname }}</td><td><CRoleIcon :tank="signup.roles.includes('tank')" :damage="signup.roles.includes('damage')" :support="signup.roles.includes('support')" /></td></tr></tbody></table><p v-else class="mt-6 text-fg-2">还没有人报名。</p>
        </section>
      </div><aside><dl class="c-facts c-panel"><dt>开始</dt><dd class="font-numeric">{{ eventDateTime(scrim.starts_at,true) }}</dd><dt>报名截止</dt><dd class="font-numeric">{{ eventDateTime(page.card.signup_deadline) }}</dd><dt>规格</dt><dd>{{ page.card.format_label }}</dd><dt>参加条件</dt><dd>{{ scrim.sjtu_only?'仅限交大':'不限学校' }}</dd><dt>分队</dt><dd>管理员用系统自动分队，结果发到群里</dd></dl></aside></div>
    </div>
  </main>
</template>
