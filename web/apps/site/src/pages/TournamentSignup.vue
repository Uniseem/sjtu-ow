<script lang="ts">
import type { LoadCtx } from "../router"
import { getIndividualForm } from "../registration-form"
import { requireTournament as loadedTournament } from "../event-domain"
export async function load(ctx:LoadCtx){const form=await getIndividualForm(ctx.api,ctx.params.id);return{title:"个人报名 · "+loadedTournament(form.tournament).title,form}}
</script>
<script setup lang="ts">
import { computed,inject,ref,watch } from "vue"
import { useHead } from "@unhead/vue"
import { postApiTournamentsIdSignup } from "@sjtu-ow/api"
import CProfileGaps from "@sjtu-ow/ui/CProfileGaps.vue"
import { useViewer } from "../viewer"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { TEAM_ROLES } from "../team-domain"
import { requireTournament } from "../event-domain"
import { requirePageData } from "../personal"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { finishAccountAction } from "../account-form"
import type { IndividualForm } from "../registration-form"
const viewer=useViewer()
const data=requirePageData(inject<{form:IndividualForm}>("page-data"))
const form=computed(()=>data.form)
const tournament=computed(()=>requireTournament(form.value.tournament))
const account=ref<number|null>(form.value.my_signup?.game_account_id||form.value.game_accounts[0]?.id||null)
const roles=ref<string[]>(form.value.my_signup?.roles||[])
const api=useApi()
const signup=useMutation((body:{game_account_id:number;roles:string[]},extras)=>postApiTournamentsIdSignup(api,tournament.value.id,body,extras),()=>finishAccountAction("/tournaments/"+tournament.value.id+"/"))
watch(()=>data.form,next=>{account.value=next.my_signup?.game_account_id||next.game_accounts[0]?.id||null;roles.value=next.my_signup?.roles||[];signup.clear()})
useHead(computed(()=>({title:"个人报名 · "+tournament.value.title+" · SJTU-OW",meta:[{name:"robots",content:"noindex"}]})))
function submit():void{if(form.value.can_submit&&account.value)void signup.submit({game_account_id:account.value,roles:[...roles.value]})}
</script>
<template>
  <main id="main" class="flex-1">
    <header class="c-pagehead"><div class="l-container l-container--narrow"><nav class="c-crumbs" aria-label="位置"><a href="/">首页</a><span class="c-crumbs__sep">/</span><a href="/tournaments/">赛事</a><span class="c-crumbs__sep">/</span><a :href="'/tournaments/' + tournament.id + '/'">{{ tournament.title }}</a><span class="c-crumbs__sep">/</span><span>个人报名</span></nav><h1>个人报名</h1><p class="c-pagehead__lede"><a :href="'/tournaments/'+tournament.id+'/'" class="c-link">{{ tournament.title }}</a> · 报名后由赛事管理员编成临时队伍</p></div></header>
    <div class="l-container l-container--narrow pt-8 pb-16 lg:pb-24"><div class="flex max-w-2xl flex-col gap-8">
      <div v-if="form.problems.length" class="c-notice c-notice--error" role="alert"><CIcon name="x-circle" /><div class="c-notice__body"><p class="font-semibold">下面的问题需要先解决：</p><ul class="mt-1 list-[square] pl-5"><li v-for="(problem,index) in form.problems" :key="index">{{ problem }}</li></ul><CProfileGaps :gaps="viewer.user?.profile_gaps ?? []" /></div></div>
      <div v-if="form.my_signup?.placed" class="c-notice c-notice--ok"><CIcon name="check-circle" /><p class="c-notice__body">你已经被编入「{{ form.registration_team_name }}」，要改动请联系赛事管理员。</p></div>
      <div v-else-if="!form.game_accounts.length" class="c-notice c-notice--info"><CIcon name="info" /><p class="c-notice__body">需要先绑定游戏 ID，<a href="/me/game-accounts/">去添加</a>。</p></div>
      <form v-else method="post" class="c-form" :aria-busy="signup.pending.value||undefined" @submit.prevent="submit">
        <CMutationError :message="signup.message.value" :uncertain="signup.uncertain.value" :pending="signup.pending.value" @retry="signup.retry" />
        <div class="c-step"><div class="c-step__head"><h2 class="text-lg">选择游戏 ID</h2></div><CField label="游戏 ID" input-id="signup-account" :errors="signup.fields.value.game_account_id" required><select id="signup-account" v-model="account" name="game_account" required :disabled="!signup.canStart.value"><option v-for="game in form.game_accounts" :key="game.id" :value="game.id">{{ game.battletag }}</option></select><template #help>不要求填段位，但管理员编队时会参考这个游戏 ID 上的段位。</template></CField></div>
        <div class="c-step"><div class="c-step__head"><h2 class="text-lg">能打的位置（至少一个）</h2></div><fieldset class="c-choices" :disabled="!signup.canStart.value"><legend class="sr-only">能打的位置</legend><label v-for="role in TEAM_ROLES" :key="role.code" class="c-choice"><input v-model="roles" type="checkbox" name="roles" :value="role.code"><CIcon :name="'role-'+role.code" class="size-4" /><span>{{ role.label }}</span></label></fieldset><p v-for="(error,index) in signup.fields.value.roles" :key="index" class="c-field__error">{{ error }}</p></div>
        <div class="c-formbar"><button type="submit" class="c-btn c-btn--primary" :disabled="!form.can_submit||!signup.canStart.value||!account">{{ form.my_signup?'保存修改':'提交个人报名' }}</button><a :href="'/tournaments/'+tournament.id+'/'" class="c-btn c-btn--quiet">返回赛事</a></div>
      </form>
    </div></div>
  </main>
</template>
