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
import { actionLabel, objectLabel, objectHref } from "./log-labels"
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
      <label>动作<input v-model="action" class="c-input" placeholder="全部动作" />
    </label>
    <label>从<input v-model="since" class="c-input" type="date" />
  </label>
  <label>到<input v-model="until" class="c-input" type="date" />
  </label>
  <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
  </form>
  <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.items.length" empty-text="没有符合条件的操作记录。" @retry="resource.refresh" />
  <table v-if="resource.data.value?.items.length" class="c-table">
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
        <td>{{ date(record.created_at) }}</td>
        <td>{{ record.actor_nickname || '系统' }}<span v-if="record.actor_email" class="b-sub">{{ record.actor_email }}</span>
        </td>
        <td>{{ actionLabel(record.action) }}</td>
        <td>
          <RouterLink v-if="objectHref(record.object_type, record.object_id)" class="c-link" :to="objectHref(record.object_type, record.object_id)!">{{ objectLabel(record.object_type) }} #{{ record.object_id }}</RouterLink>
          <span v-else>{{ objectLabel(record.object_type) }} #{{ record.object_id }}</span>
        </td>
      </tr>
    </tbody>
  </table>
  <ManagementPager v-if="resource.data.value" :total="resource.data.value.total" :page="resource.data.value.page" :size="resource.data.value.page_size" />
  </AdminPage>
</template>
