<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import PlainPageEditor from "../../components/content/PlainPageEditor.vue"
import { useContentResource } from "./use-resource"
import { readPlainPage } from "./pending"
import { positiveID } from "./types"
const api = useAdminApi()
const route = useRoute()
const id = computed(() => positiveID(route.params.id))
const resource = useContentResource(async (signal) => {
  if (!id.value) throw new ApiError(404, "not_found", "找不到这个页面。")
  return readPlainPage(api, id.value, { signal })
})
onMounted(() => { void resource.load() })
watch(() => route.params.id, () => { void resource.load() })
</script>
<template>
  <AdminPage :title="resource.data.value?.page.draft_title || resource.data.value?.page.title || '编辑页面'" section="content" back-href="/admin/pages/">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <PlainPageEditor v-if="resource.data.value && !resource.pending.value" :key="id ?? 'missing'" :detail="resource.data.value" />
  </AdminPage>
</template>
