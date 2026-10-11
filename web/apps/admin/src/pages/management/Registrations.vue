<script setup lang="ts">
import { computed, onUnmounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import { useResource } from "./use-resource"
import { getRegistrations, bulkApprove, exportRegistrations, type BulkReceipt, type RegistrationQuery } from "./pending"
import { text, positive, date, state } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ActionState from "../../components/management/ActionState.vue"
import ConfirmAction from "../../components/management/ConfirmAction.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const search = ref(text(route.query.q))
const status = ref(text(route.query.status))
const tournament = ref(text(route.query.tournament))
const selection = ref<number[]>([])
const result = ref<BulkReceipt | null>(null)
const downloadError = ref("")
const exporting = ref(false)
let csvUrl: string | null = null
let exportFlight: AbortController | undefined
function query(): RegistrationQuery { return { q: text(route.query.q), status: text(route.query.status), tournament_id: route.query.tournament ? positive(route.query.tournament) : undefined, page: positive(route.query.page) } }
const resource = useResource(() => route.fullPath, async signal => { selection.value = []; result.value = null; return getRegistrations(api, query(), { signal }) })
const selectable = computed(() => resource.data.value?.items.filter(row => row.can_approve).map(row => row.id) ?? [])
const all = computed(() => selectable.value.length > 0 && selectable.value.every(id => selection.value.includes(id)))
const action = useAdminAction<number[], BulkReceipt>((ids, extras) => bulkApprove(api, ids, extras), async response => { await resource.refresh(); result.value = response; selection.value = response.failed.map(item => item.id) })
function choose(id: number, enabled: boolean) { selection.value = enabled ? [...new Set([...selection.value, id])] : selection.value.filter(value => value !== id) }
function checked(event: Event) { return (event.target as HTMLInputElement).checked }
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, status: status.value || undefined, tournament: tournament.value || undefined } }) }
async function download() {
  if (exporting.value) return
  exporting.value = true
  downloadError.value = ""
  exportFlight = new AbortController()
  try {
    const response = await exportRegistrations(api, { ...query(), page: undefined }, { signal: exportFlight.signal })
    if (csvUrl) URL.revokeObjectURL(csvUrl)
    csvUrl = URL.createObjectURL(new Blob([response.csv], { type: "text/csv;charset=utf-8" }))
    const link = document.createElement("a")
    link.href = csvUrl
    link.download = response.filename.replace(/[\/\\]/g, "_") || "registrations.csv"
    link.click()
  } catch (error) { downloadError.value = error instanceof Error ? error.message : '暂时无法导出。' }
  finally { exporting.value = false }
}
onUnmounted(() => { exportFlight?.abort(); if (csvUrl) URL.revokeObjectURL(csvUrl) })
</script>
<template>
  <AdminPage title="报名" section="审核">
    <template #actions>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="exporting || resource.pending.value" @click="download">{{ exporting ? '正在导出…' : '导出 CSV' }}</button>
    </template>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" type="search" class="c-input" placeholder="搜队名" aria-label="搜队名" />
      <select v-model="tournament" class="c-input" aria-label="赛事">
        <option value="">全部赛事</option>
        <option v-for="event in resource.data.value?.tournaments" :key="event.id" :value="String(event.id)">{{ event.title }}</option>
      </select>
      <select v-model="status" class="c-input" aria-label="状态">
        <option value="">全部状态</option>
        <option value="pending">待审核</option>
        <option value="approved">已通过</option>
        <option value="rejected">已驳回</option>
        <option value="withdrawn">已撤回</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
    </form>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.items.length" empty-text="没有符合条件的报名。" @retry="resource.refresh" />
    <ActionState :message="action.message.value" :pending="action.pending.value" :uncertain="action.uncertain.value" @retry="action.retry" />
    <p v-if="downloadError" class="c-field__error" role="alert">{{ downloadError }}</p>
    <section v-if="result" class="b-section" aria-live="polite">
      <p>已通过 {{ result.approved.length }} 份报名。</p>
      <ul v-if="result.failed.length" class="b-list">
        <li v-for="failed in result.failed" :key="failed.id">
          <RouterLink :to="`/admin/registrations/${failed.id}/`">报名 #{{ failed.id }}</RouterLink>
          <span>{{ failed.message }}</span>
        </li>
      </ul>
    </section>
    <table v-if="resource.data.value?.items.length" class="c-table">
      <thead>
        <tr>
          <th scope="col">
            <input type="checkbox" :checked="all" :disabled="!selectable.length || !action.canStart.value" aria-label="选中本页可通过的报名" @change="selection = checked($event) ? [...selectable] : []" />
          </th>
          <th scope="col">队伍</th>
          <th scope="col">赛事</th>
          <th scope="col">状态</th>
          <th scope="col">提交时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in resource.data.value.items" :key="row.id">
          <td>
            <input type="checkbox" :checked="selection.includes(row.id)" :disabled="!row.can_approve || !action.canStart.value" :aria-label="`选择${row.team_name}的报名`" @change="choose(row.id, checked($event))" />
          </td>
          <td>
            <RouterLink class="b-title" :to="`/admin/registrations/${row.id}/`">{{ row.team_name }}</RouterLink>
          </td>
          <td>{{ row.tournament_title }}</td>
          <td>{{ state(row.status) }}<span v-if="row.status_note" class="b-sub">{{ row.status_note }}</span>
          </td>
          <td>{{ date(row.submitted_at) }}</td>
        </tr>
      </tbody>
    </table>
    <div v-if="selectable.length" class="b-actions">
      <span class="b-sub">已选 {{ selection.length }} 份</span>
      <ConfirmAction title="批量通过报名" :message="`通过已选的 ${selection.length} 份报名？`" label="批量通过" :pending="!selection.length || !action.canStart.value" @confirm="action.submit([...selection])" />
    </div>
    <ManagementPager v-if="resource.data.value" :total="resource.data.value.total" :page="resource.data.value.page" :size="resource.data.value.page_size" />
  </AdminPage>
</template>
