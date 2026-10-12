<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getApiAdminTeams } from "@sjtu-ow/api"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import ManagementPager from "../../components/management/ManagementPager.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CStatus from "@sjtu-ow/ui/CStatus.vue"
import { useResource } from "./use-resource"
import { useAdminApi } from "../../core/api"
import { positive, text } from "./format"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const search = ref(text(route.query.q))
const stopped = ref(route.query.captain === "gone" || route.query.captain_inactive === "1")
const resource = useResource(() => route.fullPath, signal => getApiAdminTeams(api, { signal }))
const filtered = computed(() => (resource.data.value?.teams ?? []).filter(team => team.name.toLocaleLowerCase().includes(text(route.query.q).toLocaleLowerCase()) && (!(route.query.captain === "gone" || route.query.captain_inactive === "1") || (!team.captain_active && !team.disbanded_at))))
const rows = computed(() => filtered.value.slice((positive(route.query.page) - 1) * 50, positive(route.query.page) * 50))
function filter() { void router.push({ path: route.path, query: { q: search.value || undefined, captain: stopped.value ? "gone" : undefined } }) }
</script>
<template>
  <AdminPage title="战队" section="成员">
    <form method="get" class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" name="q" maxlength="50" placeholder="搜队名" aria-label="搜队名" />
      <label class="c-check"><input v-model="stopped" type="checkbox" name="captain" value="gone" @change="filter" />只看队长已停用的</label>
      <button type="submit" class="c-btn c-btn--secondary c-btn--sm">筛选</button>
    </form>
    <p class="b-section__text">战队由队长在网站上建，结束时解散；后台只改资料、指定队长和解散。</p>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <table v-if="rows.length" class="c-table c-table--stack">
      <thead><tr><th>队名</th><th>队长</th><th class="is-num">人数</th><th>招募</th><th>状态</th><th><span class="sr-only">操作</span></th></tr></thead>
      <tbody>
        <tr v-for="team in rows" :key="team.id" :data-team-row="team.id">
          <td><RouterLink class="b-title" :to="`/admin/teams/edit/${team.id}/`">{{ team.name }}</RouterLink></td>
          <td data-label="队长">{{ team.captain_name }}</td>
          <td data-label="人数" class="is-num">{{ team.member_count }}</td>
          <td data-label="招募">{{ team.is_recruiting && !team.disbanded_at ? '招募中' : '—' }}</td>
          <td data-label="状态"><CStatus :label="team.disbanded_at ? '已解散' : !team.captain_active ? '队长已停用' : '正常'" :kind="team.disbanded_at ? 'off' : !team.captain_active ? 'warn' : 'ok'" /></td>
          <td><div class="b-rowacts"><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/teams/edit/${team.id}/`">编辑</RouterLink><a v-if="!team.disbanded_at" class="c-btn c-btn--quiet c-btn--sm" :href="`/admin/teams/${team.id}/assign-captain/`">指定队长</a></div></td>
        </tr>
      </tbody>
    </table>
    <CEmpty v-else-if="!resource.pending.value && !resource.message.value" title="没有战队" message="换个筛选条件试试。" />
    <ManagementPager v-if="resource.data.value" :page="positive(route.query.page)" :size="50" :total="filtered.length" />
  </AdminPage>
</template>
