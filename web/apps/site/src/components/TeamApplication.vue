<script setup lang="ts">
import { ref } from "vue"
import { postApiTeamApplicationsIdApprove, postApiTeamApplicationsIdReject } from "@sjtu-ow/api"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { owDate } from "@sjtu-ow/shared/time"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { memberPerson } from "../team-domain"
import type { TeamManage } from "../team-domain"
const props = defineProps<{ application: TeamManage["pending"][number] & { game_accounts?: Array<{id:number;battletag:string;rank_summary:string}> } }>()
const emit = defineEmits<{ changed: [] }>()
const api = useApi()
const note = ref("")
const action = useMutation((body: { approve: boolean; note: string }, extras) => body.approve
  ? postApiTeamApplicationsIdApprove(api, props.application.id, extras)
  : postApiTeamApplicationsIdReject(api, props.application.id, { note: body.note }, extras), () => emit("changed"))
function approve(): void { void action.submit({ approve: true, note: "" }) }
function reject(): void { void action.submit({ approve: false, note: note.value }) }
</script>
<template>
  <li class="c-panel">
    <div class="c-panel__head">
      <p class="flex flex-wrap items-center gap-3">
        <CAvatar :person="memberPerson(application.applicant)" size="sm" plain />
        <strong>{{ application.applicant.nickname }}</strong>
        <CIcon v-for="role in application.roles" :key="role" :name="'role-' + role" />
      </p>
      <time class="font-numeric text-sm text-fg-3" :datetime="application.created_at">{{ owDate(new Date(application.created_at)) }}</time>
    </div>
    <p v-if="application.message" class="mt-3 leading-7">{{ application.message }}</p>
    <ul class="mt-3 flex flex-col gap-1 text-sm text-fg-2">
      <template v-if="application.game_accounts"><li v-for="game in application.game_accounts" :key="game.id"><span class="font-code text-fg">{{ game.battletag }}</span>：{{ game.rank_summary }}</li></template><template v-else><li v-for="(tag,index) in application.game_ids" :key="index"><span class="font-code text-fg">{{ tag }}</span></li></template>
      <li v-if="!application.game_ids.length">游戏 ID：未填写</li>
    </ul>
    <CMutationError :message="action.message.value" :uncertain="action.uncertain.value" :pending="action.pending.value" @retry="action.retry" />
    <div class="c-panel__actions items-end">
      <form method="post" @submit.prevent="approve"><button type="submit" class="c-btn c-btn--primary c-btn--sm" :disabled="!action.canStart.value">通过</button></form>
      <form method="post" class="flex flex-1 flex-wrap items-end gap-2" @submit.prevent="reject">
        <label class="sr-only" :for="'reject-' + application.id">拒绝原因</label>
        <input :id="'reject-' + application.id" v-model="note" type="text" name="note" maxlength="200" placeholder="拒绝原因（可选）" class="c-input min-h-9 max-w-xs flex-1 py-1.5 text-sm" :disabled="!action.canStart.value">
        <button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!action.canStart.value">拒绝</button>
      </form>
    </div>
  </li>
</template>
