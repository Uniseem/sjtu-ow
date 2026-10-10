<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminActivity, type GetApiAdminActivityOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const dataSection = ADMIN_SECTIONS.find((s) => s.id === "data")
const loading = ref(true)
const activity = ref<GetApiAdminActivityOut | null>(null)
const error = ref<string | null>(null)

async function loadActivity() {
  loading.value = true
  try {
    const res = await getApiAdminActivity(api)
    activity.value = res
  } catch (err: any) {
    error.value = err?.message ?? "加载活动数据失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadActivity()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="数据"
      title="活动数据统计"
      :tabs="dataSection?.tabs"
      active-tab="activity"
    >
      <template #actions>
        <a href="/api/admin/activity/export" download class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="download" class="size-4 mr-1" /> 导出 CSV 表格
        </a>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <!-- 宏观指标卡片 -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div class="p-5 rounded-lg bg-surface border border-border shadow-xs">
          <p class="text-xs text-fg-3 font-medium">内战总场次</p>
          <p class="text-2xl font-bold text-fg mt-2">
            {{ activity?.summary?.total_scrims ?? 0 }}
          </p>
        </div>
        <div class="p-5 rounded-lg bg-surface border border-border shadow-xs">
          <p class="text-xs text-fg-3 font-medium">赛事总场次</p>
          <p class="text-2xl font-bold text-fg mt-2">
            {{ activity?.summary?.total_tournaments ?? 0 }}
          </p>
        </div>
        <div class="p-5 rounded-lg bg-surface border border-border shadow-xs">
          <p class="text-xs text-fg-3 font-medium">参赛总人次</p>
          <p class="text-2xl font-bold text-fg mt-2">
            {{ activity?.summary?.total_participants ?? 0 }}
          </p>
        </div>
        <div class="p-5 rounded-lg bg-surface border border-border shadow-xs">
          <p class="text-xs text-fg-3 font-medium">当前活跃成员</p>
          <p class="text-2xl font-bold text-fg mt-2">
            {{ activity?.summary?.active_members ?? 0 }}
          </p>
        </div>
      </div>

      <!-- 逐场事件列表 -->
      <div class="bg-surface border border-border rounded-lg overflow-x-auto mt-6">
        <div class="p-4 border-b border-border flex justify-between items-center">
          <h2 class="font-bold text-sm text-fg">逐场活动事件明细</h2>
          <span class="text-xs text-fg-3">支持导出为 UTF-8 BOM 编码的 Excel 兼容文件</span>
        </div>

        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">类型</th>
              <th class="p-3 font-medium">活动标题</th>
              <th class="p-3 font-medium">开赛时间</th>
              <th class="p-3 font-medium">规格</th>
              <th class="p-3 font-medium text-right">参与人数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">正在拉取活动事件...</td>
            </tr>
            <tr v-else-if="!activity?.events?.length" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">该学年内暂无活动数据记录</td>
            </tr>
            <tr
              v-for="e in (activity?.events ?? [])"
              v-else
              :key="`${e.kind}-${e.id}`"
              class="border-b border-border hover:bg-surface-2 transition-colors text-sm"
            >
              <td class="p-3 font-semibold text-fg">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="e.kind === 'scrim' ? 'bg-primary-soft text-on-primary-soft' : 'bg-accent-soft text-on-accent-soft'"
                >
                  {{ e.kind === 'scrim' ? '内战' : '赛事' }}
                </span>
              </td>
              <td class="p-3 font-bold text-fg">{{ e.title }}</td>
              <td class="p-3 text-xs text-fg-3">{{ e.start_time }}</td>
              <td class="p-3 text-xs text-fg-2">{{ e.format_label }}</td>
              <td class="p-3 text-right font-medium text-fg">{{ e.participant_count }} 人</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
