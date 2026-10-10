<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminModeration, type GetApiAdminModerationOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const reviewSection = ADMIN_SECTIONS.find((s) => s.id === "review")
const loading = ref(true)
const items = ref<GetApiAdminModerationOut["items"]>([])
const error = ref<string | null>(null)

async function loadItems() {
  loading.value = true
  try {
    const res = await getApiAdminModeration(api)
    items.value = res.items
  } catch (err: any) {
    error.value = err?.message ?? "加载审核记录失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadItems()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="审核"
      title="内容巡查与审核"
      :tabs="reviewSection?.tabs"
      active-tab="moderation"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">内容类型</th>
              <th class="p-3 font-medium">作者 / 提交人</th>
              <th class="p-3 font-medium">可疑文本摘要</th>
              <th class="p-3 font-medium">AI 风险判定</th>
              <th class="p-3 font-medium">处置状态</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取审核记录...</td>
            </tr>
            <tr v-else-if="items.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无可疑或待复核内容</td>
            </tr>
            <tr
              v-for="item in items"
              v-else
              :key="item.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3 font-bold text-fg">{{ item.content_type }}</td>
              <td class="p-3 text-sm text-fg-2">{{ item.author_nickname }}</td>
              <td class="p-3 text-xs text-fg-2 max-w-xs truncate">{{ item.snippet }}</td>
              <td class="p-3 text-sm">
                <span class="text-danger font-semibold">{{ item.ai_judgment }}</span>
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="item.handled_at ? 'bg-success-soft text-on-success-soft' : 'bg-warning-soft text-on-warning-soft'"
                >
                  {{ item.handled_at ? '已处置' : '待复核' }}
                </span>
              </td>
              <td class="p-3 text-right">
                <button class="c-btn c-btn--ghost c-btn--xs">复核详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
