<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ArticleEditor from "../../components/content/ArticleEditor.vue"
import { useAdminApi } from "../../core/api"
import { useContentResource } from "./use-resource"
import { readArticleEditor, readNewArticleEditor } from "./pending"
import { positiveID } from "./types"
const api = useAdminApi()
const route = useRoute()
const id = computed(() => route.params.id === undefined ? null : positiveID(route.params.id))
const retainedCreationID = ref<number | null>(null)
const retainingCreation = computed(() => retainedCreationID.value !== null && retainedCreationID.value === id.value)
const editorKey = computed(() => retainingCreation.value ? "new" : id.value ?? "new")
const resource = useContentResource(async (signal) => {
  if (route.params.id !== undefined && id.value === null) throw new ApiError(404, "not_found", "找不到这篇文章。")
  const detail = id.value ? await readArticleEditor(api, id.value, { signal }) : await readNewArticleEditor(api, { signal })
  if (id.value && !detail?.article) throw new ApiError(404, "not_found", "找不到这篇文章。")
  return { detail, categories: detail.categories }
})
onMounted(() => { void resource.load() })
watch(() => route.fullPath, () => {
  if (!retainingCreation.value) retainedCreationID.value = null
  void resource.load()
})
</script>
<template>
  <AdminPage :title="id ? (resource.data.value?.detail.revision?.title || resource.data.value?.detail.article?.title || '（无标题）') : '写文章'" section="content" back-href="/admin/articles/">
    <ContentLoad :pending="resource.pending.value && !retainingCreation" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <ArticleEditor v-if="resource.data.value && (!resource.pending.value || retainingCreation)" :key="editorKey" :detail="resource.data.value.detail" :categories="resource.data.value.categories" @created="retainedCreationID = $event" />
  </AdminPage>
</template>
