<script setup lang="ts">
import { computed, onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import { useContentResource } from "./use-resource"
import { readArticleEditor } from "./pending"
import { contentPreviewURL } from "./preview-url"
import { positiveID } from "./types"
const api = useAdminApi()
const route = useRoute()
const id = computed(() => positiveID(route.params.id))
const resource = useContentResource(async (signal) => {
  if (!id.value) throw new ApiError(404, "not_found", "找不到这篇文章。")
  return readArticleEditor(api, id.value, { signal })
})
const url = computed(() => contentPreviewURL(resource.data.value?.preview_url))
onMounted(() => { void resource.load() })
watch(() => route.params.id, () => { void resource.load() })
</script>
<template>
  <AdminPage title="预览草稿" section="content" :back-href="`/admin/articles/${id}/`">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <template v-if="resource.data.value">
      <p class="c-notice c-notice--info">这是最新保存的草稿，只有能编辑这篇文章的人可以打开。未保存的改动不会出现在这里。</p>
      <a v-if="url" class="c-btn c-btn--secondary" :href="url" target="_blank" rel="noopener">新窗口打开预览</a>
      <iframe v-if="url" :src="url" class="w-full min-h-96 border-0" title="文章草稿预览" sandbox="allow-same-origin" />
      <p v-else class="b-section__text">预览地址暂不可用，请稍后再试。</p>
    </template>
  </AdminPage>
</template>
