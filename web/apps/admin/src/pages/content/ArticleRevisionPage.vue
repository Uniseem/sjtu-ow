<script setup lang="ts">
import { formatContentTime } from "./types"
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ContentActionMessage from "../../components/content/ContentActionMessage.vue"
import ConfirmContentAction from "../../components/content/ConfirmContentAction.vue"
import RevisionComparison from "../../components/content/RevisionComparison.vue"
import MarkdownPreview from "../../components/content/MarkdownPreview.vue"
import { useContentResource } from "./use-resource"
import { readArticleRevision, readArticleEditor, restoreArticleRevision } from "./pending"
import { draftFromArticle, emptyArticle, positiveID } from "./types"
import { contentPreviewURL } from "./preview-url"
const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const id = computed(() => positiveID(route.params.id))
const revisionID = computed(() => positiveID(route.params.revision))
const confirmation = ref(false)
const resource = useContentResource(async (signal) => {
  if (!id.value || !revisionID.value) throw new ApiError(404, "not_found", "找不到这份修订。")
  const revision = await readArticleRevision(api, id.value, revisionID.value, { signal })
  const current = await readArticleEditor(api, id.value, { signal })
  return { revision, current }
})
const latest = computed(() => resource.data.value?.current.revision ?? (
  resource.data.value?.current.article ? draftFromArticle(resource.data.value.current.article) : emptyArticle()
))
const preview = computed(() => contentPreviewURL(resource.data.value?.revision.preview_url))
const restore = useAdminAction(
  async (version: number, extras) => {
    if (!id.value || !revisionID.value) throw new ApiError(404, "not_found", "找不到这份修订。")
    return restoreArticleRevision(api, id.value, revisionID.value, version, extras)
  },
  async () => { await router.push(`/admin/articles/${id.value}/`) },
)
function restored(): void {
  if (!resource.data.value?.revision.can_restore || !restore.canStart.value) return
  void restore.submit(resource.data.value.current.version)
}
onMounted(() => { void resource.load() })
watch(() => route.fullPath, () => { confirmation.value = false; void resource.load() })
</script>
<template>
  <AdminPage title="查看修订" section="content" :back-href="`/admin/articles/${id}/revisions/`">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <ContentActionMessage :message="restore.message.value" :pending="restore.pending.value" :uncertain="restore.uncertain.value" @retry="restore.retry" />
    <template v-if="resource.data.value">
      <section class="b-section">
        <h2 class="b-section__title">{{ resource.data.value.revision.revision.title || '（无标题）' }}</h2>
        <dl class="b-kv"><dt>保存人</dt><dd>{{ resource.data.value.revision.revision.user_name || '—' }}</dd><dt>保存时间</dt><dd>{{ formatContentTime(resource.data.value.revision.revision.created_at) }}</dd></dl>
        <div class="b-actions">
          <a v-if="preview" class="c-btn c-btn--secondary" :href="preview" target="_blank" rel="noopener">预览这份修订</a>
          <button v-if="resource.data.value.revision.can_restore && !resource.data.value.revision.revision.latest" type="button" class="c-btn c-btn--primary" :disabled="!restore.canStart.value" @click="confirmation = true">恢复成草稿</button>
        </div>
      </section>
      <ConfirmContentAction v-if="confirmation" title="恢复这份修订？" description="恢复会创建新的草稿，网站上的文章保持上次发布的样子。编辑后再点「发布」才上线。" :pending="restore.pending.value" @confirm="restored" @cancel="confirmation = false" />
      <RevisionComparison :before="resource.data.value.revision.draft" :after="latest" />
      <MarkdownPreview :body="resource.data.value.revision.draft.body_md" open />
    </template>
  </AdminPage>
</template>
