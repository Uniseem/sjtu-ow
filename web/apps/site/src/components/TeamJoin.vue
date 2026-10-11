<script setup lang="ts">
import { computed } from "vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { postApiTeamsIdLeave } from "@sjtu-ow/api"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { useViewer } from "../viewer"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { finishAccountAction } from "../account-form"
import type { TeamDetail, Team } from "../team-domain"

const props = defineProps<{ team: Team; viewer: TeamDetail["viewer"] }>()
const viewer = useViewer()
const api = useApi()
const confirm = useConfirm()
const login = computed(() => `/accounts/login/?next=/teams/${props.team.id}/`)
const mutation = useMutation(
  (id: number, extras) => postApiTeamsIdLeave(api, id, extras),
  () => finishAccountAction(`/teams/${props.team.id}/`),
)

function leave(): void {
  if (!confirm("确定退出这支战队？")) return
  void mutation.submit(props.team.id)
}
</script>

<template>
  <div :id="'slot-team-join'" :data-slot="'team-join:' + team.id" class="flex flex-wrap items-center gap-3">
    <template v-if="props.viewer.is_captain">
      <a :href="'/teams/' + team.id + '/manage/'" class="c-btn c-btn--primary"><CIcon name="settings" />管理战队</a>
    </template>
    <template v-else-if="props.viewer.is_member">
      <CStatus kind="ok" label="你已是成员" />
      <form method="post" :action="'/teams/' + team.id + '/leave/'" @submit.prevent="leave">
        <button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!mutation.canStart.value">退出战队</button>
      </form>
    </template>
    <a v-else-if="props.viewer.can_apply" :href="'/teams/' + team.id + '/apply/'" class="c-btn c-btn--primary">申请加入</a>
    <div v-else-if="viewer.user" class="text-sm text-fg-2">
      {{ props.viewer.apply_reason }}
      <a v-if="props.viewer.needs_game_account" href="/me/game-accounts/" class="c-link">补全游戏 ID</a>
    </div>
    <a v-else :href="login" class="c-btn c-btn--primary">登录后申请</a>
    <p v-if="(props.viewer.is_member || props.viewer.is_captain) && team.member_contact" class="w-full text-sm text-fg-2" data-member-contact>
      队内联系方式：<span class="font-code text-fg">{{ team.member_contact }}</span><span v-if="props.viewer.is_captain" class="text-fg-3">（只有队员看得到）</span>
    </p>
    <p v-else-if="props.viewer.is_captain" class="w-full text-sm text-fg-3">还没填队内联系方式（比如群号），新队员入队后不知道怎么联系你们。<a :href="'/teams/' + team.id + '/manage/#manage-profile'" class="c-link">去填</a></p>
    <CMutationError :message="mutation.message.value" :uncertain="mutation.uncertain.value" :pending="mutation.pending.value" @retry="mutation.retry" />
  </div>
</template>
