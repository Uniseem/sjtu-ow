<script setup lang="ts">
import { getApiAdminSettings } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import SettingsEditor from "../../components/management/SettingsEditor.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getApiAdminSettings(api, { signal }))
</script>
<template>
  <AdminPage title="全站设置" section="设置">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <SettingsEditor v-if="resource.data.value?.settings" :key="resource.data.value.settings.id" :settings="resource.data.value.settings" />
  </AdminPage>
</template>
