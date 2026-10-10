<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminScrims, type GetApiAdminScrimsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const eventsSection = ADMIN_SECTIONS.find((s) => s.id === "events")
const loading = ref(true)
const scrims = ref<GetApiAdminScrimsOut["scrims"]>([])
const error = ref<string | null>(null)

async function loadScrims() {
  loading.value = true
  try {
    const res = await getApiAdminScrims(api)
    scrims.value = res.scrims
  } catch (err: any) {
    error.value = err?.message ?? "加载内战列表失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadScrims()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="活动"
      title="内战管理"
      :tabs="eventsSection?.tabs"
      active-tab="scrims"
    >
      <template #actions>
        <a href="/admin/scrims/new/" class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="plus" class="size-4 mr-1" /> 新建内战
        </a>
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
              <th class="p-3 font-medium">标题</th>
              <th class="p-3 font-medium">模式规格</th>
              <th class="p-3 font-medium">状态</th>
              <th class="p-3 font-medium">开赛时间</th>
              <th class="p-3 font-medium">报名人数</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取内战列表...</td>
            </tr>
            <tr v-else-if="scrims.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无内战记录</td>
            </tr>
            <tr
              v-for="s in scrims"
              v-else
              :key="s.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3">
                <a :href="`/admin/scrims/${s.id}/`" class="font-bold text-fg hover:underline">
                  {{ s.title }}
                </a>
              </td>
              <td class="p-3 text-sm text-fg-2">
                {{ s.format === '5v5' ? '5v5 标准模式' : '6v6 怀旧模式' }}
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="{
                    'bg-success-soft text-on-success-soft': s.status === 'published',
                    'bg-warning-soft text-on-warning-soft': s.status === 'draft',
                    'bg-surface-2 text-fg-3': s.status === 'finished' || s.status === 'cancelled',
                  }"
                >
                  {{ s.status === 'published' ? '报名中' : s.status === 'finished' ? '已结束' : s.status === 'cancelled' ? '已取消' : '草稿' }}
                </span>
              </td>
              <td class="p-3 text-xs text-fg-3">
                {{ s.start_time || "未设定" }}
              </td>
              <td class="p-3 text-sm text-fg-2">
                {{ s.signup_count }} 人
              </td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <a :href="`/admin/scrims/${s.id}/split/`" class="c-btn c-btn--ghost c-btn--xs">分队</a>
                  <a :href="`/admin/scrims/${s.id}/`" class="c-btn c-btn--ghost c-btn--xs">编辑</a>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
