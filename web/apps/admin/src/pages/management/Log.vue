<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminLog } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { text, positive, date } from "./format"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import { actionLabel, objectLabel } from "./log-labels"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const action = ref(text(route.query.action))
const since = ref(text(route.query.since))
const until = ref(text(route.query.until))
const resource = useResource(() => route.fullPath, signal => getApiAdminLog(api, { action: text(route.query.action), since: text(route.query.since), until: text(route.query.until), page: positive(route.query.page), page_size: 50 }, { signal }))
function filter() { void router.push({ path: route.path, query: { action: action.value || undefined, since: since.value || undefined, until: until.value || undefined } }) }
</script>
<template>
  <AdminPage title="操作记录" section="设置">
    <form class="b-filters" @submit.prevent="filter">
      <select v-model="action" name="action" class="c-input" aria-label="动作" @change="filter"><option value="">全部动作</option><option v-for="value in resource.data.value?.actions" :key="value" :value="value">{{ actionLabel(value) }}</option></select>
      <label class="b-count" for="id_since">从</label><input id="id_since" v-model="since" name="since" class="c-input" type="date" />
      <label class="b-count" for="id_until">到</label><input id="id_until" v-model="until" name="until" class="c-input" type="date" />
  <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
  </form>
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
  <table v-if="resource.data.value?.items.length" class="c-table c-table--stack">
    <thead>
      <tr>
        <th scope="col">时间</th>
        <th scope="col">谁</th>
        <th scope="col">做了什么</th>
        <th scope="col">对象</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="record in resource.data.value.items" :key="record.id">
        <td>{{ date(record.created_at) }}:{{ String(new Date(record.created_at).getUTCSeconds()).padStart(2,'0') }}</td>
        <td data-label="谁">{{ record.actor_nickname || '系统' }}</td>
        <td data-label="做了什么">{{ actionLabel(record.action) }}</td>
        <td data-label="对象">{{ record.label || `${objectLabel(record.object_type)} #${record.object_id}` }}</td>
      </tr>
    </tbody>
  </table>
  <CEmpty v-else-if="!resource.pending.value && !resource.message.value" title="没有记录" message="换个时间段或动作试试。" />
  <ManagementPager v-if="resource.data.value" :total="resource.data.value.total" :page="resource.data.value.page" :size="resource.data.value.page_size" />
  </AdminPage>
</template>
