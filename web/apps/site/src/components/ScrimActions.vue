<script setup lang="ts">
import { computed,ref,watch } from "vue"
import { postApiScrimsIdSignup,deleteApiScrimsIdSignup } from "@sjtu-ow/api"
import CProfileGaps from "@sjtu-ow/ui/CProfileGaps.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CRoleIcon from "@sjtu-ow/ui/CRoleIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import EventSignupFields from "./EventSignupFields.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { useViewer } from "../viewer"
import { useMutation } from "../use-mutation"
import { useApi } from "../api"
import type { ScrimPage } from "../event-domain"
const props=defineProps<{ page:ScrimPage;accounts:Array<{id:number;battletag:string}>;groupUrl?:string }>()
const emit=defineEmits<{changed:[]}>()
const viewer=useViewer()
const api=useApi()
const confirm=useConfirm()
const account=ref<number|null>(props.page.mine?.game_account_id || props.accounts[0]?.id || null)
const roles=ref<string[]>(props.page.mine?.roles || [])
const open=computed(()=>props.page.card.signup_open)
const canEdit=computed(()=>open.value&&props.accounts.length>0)
const signup=useMutation((body:{game_account_id:number;roles:string[]},extras)=>postApiScrimsIdSignup(api,props.page.card.id,body,extras),()=>emit("changed"))
const cancel=useMutation((_body:Record<string,never>,extras)=>deleteApiScrimsIdSignup(api,props.page.card.id,extras),()=>emit("changed"))
function submit():void{if(canEdit.value&&account.value)void signup.submit({game_account_id:account.value,roles:[...roles.value]})}
function remove():void{if(props.page.mine?.can_cancel&&confirm("取消这场内战的报名？"))void cancel.submit({})}
watch(()=>props.page.mine,mine=>{account.value=mine?.game_account_id||props.accounts[0]?.id||null;roles.value=mine?.roles||[];signup.clear();cancel.clear()})
</script>
<template>
  <div id="slot-scrim-actions">
    <p v-if="page.card.status==='cancelled'" class="text-sm text-fg-2">这场内战已取消，不再接受报名。</p>
    <a v-else-if="!viewer.user" :href="'/accounts/login/?next=' + ('/scrims/' + page.card.id + '/')" class="c-btn c-btn--primary">登录后报名</a>
    <template v-else-if="page.mine">
      <div class="max-w-2xl">
        <p class="flex flex-wrap items-center gap-3"><CStatus kind="ok" label="已报名" /><span class="font-code text-sm">{{ accounts.find(item=>item.id===page.mine?.game_account_id)?.battletag }}</span><CRoleIcon :tank="page.mine.roles.includes('tank')" :damage="page.mine.roles.includes('damage')" :support="page.mine.roles.includes('support')" /></p>
        <p v-if="page.mine.placement" class="mt-2 text-sm" data-my-placement>当前分队：<strong>{{ page.mine.placement }}</strong><span class="text-fg-2">（以管理员在群里发的为准）</span></p>
        <p v-if="groupUrl" class="mt-2 text-sm text-fg-2" data-group-link>分队结果发到社团 QQ 群，<a :href="groupUrl" class="c-link" rel="noopener">还没进群的点这里加入</a>。</p>
        <div v-if="open" class="mt-4 flex flex-wrap items-start gap-3">
          <details class="open:order-last open:basis-full"><summary class="c-btn c-btn--secondary c-btn--sm">修改报名</summary><form method="post" class="c-form mt-4" @submit.prevent="submit"><EventSignupFields :prefix="'scrim-' + page.card.id" :accounts="accounts" :account-id="account" :roles="roles" :fields="signup.fields.value" :disabled="!signup.canStart.value" :role-queue="page.card.format !== 'open_5v5' && page.card.format !== 'open_6v6'" @account="value=>account=value" @roles="value=>roles=value" /><button type="submit" class="c-btn c-btn--primary" :disabled="!signup.canStart.value || !account">保存修改</button></form></details>
          <form v-if="page.mine.can_cancel" method="post" @submit.prevent="remove"><button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!cancel.canStart.value">取消报名</button></form>
        </div><p v-else class="mt-3 text-sm text-fg-2">报名已截止，不能再修改。</p>
      </div>
    </template>
    <template v-else-if="page.problems.length"><div class="c-notice c-notice--warn max-w-2xl"><CIcon name="alert" /><div class="c-notice__body"><p>暂时不能报名：</p><ul class="mt-1 list-[square] pl-5"><li v-for="(problem,index) in page.problems" :key="index">{{ problem }}</li></ul><CProfileGaps :gaps="viewer.user?.profile_gaps ?? []" /></div></div></template>
    <template v-else-if="!accounts.length"><div class="c-notice c-notice--info max-w-2xl"><CIcon name="info" /><div class="c-notice__body">需要先绑定游戏 ID，<a href="/me/game-accounts/">去添加</a>。</div></div></template>
    <template v-else-if="open"><div class="max-w-2xl"><h2 class="text-lg">报名</h2><form method="post" class="c-form mt-4" @submit.prevent="submit"><EventSignupFields :prefix="'scrim-' + page.card.id" :accounts="accounts" :account-id="account" :roles="roles" :fields="signup.fields.value" :disabled="!signup.canStart.value" :role-queue="page.card.format.startsWith('rq_')" @account="value=>account=value" @roles="value=>roles=value" /><button type="submit" class="c-btn c-btn--primary" :disabled="!signup.canStart.value || !account">报名</button></form></div></template>
    <p v-else class="text-sm text-fg-2">报名已截止，不能再报名。</p>
    <CMutationError :message="signup.message.value" :uncertain="signup.uncertain.value" :pending="signup.pending.value" @retry="signup.retry" />
    <CMutationError :message="cancel.message.value" :uncertain="cancel.uncertain.value" :pending="cancel.pending.value" @retry="cancel.retry" />
  </div>
</template>
