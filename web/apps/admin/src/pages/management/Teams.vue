<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminTeams } from "@sjtu-ow/api"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import { useResource } from "./use-resource"
import { useAdminApi } from "../../core/api"
import { text } from "./format"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const search = ref(text(route.query.q))
const stopped = ref(route.query.captain_inactive === "1")
const resource = useResource(() => route.fullPath, signal => getApiAdminTeams(api, { signal }))
const rows = computed(() => (resource.data.value?.teams ?? []).filter(team => team.name.toLocaleLowerCase().includes(text(route.query.q).toLocaleLowerCase()) && (route.query.captain_inactive !== "1" || (!team.captain_active && !team.disbanded_at))))
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, captain_inactive: stopped.value ? "1" : undefined } }) }
</script>
<template>
  <AdminPage title="战队" section="成员">
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" placeholder="搜队名" aria-label="搜队名" />
      <label class="c-check">
        <input v-model="stopped" type="checkbox" />队长已停用</label>
        <button type="submit" class="c-btn c-btn--secondary c-btn--sm">筛选</button>
      </form>
      <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!rows.length" empty-text="没有符合条件的战队。" @retry="resource.refresh" />
      <table v-if="rows.length" class="c-table">
        <thead>
          <tr>
            <th scope="col">队名</th>
            <th scope="col">队长</th>
            <th scope="col">人数</th>
            <th scope="col">招募</th>
            <th scope="col">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="team in rows" :key="team.id">
            <td>
              <RouterLink class="b-title" :to="`/admin/teams/edit/${team.id}/`">{{ team.name }}</RouterLink>
            </td>
            <td>{{ team.captain_name || '无队长' }}</td>
            <td>{{ team.member_count }}</td>
            <td>{{ team.is_recruiting ? '招募中' : '暂不招募' }}</td>
            <td>{{ team.disbanded_at ? '已解散' : !team.captain_active ? '队长已停用' : '正常' }}</td>
          </tr>
        </tbody>
      </table>
    </AdminPage>
</template>
