<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminLog, type GetApiAdminLogOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const settingsSection = ADMIN_SECTIONS.find((s) => s.id === "settings")
const loading = ref(true)
const logs = ref<GetApiAdminLogOut["entries"]>([])
const error = ref<string | null>(null)

async function loadLog() {
  loading.value = true
  try {
    const res = await getApiAdminLog()
    logs.value = res.entries
  } catch (err: any) {
    error.value = err?.message ?? "加载审计日志失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadLog()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="设置"
      title="操作记录与审计日志"
      :tabs="settingsSection?.tabs"
      active-tab="log"
    />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">操作时间</th>
              <th class="p-3 font-medium">操作人</th>
              <th class="p-3 font-medium">操作类型 (Action)</th>
              <th class="p-3 font-medium">目标对象</th>
              <th class="p-3 font-medium">详细说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">正在拉取审计日志...</td>
            </tr>
            <tr v-else-if="logs.length === 0" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">暂无操作记录</td>
            </tr>
            <tr
              v-for="l in logs"
              v-else
              :key="l.id"
              class="border-b border-border hover:bg-surface-2 transition-colors text-xs"
            >
              <td class="p-3 text-fg-3 font-mono">{{ l.created_at }}</td>
              <td class="p-3 font-bold text-fg">
                {{ l.actor_nickname || (l.actor_id ? `#${l.actor_id}` : '系统代发') }}
              </td>
              <td class="p-3 font-semibold text-fg">
                <span class="px-2 py-0.5 rounded bg-surface-2 border border-border">
                  {{ l.action }}
                </span>
              </td>
              <td class="p-3 text-fg-2 font-mono">
                {{ l.target_type }} {{ l.target_id ? `#${l.target_id}` : '' }}
              </td>
              <td class="p-3 text-fg-2 max-w-sm truncate">{{ l.comment || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
