<script lang="ts">
import type { LoadCtx } from "../router"
import { getRegisterForm } from "../registration-form"
import { requireTournament as loadedTournament } from "../event-domain"
export async function load(ctx:LoadCtx){const selected=Number(ctx.query.team);const form=await getRegisterForm(ctx.api,ctx.params.id,Number.isSafeInteger(selected)&&selected>0?selected:undefined);return{title:"为战队报名 · "+loadedTournament(form.tournament).title,form}}
</script>
<script setup lang="ts">
import { computed,inject,ref,watch } from "vue"
import { useHead } from "@unhead/vue"

import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { requirePageData } from "../personal"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { finishAccountAction } from "../account-form"
import { requireTournament,eventDateTime } from "../event-domain"
import { selectedAccounts,safeRosterSelection,submitRegisterForm,type RegisterForm } from "../registration-form"
import { registrationLabel } from "../registration-display"
const data=requirePageData(inject<{form:RegisterForm}>("page-data"))
const form=computed(()=>data.form)
const tournament=computed(()=>requireTournament(form.value.tournament))
// The legacy registration form orders members before the captain, keeping
// the API membership order (join time) within each group.
const displayRows=computed(()=>[...form.value.rows].sort((a,b)=>Number(a.is_captain)-Number(b.is_captain)))
const selectedTeam=ref(form.value.team?.id||null)
const accounts=ref(selectedAccounts(form.value.rows))
const api=useApi()
const submit=useMutation((body:{team_id:number;accounts:Record<string,number>;base_team_version:number;base_roster_version:number},extras)=>submitRegisterForm(api,tournament.value.id,body,extras),result=>{
 if(!result.registration)throw new Error("报名结果无效，请重新打开我的报名确认。")
 return finishAccountAction("/registrations/"+result.registration.id+"/")
})
watch(()=>data.form,next=>{selectedTeam.value=next.team?.id||null;accounts.value=selectedAccounts(next.rows);submit.clear()})
useHead(computed(()=>({title:"为战队报名 · "+tournament.value.title+" · SJTU-OW",meta:[{name:"robots",content:"noindex"}]})))
function send():void{if(form.value.can_submit&&form.value.team)void submit.submit({team_id:form.value.team.id,accounts:safeRosterSelection(form.value.rows,accounts.value),base_team_version:form.value.team.version,base_roster_version:form.value.existing?.roster_version||0})}
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead"><div class="l-container l-container--narrow"><nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/tournaments/">赛事</a><span class="c-crumbs__sep">/</span><a :href="'/tournaments/' + tournament.id + '/'">{{ tournament.title }}</a><span class="c-crumbs__sep">/</span><span>为战队报名</span></nav><h1>为战队报名</h1><p class="c-pagehead__meta"><span>{{ tournament.title }}</span><span>每队 <span class="font-numeric">{{ tournament.roster_min }}–{{ tournament.roster_max }}</span> 人</span><span>报名截止 <span class="font-numeric">{{ eventDateTime(tournament.registration_closes_at) }}</span></span></p></div></header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24"><div class="flex max-w-3xl flex-col gap-8">
      <form v-if="form.teams.length>1" method="get" class="flex flex-wrap items-end gap-3"><div class="c-field min-w-[14rem] flex-1"><label class="c-field__label" for="register-team">选择战队</label><select id="register-team" v-model="selectedTeam" name="team"><option v-for="team in form.teams" :key="team.id" :value="team.id">{{ team.name }}</option></select></div><button type="submit" class="c-btn c-btn--secondary">切换</button></form>
      <div v-if="form.problems.length" class="c-notice c-notice--error" role="alert"><CIcon name="x-circle" /><div class="c-notice__body"><p class="font-semibold">下面的问题需要先解决：</p><ul class="mt-1 list-[square] pl-5"><li v-for="(problem,index) in form.problems" :key="index">{{ problem }}</li></ul></div></div>
      <div v-if="form.existing" class="c-notice c-notice--info"><CIcon name="info" /><p class="c-notice__body">这支战队已经报名过（状态：{{ registrationLabel(form.existing.status) }}，名单版本 {{ form.existing.roster_version }}）。{{ " " }}再次提交会同步为当前名单{{ tournament.auto_approve?'并自动通过':'并重新审核' }}。{{ " " }}<a :href="'/registrations/' + form.existing.id + '/'">查看报名</a></p></div>
      <form v-if="form.team" method="post" class="c-form" :aria-busy="submit.pending.value||undefined" @submit.prevent="send">
        <CMutationError :message="submit.message.value" :uncertain="submit.uncertain.value" :pending="submit.pending.value" @retry="submit.retry" />
        <div class="c-step"><div class="c-step__head"><h2 class="text-lg">「{{ form.team.name }}」的名单</h2></div><p class="text-sm text-fg-2" data-no-confirm>整支战队一起报名：提交后全队 {{ form.rows.length }} 人直接进入名单，<strong class="text-fg">不需要队员确认</strong>，提交后可以发信告诉队员。游戏 ID 已经默认选好（有多个的选了第一个），需要的话改一下再提交。</p>
          <ol class="border-t border-line"><li v-for="(row,index) in displayRows" :key="row.user_id" class="grid gap-3 border-b border-line py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,18rem)] sm:items-center" data-roster-row>
            <div class="flex flex-wrap items-center gap-2"><span class="font-numeric w-7 text-sm text-fg-3">{{ String(index+1).padStart(2,'0') }}</span><span class="font-semibold">{{ row.nickname }}</span><span v-if="row.is_captain" class="c-tag c-tag--strong">队长</span><span v-if="row.is_sjtu" class="c-tag">交大</span></div>
            <div :class="['c-field',{'is-invalid':row.problems.length||!row.accounts.length||submit.fields.value['account-'+row.user_id]}]"><template v-if="row.accounts.length"><label class="sr-only" :for="'account-'+row.user_id">{{ row.nickname }} 的游戏 ID</label><select :id="'account-'+row.user_id" v-model="accounts[String(row.user_id)]" :name="'account-'+row.user_id" :disabled="!submit.canStart.value"><option v-for="account in row.accounts" :key="account.id" :value="account.id">{{ account.battletag }}</option></select></template><p v-else class="c-field__error"><CIcon name="alert" /><span>这位队员还没有填写游戏 ID。</span></p><p v-for="(problem,problemIndex) in row.problems" :key="problemIndex" class="c-field__error"><CIcon name="alert" /><span>{{ problem }}</span></p><p v-for="(problem,problemIndex) in submit.fields.value['account-'+row.user_id]" :key="'error-'+problemIndex" class="c-field__error">{{ problem }}</p></div>
          </li></ol>
        </div>
        <div class="c-formbar"><button type="submit" class="c-btn c-btn--primary" :disabled="!form.can_submit||!submit.canStart.value">提交报名</button><a :href="'/tournaments/'+tournament.id+'/'" class="c-btn c-btn--quiet">返回赛事</a></div>
      </form>
    </div></div>
  </main>
</template>
