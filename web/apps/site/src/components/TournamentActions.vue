<script setup lang="ts">
import { computed } from "vue"
import { deleteApiTournamentsIdSignup } from "@sjtu-ow/api"
import CProfileGaps from "@sjtu-ow/ui/CProfileGaps.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import CRegStatus from "@sjtu-ow/ui/CRegStatus.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import { TEAM_ROLES } from "../team-domain"
import { useApi } from "../api"
import { useViewer } from "../viewer"
import { useMutation } from "../use-mutation"
import { registrationLabel } from "../registration-display"
import { type TournamentPage } from "../event-domain"
const props=defineProps<{ page:TournamentPage }>()
const emit=defineEmits<{ changed:[] }>()
const api=useApi()
const viewer=useViewer()
const confirm=useConfirm()
const tournament=computed(()=>props.page.tournament)
const mine=computed(()=>props.page.viewer.my_signup)
const roleLabels=computed(()=>TEAM_ROLES.filter(role=>mine.value?.roles.includes(role.code)).map(role=>role.label).join(" / "))
const placedTeamName=computed(()=>mine.value?.registration_team_name ?? props.page.approved_teams.find(team=>team.registration_id===mine.value?.registration_id)?.team_name)
const teamRegistration=computed(()=>props.page.viewer.captain_teams.find(team=>team.registration)?.registration)
const cancel=useMutation((_body:Record<string,never>,extras)=>deleteApiTournamentsIdSignup(api,tournament.value?.id || 0,extras),()=>emit("changed"))
function remove():void{if(confirm("取消个人报名？"))void cancel.submit({})}
</script>
<template>
  <div v-if="tournament" id="slot-tournament-actions" class="flex flex-wrap items-center gap-3">
    <template v-if="tournament.status === 'cancelled'"><p class="text-sm text-fg-2">赛事已取消，不再接受报名。</p></template>
    <template v-else-if="!viewer.user"><a :href="'/accounts/login/?next=' + ('/tournaments/' + tournament.id + '/')" class="c-btn c-btn--primary">登录后报名</a></template>
    <template v-else-if="tournament.registration_mode === 'individual'">
      <template v-if="mine">
        <template v-if="mine.placed && mine.registration_id"><CStatus kind="ok" :label="placedTeamName?'已编入「'+placedTeamName+'」':'已编入队伍'" /><a :href="'/registrations/' + mine.registration_id + '/'" class="c-btn c-btn--primary">查看报名</a></template>
        <template v-else><CStatus kind="ok" label="已个人报名，等待编队" /><span class="text-sm text-fg-2">{{ roleLabels }}</span><template v-if="page.viewer.registration_open"><a :href="'/tournaments/' + tournament.id + '/signup/'" class="c-btn c-btn--secondary c-btn--sm">修改</a><form method="post" @submit.prevent="remove"><button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!cancel.canStart.value">取消个人报名</button></form></template><span v-else class="text-sm text-fg-2">报名已截止，不能再修改。</span></template>
      </template>
      <template v-else-if="!page.viewer.registration_open"><span class="text-sm text-fg-2">当前不在报名时间内。</span></template>
      <template v-else-if="page.viewer.individual_problems.length"><div class="c-notice c-notice--warn w-full max-w-2xl"><CIcon name="alert" /><div class="c-notice__body"><p>暂时不能个人报名：</p><ul class="mt-1 list-[square] pl-5"><li v-for="(problem,index) in page.viewer.individual_problems" :key="index">{{ problem }}</li></ul><CProfileGaps :gaps="viewer.user?.profile_gaps ?? []" /></div></div></template>
      <template v-else><a :href="'/tournaments/' + tournament.id + '/signup/'" class="c-btn c-btn--primary">个人报名</a><span class="text-sm text-fg-2">每人自己报名，截止后由赛事管理员编队。</span></template>
    </template>
    <template v-else-if="teamRegistration"><CRegStatus :status="teamRegistration.status" :label="registrationLabel(teamRegistration.status)" /><a :href="'/registrations/' + teamRegistration.id + '/'" class="c-btn c-btn--primary">查看报名</a></template>
    <template v-else-if="page.viewer.captain_teams.length && page.viewer.registration_open"><a :href="'/tournaments/' + tournament.id + '/register/'" class="c-btn c-btn--primary">为战队报名</a><span class="text-sm text-fg-2">整队报名，提交后全队直接进入名单，不需要队员确认。</span></template>
    <template v-else-if="page.viewer.captain_teams.length"><span class="text-sm text-fg-2">当前不在报名时间内。</span></template>
    <template v-else-if="page.viewer.on_roster"><CRegStatus :status="page.viewer.on_roster.status" :label="registrationLabel(page.viewer.on_roster.status)" /><span class="text-sm">你在「{{ page.viewer.on_roster.team_name }}」的名单里</span><a :href="'/registrations/' + page.viewer.on_roster.id + '/'" class="c-btn c-btn--primary">查看报名</a></template>
    <template v-else><span class="text-sm text-fg-2">这项赛事是整队报名，需要由队长为战队报名。</span></template>
    <p v-if="page.viewer.participant_contact" class="w-full text-sm text-fg-2" data-participant-contact>选手联系方式：<span class="font-code text-fg">{{ page.viewer.participant_contact }}</span></p>
    <CMutationError :message="cancel.message.value" :uncertain="cancel.uncertain.value" :pending="cancel.pending.value" @retry="cancel.retry" />
  </div>
</template>
