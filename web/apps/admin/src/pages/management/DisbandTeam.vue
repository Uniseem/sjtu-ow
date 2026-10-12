<script setup lang="ts">
import { useRoute, useRouter } from "vue-router"
import { getApiAdminTeamsId, postApiAdminTeamsIdDisband } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const confirm = useConfirm()
const resource = useResource(() => route.params.id, signal => getApiAdminTeamsId(api, String(route.params.id), { signal }))
const action = useAdminAction<null, { result: string }>((_, extras) => postApiAdminTeamsIdDisband(api, String(route.params.id), extras), async () => { await router.push('/admin/teams/') })
function disband() { if (action.canStart.value && confirm(`确定解散「${resource.data.value?.team?.name}」吗？`)) void action.submit(null) }
</script>
<template>
  <AdminPage :title="resource.data.value?.team ? `解散战队：${resource.data.value.team.name}` : '解散战队'" section="成员" :back-href="`/admin/teams/edit/${route.params.id}/`">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <section v-if="resource.data.value?.team" class="b-section">
      <p class="b-section__text">确定解散「{{ resource.data.value.team.name }}」吗？成员会被清空、待审批的申请会取消，队名可以被其他战队使用。历史报名记录仍然保留。</p>
      <form class="b-actions" @submit.prevent="disband"><button type="submit" class="c-btn c-btn--danger" :disabled="!action.canStart.value">确认解散</button><RouterLink class="c-btn c-btn--secondary" to="/admin/teams/">取消</RouterLink></form>
    </section>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </AdminPage>
</template>
