<script setup lang="ts">
import { useRoute } from "vue-router"
import { getApiAdminMemberGroupsId } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import GroupEditor from "../../components/management/GroupEditor.vue"
const api = useAdminApi()
const route = useRoute()
const resource = useResource(() => route.params.id, signal => getApiAdminMemberGroupsId(api, String(route.params.id), { signal }))
</script>
<template>
  <AdminPage :title="resource.data.value?.group.name || '（未命名分组）'" section="成员" back-href="/admin/member-groups/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <GroupEditor v-if="resource.data.value" :key="resource.data.value.group.id" :data="resource.data.value" />
  </AdminPage>
</template>
