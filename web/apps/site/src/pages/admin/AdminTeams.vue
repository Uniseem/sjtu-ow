<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminTeams, type GetApiAdminTeamsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const membersSection = ADMIN_SECTIONS.find((s) => s.id === "members")
const loading = ref(true)
const teams = ref<GetApiAdminTeamsOut["teams"]>([])
const error = ref<string | null>(null)

async function loadTeams() {
  loading.value = true
  try {
    const res = await getApiAdminTeams()
    teams.value = res.teams
  } catch (err: any) {
    error.value = err?.message ?? "加载战队列表失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadTeams()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="成员"
      title="战队管理"
      :tabs="membersSection?.tabs"
      active-tab="teams"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">战队名称</th>
              <th class="p-3 font-medium">现任队长</th>
              <th class="p-3 font-medium">成员人数</th>
              <th class="p-3 font-medium">招募状态</th>
              <th class="p-3 font-medium">战队状态</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">正在拉取战队列表...</td>
            </tr>
            <tr v-else-if="teams.length === 0" class="border-b border-border">
              <td colspan="6" class="p-8 text-center text-fg-3">暂无战队记录</td>
            </tr>
            <tr
              v-for="t in teams"
              v-else
              :key="t.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3 font-bold text-fg">
                <a :href="`/teams/${t.id}/`" target="_blank" class="hover:underline">{{ t.name }}</a>
              </td>
              <td class="p-3 text-sm text-fg-2">
                <span v-if="t.captain_nickname">{{ t.captain_nickname }}</span>
                <span v-else class="text-danger font-bold text-xs">无队长（需指定）</span>
              </td>
              <td class="p-3 text-sm text-fg-2">{{ t.member_count }} 人</td>
              <td class="p-3 text-sm">
                <span :class="t.recruiting ? 'text-success' : 'text-fg-3'">
                  {{ t.recruiting ? '招募中' : '已暂停' }}
                </span>
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="t.disbanded_at ? 'bg-danger-soft text-on-danger-soft' : 'bg-success-soft text-on-success-soft'"
                >
                  {{ t.disbanded_at ? '已解散' : '正常' }}
                </span>
              </td>
              <td class="p-3 text-right">
                <div class="inline-flex gap-2">
                  <button v-if="!t.disbanded_at" class="c-btn c-btn--ghost c-btn--xs">指定队长</button>
                  <button v-if="!t.disbanded_at" class="c-btn c-btn--ghost c-btn--xs text-danger">解散战队</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
