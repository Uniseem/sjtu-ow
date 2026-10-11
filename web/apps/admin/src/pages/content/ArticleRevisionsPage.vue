<script setup lang="ts">
import { formatContentTime } from "./types"
import { computed, onMounted, watch } from "vue"
import { useRoute } from "vue-router"
import { ApiError } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import { useContentResource } from "./use-resource"
import { readArticleRevisions, readArticleEditor } from "./pending"
import { positiveID } from "./types"
const api = useAdminApi()
const route = useRoute()
const id = computed(() => positiveID(route.params.id))
const resource = useContentResource(async (signal) => {
  if (!id.value) throw new ApiError(404, "not_found", "找不到这篇文章。")
  const article = await readArticleEditor(api, id.value, { signal })
  const revisions = await readArticleRevisions(api, id.value, { signal })
  return { article, revisions }
})
onMounted(() => { void resource.load() })
watch(() => route.params.id, () => { void resource.load() })
</script>
<template>
  <AdminPage title="文章修订" section="content" :back-href="`/admin/articles/${id}/`">
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <template v-if="resource.data.value">
      <section class="b-section">
        <h2 class="b-section__title">{{ resource.data.value.article.article?.title || '（无标题）' }}</h2>
        <p class="b-section__text">这里只列出新站中实际保存的修订。旧站没有迁入的历史仍保留在旧库存档。</p>
        <p v-if="resource.data.value.revisions.has_unpublished_changes" class="b-sub">最新草稿里有改动还没发布。</p>
      </section>
      <table v-if="resource.data.value.revisions.items.length" class="c-table c-table--stack">
        <thead><tr><th>修订</th><th>保存人</th><th>保存时间</th><th>状态</th><th><span class="sr-only">操作</span></th></tr></thead>
        <tbody>
          <tr v-for="revision in resource.data.value.revisions.items" :key="revision.id">
            <td><RouterLink class="b-title" :to="`/admin/articles/${id}/revisions/${revision.id}/`">{{ revision.title || '（无标题）' }}</RouterLink></td>
            <td data-label="保存人">{{ revision.user_name || '—' }}</td>
            <td data-label="保存时间">{{ formatContentTime(revision.created_at) }}</td>
            <td data-label="状态"><span v-if="revision.latest" class="c-status">最新草稿</span><span v-if="revision.live" class="c-status">线上版本</span><span v-if="revision.scheduled" class="c-status">定时上线</span></td>
            <td><RouterLink class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/articles/${id}/revisions/${revision.id}/`">查看</RouterLink></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="b-section__text">还没有修订。</p>
    </template>
  </AdminPage>
</template>
