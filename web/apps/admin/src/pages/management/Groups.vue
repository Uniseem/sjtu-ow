<script setup lang="ts">
import { getApiAdminMemberGroups } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import AdminPage from "../../components/AdminPage.vue"
import CEmpty from "@sjtu-ow/ui/CEmpty.vue"
import CIcon from "@sjtu-ow/ui/CIcon.vue"
import ResourceState from "../../components/management/ResourceState.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getApiAdminMemberGroups(api, { signal }))
</script>
<template>
  <AdminPage title="成员分组" section="成员">
    <template #actions>
      <RouterLink class="c-btn c-btn--primary c-btn--sm" to="/admin/member-groups/new/"><CIcon name="plus" />新建分组</RouterLink>
    </template>
    <p class="b-section__text">成员展示页上的分组，比如「社团干部」。组里的人照样在「全部成员」里。</p>
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <table v-if="resource.data.value?.groups.length" class="c-table c-table--stack">
      <thead>
        <tr>
          <th scope="col">名称</th>
          <th scope="col">显示</th>
          <th class="is-num">人数</th>
          <th class="is-num">排序</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="group in resource.data.value.groups" :key="group.id">
          <td>
            <RouterLink class="b-title" :to="`/admin/member-groups/${group.id}/`">{{ group.name || '（未命名分组）' }}</RouterLink>
            <span v-if="!group.name" class="b-sub">名称空着，成员展示页上不显示</span><span v-else-if="group.description" class="b-sub">{{ group.description }}</span>
          </td>
          <td data-label="显示">{{ group.is_visible ? '显示' : '不显示' }}</td>
          <td data-label="人数" class="is-num">{{ group.member_count }}</td>
          <td data-label="排序" class="is-num">{{ group.sort_order }}</td>
        </tr>
      </tbody>
    </table>
    <CEmpty v-else-if="!resource.pending.value && !resource.message.value" title="还没有分组" message="成员展示页只显示「全部成员」。" />
  </AdminPage>
</template>
