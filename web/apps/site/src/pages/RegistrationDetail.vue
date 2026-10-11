<script lang="ts">
import type { LoadCtx } from "../router"
import { getApiRegistrationsId as loadRegistration } from "@sjtu-ow/api"
import { httpError } from "../router"
export async function load(ctx:LoadCtx){const page=await loadRegistration(ctx.api,ctx.params.id);if(!page.registration||!page.tournament)throw httpError(404);return{title:page.registration.team_name+" · 报名",page}}
</script>
<script setup lang="ts">
import { computed,inject,reactive,ref } from "vue"
import { useHead } from "@unhead/vue"
import { getApiRegistrationsId,postApiRegistrationsIdWithdraw,postApiRegistrationsIdLeave } from "@sjtu-ow/api"
import type { GetApiRegistrationsIdOut } from "@sjtu-ow/api"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CRegStatus from "@sjtu-ow/ui/CRegStatus.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { requirePageData } from "../personal"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { registrationLabel } from "../registration-display"
import { eventDateTime } from "../event-domain"
import { finishAccountAction } from "../account-form"
type RegistrationPage=Omit<GetApiRegistrationsIdOut,"roster"|"logs">&{
 roster:Array<GetApiRegistrationsIdOut["roster"][number]&{rank_summary?:string}>
 logs:Array<GetApiRegistrationsIdOut["logs"][number]&{action_label?:string;to_status_label?:string}>
}
const data=requirePageData(inject<{page:RegistrationPage}>("page-data"))
const page=reactive(structuredClone(data.page))
const registration=computed(()=>page.registration!)
const tournament=computed(()=>page.tournament!)
const api=useApi()
const confirm=useConfirm()
const refreshError=ref("")
const action=useMutation<{leave:boolean},unknown>((body:{leave:boolean},extras)=>body.leave?postApiRegistrationsIdLeave(api,registration.value.id,extras):postApiRegistrationsIdWithdraw(api,registration.value.id,extras),async()=>{
 if(page.can_leave)return finishAccountAction("/tournaments/"+tournament.value.id+"/")
 try{Object.assign(page,await getApiRegistrationsId(api,registration.value.id));refreshError.value=""}catch(failure){refreshError.value=failure instanceof Error?failure.message:"操作已完成，但页面没有刷新，请重新打开。"}
})
function withdraw():void{if(page.can_withdraw&&confirm("撤回这份报名？"))void action.submit({leave:false})}
function leave():void{if(page.can_leave&&confirm("退出这支临时队伍？"))void action.submit({leave:true})}
useHead(computed(()=>({title:"报名详情 · "+tournament.value.title+" · SJTU-OW",meta:[{name:"robots",content:"noindex"}]})))
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead"><div class="l-container l-container--narrow">
      <nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/me/registrations/">我的报名</a><span class="c-crumbs__sep">/</span><span>报名详情</span></nav>
      <h1><template v-if="registration.team_id===null">{{ registration.team_name }}</template><a v-else :href="'/teams/'+registration.team_id+'/'" class="hover:text-primary-text">{{ registration.team_name }}</a></h1>
      <p class="c-pagehead__meta"><a :href="'/tournaments/'+tournament.id+'/'" class="c-link">{{ tournament.title }}</a><span v-if="registration.team_id===null" class="c-tag">临时队伍</span><CRegStatus :status="registration.status" :label="registrationLabel(registration.status)" /><span v-if="tournament.starts_at" class="font-numeric" data-detail-starts>比赛 {{ eventDateTime(tournament.starts_at) }}</span><span class="font-numeric">名单版本 {{ registration.roster_version }}</span></p>
    </div></header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24"><div class="flex max-w-3xl flex-col gap-12">
      <div class="flex flex-col gap-4">
        <div v-if="page.participant_contact" class="c-notice" data-participant-contact><CIcon name="info" /><p class="c-notice__body">选手联系方式：<span class="font-code">{{ page.participant_contact }}</span></p></div>
        <div v-if="registration.status_note" class="c-notice"><CIcon name="info" /><p class="c-notice__body">审核备注：{{ registration.status_note }}</p></div>
        <div v-if="page.roster_differs&&page.is_captain" class="c-notice c-notice--warn" role="status"><CIcon name="alert" /><p class="c-notice__body">战队成员已发生变化，名单可能需要同步。</p></div>
        <div v-if="page.can_resubmit||page.can_withdraw" class="flex flex-wrap gap-3"><a v-if="page.can_resubmit" :href="'/tournaments/'+tournament.id+'/register/?team='+registration.team_id" class="c-btn c-btn--primary">{{ registration.status==='pending'||registration.status==='approved'?'同步名单':'重新提交' }}</a><form v-if="page.can_withdraw" method="post" @submit.prevent="withdraw"><button type="submit" class="c-btn c-btn--danger" :disabled="!action.canStart.value">撤回报名</button></form></div>
        <p v-else-if="page.is_captain" class="text-sm text-fg-2">报名已截止，不能再修改。</p>
        <form v-else-if="page.can_leave" method="post" class="flex flex-wrap items-center gap-3" @submit.prevent="leave"><button type="submit" class="c-btn c-btn--danger" :disabled="!action.canStart.value">退出队伍</button><span class="text-sm text-fg-2">退出后回到散人池，等赛事管理员重新编队。</span></form>
        <p v-else-if="registration.team_id===null&&(registration.status==='pending'||registration.status==='approved')" class="text-sm text-fg-2">报名已截止，不能再退出。</p>
        <CMutationError :message="action.message.value" :uncertain="action.uncertain.value" :pending="action.pending.value" @retry="action.retry" /><p v-if="refreshError" role="status" class="text-sm text-fg-2">{{ refreshError }}</p>
      </div>
      <section aria-labelledby="reg-roster"><SectionHead title="名单快照" heading-id="reg-roster" /><table class="c-table c-table--stack"><thead><tr><th scope="col">昵称</th><th scope="col">游戏 ID</th><th scope="col">段位（提交时）</th><th scope="col" class="is-num">身份</th></tr></thead><tbody><tr v-for="member in page.roster" :key="member.id"><td data-label="昵称" class="font-semibold">{{ member.nickname }}</td><td data-label="游戏 ID" class="font-code">{{ member.battletag }}</td><td data-label="段位（提交时）" class="text-sm">{{ member.rank_summary }}</td><td data-label="身份" class="is-num"><span v-if="member.is_captain" class="c-tag c-tag--strong">队长</span><span v-if="member.is_sjtu" class="c-tag ml-1">交大</span></td></tr></tbody></table></section>
      <section aria-labelledby="reg-log"><SectionHead title="状态历史" heading-id="reg-log" /><ol class="border-t border-line"><li v-for="entry in page.logs" :key="entry.id" class="grid gap-1 border-b border-line py-3 text-sm sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4"><time :datetime="entry.created_at" class="font-numeric text-fg-3">{{ eventDateTime(entry.created_at) }}</time><span><span class="font-semibold">{{ entry.action_label }}</span><span class="text-fg-2"> → {{ entry.to_status_label || registrationLabel(entry.to_status) }}</span><span v-if="entry.note" class="text-fg-2">（{{ entry.note }}）</span></span></li></ol></section>
    </div></div>
  </main>
</template>
