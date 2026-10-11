<script setup lang="ts">
import { getApiAdminMemberGroups } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getApiAdminMemberGroups(api, { signal }))
</script>
<template>
  <AdminPage title="成员分组" section="成员">
    <template #actions>
      <RouterLink class="c-btn c-btn--primary c-btn--sm" to="/admin/member-groups/new/">新建分组</RouterLink>
    </template>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" :empty="!resource.data.value?.groups.length" empty-text="还没有成员分组。" @retry="resource.refresh" />
    <table v-if="resource.data.value?.groups.length" class="c-table">
      <thead>
        <tr>
          <th scope="col">名称</th>
          <th scope="col">是否显示</th>
          <th scope="col">人数</th>
          <th scope="col">排序</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="group in resource.data.value.groups" :key="group.id">
          <td>
            <RouterLink class="b-title" :to="`/admin/member-groups/${group.id}/`">{{ group.name || '（未命名分组）' }}</RouterLink>
            <span v-if="!group.name" class="b-sub">网站上不显示</span>
          </td>
          <td>{{ group.is_visible && group.name ? '显示' : '不显示' }}</td>
          <td>{{ group.member_count }}</td>
          <td>{{ group.sort_order }}</td>
        </tr>
      </tbody>
    </table>
  </AdminPage>
</template>
