<script setup lang="ts">
import { formatContentTime } from "./types"
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { postApiArticlesIdUnpublish } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminAction } from "../../core/use-action"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import ContentPager from "../../components/content/ContentPager.vue"
import ContentActionMessage from "../../components/content/ContentActionMessage.vue"
import ConfirmContentAction from "../../components/content/ConfirmContentAction.vue"
import { useContentResource } from "./use-resource"
import { useContentPermissions } from "./permissions"
import { articleStatus, articleStatuses, positiveID, type Article } from "./types"
import { listContentArticles } from "./pending"

const api = useAdminApi()
const route = useRoute()
const router = useRouter()
const permission = useContentPermissions()
const query = ref(String(route.query.q ?? ""))
const category = ref(String(route.query.category ?? ""))
const status = ref(String(route.query.status ?? ""))
const mine = ref(route.query.mine === "1")
const confirmation = ref<Article | null>(null)
const resource = useContentResource((signal) => listContentArticles(api, {
  q: String(route.query.q ?? "").slice(0, 50),
  status: String(route.query.status ?? "") as "draft" | "live" | "changed" | "scheduled" | undefined,
  mine: route.query.mine === "1",
  category: String(route.query.category ?? ""),
  page: positiveID(route.query.page) ?? 1,
  page_size: 25,
}, { signal }))
const rows = computed(() => (resource.data.value?.items ?? []).filter((item): item is Article => item !== null))
const action = useAdminAction(
  (id: number, extras) => postApiArticlesIdUnpublish(api, id, extras),
  async () => { confirmation.value = null; await resource.load() },
)
function filter(): void {
  void router.push({ path: route.path, query: {
    ...(query.value.trim() ? { q: query.value.trim().slice(0, 50) } : {}),
    ...(category.value ? { category: category.value } : {}),
    ...(status.value ? { status: status.value } : {}),
    ...(mine.value ? { mine: "1" } : {}),
  } })
}
function unpublish(): void {
  if (!confirmation.value || !permission.canUnpublish(confirmation.value)) return
  void action.submit(confirmation.value.id)
}
watch(() => route.fullPath, () => {
  query.value = String(route.query.q ?? "")
  category.value = String(route.query.category ?? "")
  status.value = String(route.query.status ?? "")
  mine.value = route.query.mine === "1"
  void resource.load()
})
onMounted(() => { void resource.load() })
</script>
<template>
  <AdminPage title="文章" section="content">
    <template #actions><RouterLink v-if="permission.writeArticle.value" class="c-btn c-btn--primary c-btn--sm" to="/admin/articles/new/">写文章</RouterLink></template>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="query" class="c-input" type="search" name="q" maxlength="50" placeholder="搜标题" aria-label="搜标题">
      <select v-model="category" name="category" class="c-input" aria-label="分类" @change="filter">
        <option value="">全部分类</option>
        <option v-for="item in resource.data.value?.categories ?? []" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
      </select>
      <select v-model="status" name="status" class="c-input" aria-label="状态" @change="filter">
        <option value="">全部状态</option>
        <option v-for="(label, value) in articleStatuses" :key="value" :value="value">{{ label }}</option>
      </select>
      <label v-if="permission.everyArticle.value" class="c-check"><input v-model="mine" type="checkbox" name="mine" value="1" @change="filter">只看我的</label>
      <button class="c-btn c-btn--secondary c-btn--sm">筛选</button>
    </form>
    <ContentLoad :pending="resource.pending.value" :message="resource.message.value" :status="resource.status.value" @retry="resource.load" />
    <ContentActionMessage :message="action.message.value" :uncertain="action.uncertain.value" :pending="action.pending.value" @retry="action.retry" />
    <ConfirmContentAction v-if="confirmation" :title="`撤下「${confirmation.title}」？`" description="撤下后变回草稿，访客看不到。" :pending="action.pending.value" @confirm="unpublish" @cancel="confirmation = null" />
    <table v-if="rows.length" class="c-table c-table--stack">
      <thead><tr><th>标题</th><th>分类</th><th>作者</th><th>状态</th><th>最后改动</th><th><span class="sr-only">操作</span></th></tr></thead>
      <tbody>
        <tr v-for="item in rows" :key="item.id" :data-article-row="item.id">
          <td><RouterLink class="b-title" :to="`/admin/articles/${item.id}/`">{{ (item.draft_title ?? item.title) || '（无标题）' }}</RouterLink></td>
          <td data-label="分类">{{ item.category_name || '未选分类' }}</td>
          <td data-label="作者">{{ item.author_name || '—' }}</td>
          <td data-label="状态"><span class="c-status">{{ articleStatuses[articleStatus(item)] }}</span></td>
          <td data-label="最后改动"><time :datetime="item.updated_at">{{ formatContentTime(item.updated_at) }}</time></td>
          <td><div class="b-rowacts">
            <RouterLink v-if="permission.canEdit(item)" class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/articles/${item.id}/`">编辑</RouterLink>
            <a v-if="item.live" class="c-btn c-btn--quiet c-btn--sm" :href="`/news/${encodeURIComponent(item.slug)}/`" target="_blank" rel="noopener">看文章</a>
            <RouterLink v-if="permission.everyArticle.value && (item.live || item.go_live_at)" class="c-btn c-btn--quiet c-btn--sm" :to="`/admin/announce/article/${item.id}/`">{{ item.live ? '通知全体成员' : '上线时通知全体成员' }}</RouterLink>
            <button v-if="permission.canUnpublish(item)" type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="!action.canStart.value" @click="confirmation = item">撤下</button>
          </div></td>
        </tr>
      </tbody>
    </table>
    <section v-else-if="resource.data.value" class="c-empty">
      <h2 class="c-empty__title">没有文章</h2>
      <p>换个筛选条件，或者写一篇。</p>
      <RouterLink v-if="permission.writeArticle.value" class="c-btn c-btn--primary" to="/admin/articles/new/">写文章</RouterLink>
    </section>
    <ContentPager v-if="resource.data.value" :page="resource.data.value.page" :total="resource.data.value.total" :page-size="resource.data.value.page_size" :pending="resource.pending.value" />
  </AdminPage>
</template>
