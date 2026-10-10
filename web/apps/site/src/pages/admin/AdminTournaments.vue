<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminTournaments, type GetApiAdminTournamentsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const eventsSection = ADMIN_SECTIONS.find((s) => s.id === "events")
const loading = ref(true)
const tournaments = ref<GetApiAdminTournamentsOut["tournaments"]>([])
const error = ref<string | null>(null)

async function loadTournaments() {
  loading.value = true
  try {
    const res = await getApiAdminTournaments(api)
    tournaments.value = res.tournaments
  } catch (err: any) {
    error.value = err?.message ?? "加载赛事失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTournaments()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="活动"
      title="赛事管理"
      :tabs="eventsSection?.tabs"
      active-tab="tournaments"
    >
      <template #actions>
        <a href="/admin/tournaments/new/" class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="plus" class="size-4 mr-1" /> 新建赛事
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
              <th class="p-3 font-medium">赛事名称</th>
              <th class="p-3 font-medium">赛制模式</th>
              <th class="p-3 font-medium">状态</th>
              <th class="p-3 font-medium">开赛时间</th>
              <th class="p-3 font-medium">已报名</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取赛事列表...</td>
            </tr>
            <tr v-else-if="tournaments.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无赛事记录</td>
            </tr>
            <tr
              v-for="t in tournaments"
              v-else
              :key="t.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3">
                <a :href="`/admin/tournaments/${t.id}/`" class="font-bold text-fg hover:underline">
                  {{ t.title }}
                </a>
              </td>
              <td class="p-3 text-sm text-fg-2">
                {{ t.mode === 'team' ? '整队报名' : '个人报名' }}
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="{
                    'bg-success-soft text-on-success-soft': t.status === 'published',
                    'bg-warning-soft text-on-warning-soft': t.status === 'draft',
                    'bg-surface-2 text-fg-3': t.status === 'finished' || t.status === 'cancelled',
                  }"
                >
                  {{ t.status === 'published' ? '报名进行中' : t.status === 'finished' ? '已完赛' : t.status === 'cancelled' ? '已取消' : '草稿' }}
                </span>
              </td>
              <td class="p-3 text-xs text-fg-3">
                {{ t.start_time || "未设定" }}
              </td>
              <td class="p-3 text-sm text-fg-2">
                {{ t.registration_count }} 支队伍
              </td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <a :href="`/admin/tournaments/${t.id}/board/`" class="c-btn c-btn--ghost c-btn--xs">编队</a>
                  <a :href="`/admin/tournaments/${t.id}/review/`" class="c-btn c-btn--ghost c-btn--xs">审核</a>
                  <a :href="`/admin/tournaments/${t.id}/`" class="c-btn c-btn--ghost c-btn--xs">编辑</a>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
