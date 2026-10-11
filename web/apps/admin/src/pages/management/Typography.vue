<script setup lang="ts">
import { getTypography } from "./pending"
import { useAdminApi } from "../../core/api"
import { useResource } from "./use-resource"
import AdminPage from "../../components/AdminPage.vue"
import ResourceState from "../../components/management/ResourceState.vue"
import TypographyEditor from "../../components/management/TypographyEditor.vue"
const api = useAdminApi()
const resource = useResource(() => true, signal => getTypography(api, { signal }))
</script>
<template>
  <AdminPage title="排版设置" section="设置">
    <ResourceState :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.refresh" />
    <TypographyEditor v-if="resource.data.value" :key="resource.data.value.version" :data="resource.data.value" />
  </AdminPage>
</template>
