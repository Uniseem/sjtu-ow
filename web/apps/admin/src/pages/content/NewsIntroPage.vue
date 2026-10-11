<script setup lang="ts">
import { onMounted } from "vue"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import NewsIntroEditor from "../../components/content/NewsIntroEditor.vue"
import { useContentResource } from "./use-resource"
import { readNewsDraft } from "./pending"
const api = useAdminApi()
const resource = useContentResource((signal) => readNewsDraft(api, { signal }))
onMounted(() => { void resource.load() })
</script>
<template>
  <AdminPage title="资讯栏目的介绍" section="content" back-href="/admin/pages/">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <NewsIntroEditor v-if="resource.data.value && !resource.pending.value" :key="resource.data.value.version" :detail="resource.data.value" />
  </AdminPage>
</template>
