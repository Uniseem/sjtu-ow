<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminArticles, type GetApiAdminArticlesOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const contentSection = ADMIN_SECTIONS.find((s) => s.id === "content")
const loading = ref(true)
const articles = ref<GetApiAdminArticlesOut["articles"]>([])
const error = ref<string | null>(null)
const search = ref("")
const selectedStatus = ref("")

async function loadArticles() {
  loading.value = true
  try {
    const res = await getApiAdminArticles()
    articles.value = res.articles
  } catch (err: any) {
    error.value = err?.message ?? "加载文章失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadArticles()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="内容"
      title="文章管理"
      :tabs="contentSection?.tabs"
      active-tab="articles"
    >
      <template #actions>
        <a href="/admin/articles/new/" class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="plus" class="size-4 mr-1" /> 写文章
        </a>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <!-- 筛选栏 b-filters -->
      <div class="b-filters flex flex-wrap items-center gap-3 p-3 bg-surface border border-border rounded-lg">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="search"
            type="search"
            class="c-input w-full"
            placeholder="搜标题或摘要..."
          />
        </div>
        <select v-model="selectedStatus" class="c-input">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="published">已发布</option>
          <option value="scheduled">定时上线</option>
        </select>
        <button class="c-btn c-btn--secondary c-btn--sm" @click="loadArticles">刷新</button>
      </div>

      <!-- 表格 -->
      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">标题</th>
              <th class="p-3 font-medium">分类</th>
              <th class="p-3 font-medium">状态</th>
              <th class="p-3 font-medium">更新时间</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">正在拉取文章列表...</td>
            </tr>
            <tr v-else-if="articles.length === 0" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">暂无文章记录</td>
            </tr>
            <tr
              v-for="art in articles"
              v-else
              :key="art.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3">
                <a :href="`/admin/articles/${art.id}/`" class="font-bold text-fg hover:underline">
                  {{ art.title || "（无标题）" }}
                </a>
                <p v-if="art.slug" class="text-xs text-fg-3">/news/{{ art.slug }}/</p>
              </td>
              <td class="p-3 text-sm text-fg-2">
                {{ art.category_name || "未分类" }}
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="{
                    'bg-success-soft text-on-success-soft': art.status === 'published',
                    'bg-warning-soft text-on-warning-soft': art.status === 'draft',
                    'bg-primary-soft text-on-primary-soft': art.status === 'scheduled',
                  }"
                >
                  {{ art.status === 'published' ? '已发布' : art.status === 'scheduled' ? '定时上线' : '草稿' }}
                </span>
              </td>
              <td class="p-3 text-xs text-fg-3">
                {{ art.updated_at }}
              </td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <a :href="`/admin/articles/${art.id}/`" class="c-btn c-btn--ghost c-btn--xs">编辑</a>
                  <a v-if="art.status === 'published'" :href="`/news/${art.slug}/`" target="_blank" class="c-btn c-btn--ghost c-btn--xs">预览</a>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
