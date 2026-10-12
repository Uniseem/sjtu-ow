<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminTeamsId, getApiAdminUsersSearch, postApiAdminTeamsIdAssignCaptain } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { text } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const confirm = useConfirm()
const search = ref(text(route.query.q))
const selected = ref<number | null>(null)
const resource = useResource(() => route.params.id, signal => getApiAdminTeamsId(api, String(route.params.id), { signal }))
const candidates = useResource(() => route.fullPath, signal => getApiAdminUsersSearch(api, { q: text(route.query.q), active: 'yes', sort: 'nickname' }, { signal }))
const rows = computed(() => candidates.data.value?.users ?? [])
watch(rows, value => { if (!value.some(row => row.id === selected.value)) selected.value = value[0]?.id ?? null })
const action = useAdminAction<number, { result: string }>((id, extras) => postApiAdminTeamsIdAssignCaptain(api, String(route.params.id), { user_id: id }, extras), async () => { await router.push('/admin/teams/') })
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined } }) }
async function assign() {
  if (selected.value === null || !action.canStart.value) return
  const candidate = rows.value.find(row => row.id === selected.value)
  if (candidate && confirm(`指定 ${candidate.nickname} 为「${resource.data.value?.team?.name}」的队长？`)) await action.submit(candidate.id)
}
</script>
<template>
  <AdminPage :title="resource.data.value?.team ? `指定队长：${resource.data.value.team.name}` : '指定队长'" section="成员" :back-href="`/admin/teams/edit/${route.params.id}/`">
    <ResourceState :pending="resource.pending.value || candidates.pending.value" :message="resource.message.value || candidates.message.value" :status="resource.status.value === 200 ? candidates.status.value : resource.status.value" @retry="resource.refresh(); candidates.refresh()" />
    <template v-if="resource.data.value?.team && candidates.data.value">
      <section class="b-section">
        <p class="b-section__text">用于队长账号被停用等情况。被指定的人如果还不是成员，会先加入战队。</p>
        <p class="b-section__text">当前成员： <template v-for="(member, index) in resource.data.value.members" :key="member.user_id">{{ member.nickname }}{{ member.role === 'captain' ? '（队长）' : '' }}{{ index < resource.data.value.members.length - 1 ? '、 ' : '' }}</template><template v-if="!resource.data.value.members.length">（无）</template></p>
        <form method="get" class="b-filters" role="search" @submit.prevent="filter">
          <input id="q" v-model="search" type="search" name="q" maxlength="50" placeholder="按昵称或邮箱找人" class="c-input" aria-label="按昵称或邮箱找人" />
          <button type="submit" class="c-btn c-btn--secondary c-btn--sm">搜索</button>
          <span class="b-count">列出最多 50 个已启用的账号<template v-if="text(route.query.q)">（匹配「{{ text(route.query.q) }}」）</template></span>
        </form>
      </section>
      <form class="b-form" @submit.prevent="assign">
        <div class="b-fieldset"><div class="c-field"><label class="c-field__label" for="user">新队长</label><select id="user" v-model="selected" name="user" class="c-input"><option v-for="candidate in rows" :key="candidate.id" :value="candidate.id">{{ candidate.nickname }}（{{ candidate.email }}）</option></select></div></div>
        <div class="b-actions"><button type="submit" class="c-btn c-btn--primary" :disabled="selected === null || !action.canStart.value">指定为队长</button><RouterLink class="c-btn c-btn--secondary" to="/admin/teams/">返回</RouterLink></div>
      </form>
    </template>
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
  </AdminPage>
</template>
