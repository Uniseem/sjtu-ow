<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminImageCollections, getApiImagesId } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ImageEditor from "../../components/content/ImageEditor.vue"
import { useContentResource } from "./use-resource"
import { positiveID } from "./types"
const api = useAdminApi()
const route = useRoute()
const id = computed(() => positiveID(route.params.id))
const resource = useContentResource(async (signal) => {
  if (!id.value) throw new ApiError(404, "not_found", "找不到这张图片。")
  const image = await getApiImagesId(api, id.value, { signal })
  const collections = await getApiAdminImageCollections(api, { signal })
  return { image, collections: collections.collections }
})
onMounted(() => { void resource.load() })
watch(() => route.params.id, () => { void resource.load() })
</script>
<template>
  <AdminPage title="编辑图片" section="content" back-href="/admin/images/">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <ImageEditor v-if="resource.data.value && !resource.pending.value" :key="id ?? 'missing'" :image="resource.data.value.image" :collections="resource.data.value.collections" />
  </AdminPage>
</template>
