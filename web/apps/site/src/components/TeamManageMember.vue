<script setup lang="ts">
import { postApiTeamsIdTransfer, postApiTeamsIdMembersUser_idRemove } from "@sjtu-ow/api"
import CPlay from "@sjtu-ow/ui/CPlay.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { memberPlay, type TeamMember } from "../team-domain"
const props = defineProps<{ teamId: number; member: TeamMember & { game_ids?: string[] } }>()
const emit = defineEmits<{ changed: []; transferred: [] }>()
const api = useApi()
const confirm = useConfirm()
const action = useMutation((body: { transfer: boolean }, extras) => body.transfer
  ? postApiTeamsIdTransfer(api, props.teamId, { user_id: props.member.user_id }, extras)
  : postApiTeamsIdMembersUser_idRemove(api, props.teamId, props.member.user_id, extras), () => emit("changed"))
async function change(transfer: boolean): Promise<void> {
  if (!confirm(transfer ? "把队长转让给这名成员？转让后你就是普通队员了。" : "把这名成员移出战队？")) return
  if (await action.submit({ transfer }) && transfer) emit("transferred")
}
</script>
<template>
  <tr>
    <td data-label="昵称"><span class="font-semibold">{{ member.nickname }}</span><template v-if="member.role === 'captain'">{{ ' ' }}<span class="c-tag c-tag--strong ml-1">队长</span></template><template v-if="!member.is_active">{{ ' ' }}<span class="c-tag ml-1" data-account-stopped>账号已停用</span><span class="block text-sm text-fg-2">这个账号被管理员停用了，可以移出、空出名额</span></template></td>
    <td data-label="位置与段位"><CPlay :profile="memberPlay(member)" /></td>
    <td data-label="游戏 ID" class="text-sm"><template v-for="(tag, index) in member.game_ids" :key="index"><span class="font-code">{{ tag }}</span><template v-if="index < (member.game_ids?.length || 0) - 1">、</template></template><span v-if="member.game_ids && !member.game_ids.length" class="text-fg-3">未填写</span></td>
    <td data-label="操作" class="is-num">
      <span v-if="member.role !== 'captain'" class="inline-flex flex-wrap justify-end gap-2">
        <form v-if="member.is_active" method="post" @submit.prevent="change(true)"><button type="submit" class="c-btn c-btn--secondary c-btn--sm" :disabled="!action.canStart.value">转让队长</button></form>
        <form method="post" @submit.prevent="change(false)"><button type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!action.canStart.value">移除</button></form>
      </span>
      <CMutationError :message="action.message.value" :uncertain="action.uncertain.value" :pending="action.pending.value" @retry="action.retry" />
    </td>
  </tr>
</template>
