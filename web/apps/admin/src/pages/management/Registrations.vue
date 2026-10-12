<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { getRegistrations, bulkApprove, type BulkReceipt, type RegistrationQuery } from "./pending"
import { text, positive, date, state } from "./format"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const search = ref(text(route.query.q))
const status = ref(route.query.status === undefined ? "pending" : text(route.query.status))
const tournament = ref(text(route.query.tournament))
const selection = ref<number[]>([])
const result = ref<BulkReceipt | null>(null)
const exportHref = computed(() => {
  const query = new URLSearchParams()
  for (const key of ["tournament", "status"]) if (typeof route.query[key] === "string") query.set(key, String(route.query[key]))
  return "/admin/registrations/export.csv" + (query.size ? "?" + query : "")
})
function query(): RegistrationQuery { return { q: text(route.query.q), status: route.query.status === undefined ? "pending" : text(route.query.status), tournament_id: route.query.tournament ? positive(route.query.tournament) : undefined, page: positive(route.query.page) } }
const resource = useResource(() => route.fullPath, async signal => { selection.value = []; result.value = null; return getRegistrations(api, query(), { signal }) })
const selectable = computed(() => resource.data.value?.items.filter(row => row.can_approve).map(row => row.id) ?? [])
const all = computed(() => selectable.value.length > 0 && selectable.value.every(id => selection.value.includes(id)))
const action = useAdminAction<number[], BulkReceipt>((ids, extras) => bulkApprove(api, ids, extras), async response => { await resource.refresh(); result.value = response; selection.value = response.failed.map(item => item.id) })
function choose(id: number, enabled: boolean) { selection.value = enabled ? [...new Set([...selection.value, id])] : selection.value.filter(value => value !== id) }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, status: status.value, tournament: tournament.value || undefined } }) }
</script>
<template>
  <AdminPage title="报名审核" section="审核">
    <template #actions>
      <a :href="exportHref" class="c-btn c-btn--secondary c-btn--sm" download><CIcon name="download" />导出 CSV</a>
    </template>
    <form method="get" class="b-filters" @submit.prevent="filter">
      <select v-model="tournament" name="tournament" class="c-input" aria-label="赛事" @change="filter">
        <option value="">全部赛事</option>
        <option v-for="event in resource.data.value?.tournaments" :key="event.id" :value="String(event.id)">{{ event.title }}</option>
      </select>
      <select v-model="status" name="status" class="c-input" aria-label="状态" @change="filter">
        <option value="">全部状态</option>
        <option value="pending">待审核</option>
        <option value="approved">已通过</option>
        <option value="rejected">已驳回</option>
        <option value="withdrawn">已撤回</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
    </form>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <section v-if="result" class="b-section" aria-live="polite">
      <p>已通过 {{ result.approved.length }} 份报名。</p>
      <ul v-if="result.failed.length" class="b-list">
        <li v-for="failed in result.failed" :key="failed.id">
          <RouterLink :to="`/admin/registrations/${failed.id}/`">报名 #{{ failed.id }}</RouterLink>
          <span>{{ failed.message }}</span>
        </li>
      </ul>
    </section>
    <form v-if="resource.data.value" class="b-form" @submit.prevent="selection.length && action.canStart.value && action.submit([...selection])">
    <table class="c-table c-table--stack">
      <thead>
        <tr>
          <th scope="col">
            <label class="c-check"><input type="checkbox" :checked="all" :disabled="!selectable.length || !action.canStart.value" aria-label="全选" @change="selection = checked($event) ? [...selectable] : []" /></label>
          </th>
          <th>战队</th>
          <th scope="col">赛事</th>
          <th class="is-num">人数</th><th>状态</th><th class="is-num">名单版本</th>
          <th scope="col">提交时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in resource.data.value.items" :key="row.id">
          <td>
            <label class="c-check"><input type="checkbox" name="registration" :value="row.id" :checked="selection.includes(row.id)" :disabled="!row.can_approve || !action.canStart.value" :aria-label="`选中 ${row.team_name}`" @change="choose(row.id, checked($event))" /></label>
          </td>
          <td data-label="战队"><RouterLink class="b-title" :to="`/admin/registrations/${row.id}/`">{{ row.team_name }}</RouterLink><span v-if="row.deactivated" class="b-sub split-problem">名单里有 {{ row.deactivated }} 个账号已停用</span></td>
          <td data-label="赛事">{{ row.tournament_title }}</td><td class="is-num" data-label="人数">{{ row.member_count }}</td>
          <td data-label="状态">{{ state(row.status) }}</td><td class="is-num" data-label="名单版本">{{ row.roster_version }}</td><td data-label="提交时间">{{ date(row.submitted_at) }}</td>
        </tr>
        <tr v-if="!resource.data.value.items.length"><td colspan="7">没有符合条件的报名。</td></tr>
      </tbody>
    </table>
    <div v-if="resource.data.value.items.length" class="b-actions">
      <button type="submit" class="c-btn c-btn--primary" :disabled="!selection.length || !action.canStart.value">批量通过所选</button>
    </div>
    </form>
    <ManagementPager v-if="resource.data.value" :total="resource.data.value.total" :page="resource.data.value.page" :size="resource.data.value.page_size" />
  </AdminPage>
</template>
