<script setup lang="ts">
import { useRoute } from "vue-router"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import TeamEditor from "../../components/management/TeamEditor.vue"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import { getTeamAdmin } from "./pending"
const api = useAdminApi()
const route = useRoute()
const resource = useResource(() => route.params.id, signal => getTeamAdmin(api, String(route.params.id), { signal }))
</script>
<template>
  <AdminPage :title="resource.data.value?.team?.name || '战队'" section="成员" back-href="/admin/teams/">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <TeamEditor v-if="resource.data.value?.team" :key="`${resource.data.value.team.id}:${resource.data.value.team.updated_at}:${resource.data.value.team.disbanded_at}`" :data="resource.data.value" @changed="resource.refresh" />
  </AdminPage>
</template>
