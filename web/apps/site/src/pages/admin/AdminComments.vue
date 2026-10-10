<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminComments, type GetApiAdminCommentsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const reviewSection = ADMIN_SECTIONS.find((s) => s.id === "review")
const loading = ref(true)
const comments = ref<GetApiAdminCommentsOut["comments"]>([])
const error = ref<string | null>(null)
const search = ref("")

async function loadComments() {
  loading.value = true
  try {
    const res = await getApiAdminComments(api)
    comments.value = res.comments
  } catch (err: any) {
    error.value = err?.message ?? "加载评论失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadComments()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="审核"
      title="评论管理"
      :tabs="reviewSection?.tabs"
      active-tab="comments"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="b-filters flex flex-wrap items-center gap-3 p-3 bg-surface border border-border rounded-lg">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="search"
            type="search"
            class="c-input w-full"
            placeholder="搜索评论正文..."
          />
        </div>
        <button class="c-btn c-btn--secondary c-btn--sm" @click="loadComments">刷新</button>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">评论正文</th>
              <th class="p-3 font-medium">作者</th>
              <th class="p-3 font-medium">所属文章</th>
              <th class="p-3 font-medium">状态</th>
              <th class="p-3 font-medium">时间</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取评论列表...</td>
            </tr>
            <tr v-else-if="comments.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无评论记录</td>
            </tr>
            <tr
              v-for="c in comments"
              v-else
              :key="c.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3 max-w-md text-sm text-fg">
                <p class="line-clamp-2">{{ c.content }}</p>
              </td>
              <td class="p-3 text-sm text-fg-2">{{ c.author_nickname }}</td>
              <td class="p-3 text-sm text-fg-2">
                <a :href="`/news/${c.article_slug}/`" target="_blank" class="hover:underline">
                  {{ c.article_title }}
                </a>
              </td>
              <td class="p-3 text-xs">
                <span v-if="c.is_pinned" class="inline-block px-1.5 py-0.5 rounded bg-accent-soft text-on-accent-soft mr-1">置顶</span>
                <span v-if="c.is_hidden" class="inline-block px-1.5 py-0.5 rounded bg-danger-soft text-on-danger-soft">已隐藏</span>
                <span v-if="!c.is_pinned && !c.is_hidden" class="text-fg-3">正常</span>
              </td>
              <td class="p-3 text-xs text-fg-3">{{ c.created_at }}</td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <button class="c-btn c-btn--ghost c-btn--xs">
                    {{ c.is_hidden ? '恢复' : '隐藏' }}
                  </button>
                  <button class="c-btn c-btn--ghost c-btn--xs">
                    {{ c.is_pinned ? '取消置顶' : '置顶' }}
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
