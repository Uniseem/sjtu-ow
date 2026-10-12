<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError, getApiAdminCategories } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import CategoryEditor from "../../components/content/CategoryEditor.vue"
import { useContentResource } from "./use-resource"
import { positiveID } from "./types"

const api = useAdminApi()
const route = useRoute()
const id = computed(() => positiveID(route.params.id))
const resource = useContentResource(async (signal) => {
  if (route.params.id === undefined) return { category: null }
  if (!id.value) throw new ApiError(404, "not_found", "找不到这个分类。")
  const result = await getApiAdminCategories(api, { signal })
  const category = result.items.find((item) => item?.id === id.value) ?? null
  if (!category) throw new ApiError(404, "not_found", "找不到这个分类。")
  return { category }
})
onMounted(() => { void resource.load() })
watch(() => route.params.id, () => { void resource.load() })
</script>
<template>
  <AdminPage :title="id ? resource.data.value?.category?.name || '未命名分类' : '新建分类'" section="content" back-href="/admin/categories/">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <CategoryEditor v-if="resource.data.value && !resource.pending.value" :key="id ?? 'new'" :category="resource.data.value.category" />
  </AdminPage>
</template>
