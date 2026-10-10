<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminCategories, type GetApiAdminCategoriesOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const contentSection = ADMIN_SECTIONS.find((s) => s.id === "content")
const loading = ref(true)
const categories = ref<GetApiAdminCategoriesOut["categories"]>([])
const error = ref<string | null>(null)

async function loadCategories() {
  loading.value = true
  try {
    const res = await getApiAdminCategories(api)
    categories.value = res.categories
  } catch (err: any) {
    error.value = err?.message ?? "加载分类失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadCategories()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="内容"
      title="分类管理"
      :tabs="contentSection?.tabs"
      active-tab="categories"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="plus" class="size-4 mr-1" /> 新建分类
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">名称</th>
              <th class="p-3 font-medium">网址标识 (Slug)</th>
              <th class="p-3 font-medium">排序权重</th>
              <th class="p-3 font-medium">开放投稿</th>
              <th class="p-3 font-medium">文章数</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取分类列表...</td>
            </tr>
            <tr v-else-if="categories.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无文章分类</td>
            </tr>
            <tr
              v-for="cat in categories"
              v-else
              :key="cat.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3 font-bold text-fg">{{ cat.name }}</td>
              <td class="p-3 font-mono text-xs text-fg-2">{{ cat.slug }}</td>
              <td class="p-3 text-sm text-fg-2">{{ cat.sort_order }}</td>
              <td class="p-3 text-sm">
                <span :class="cat.allow_submissions ? 'text-success' : 'text-fg-3'">
                  {{ cat.allow_submissions ? '开放' : '关闭' }}
                </span>
              </td>
              <td class="p-3 text-sm text-fg-2">{{ cat.article_count }}</td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <button class="c-btn c-btn--ghost c-btn--xs">编辑</button>
                  <button v-if="cat.article_count === 0" class="c-btn c-btn--ghost c-btn--xs text-danger">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
