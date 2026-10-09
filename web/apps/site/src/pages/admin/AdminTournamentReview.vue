<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import {
  getApiAdminTournamentsIdRegistrations,
  postApiAdminRegistrationsIdApprove,
  postApiAdminRegistrationsIdReject,
  type GetApiAdminTournamentsIdRegistrationsOut,
} from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const route = useRoute()
const id = ref((route.params.id as string) || "")
const loading = ref(true)
const registrations = ref<GetApiAdminTournamentsIdRegistrationsOut["registrations"]>([])
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)

async function loadRegistrations() {
  loading.value = true
  try {
    const res = await getApiAdminTournamentsIdRegistrations(id.value)
    registrations.value = res.registrations
  } catch (err: any) {
    error.value = err?.message ?? "加载报名记录失败"
  } finally {
    loading.value = false
  }
}

async function approve(regId: number) {
  try {
    await postApiAdminRegistrationsIdApprove(String(regId))
    successMsg.value = `报名 #${regId} 已通过审核`
    await loadRegistrations()
  } catch (err: any) {
    error.value = err?.message ?? "审核通过失败"
  }
}

async function reject(regId: number) {
  const reason = prompt("请输入驳回原因：")
  if (!reason) return
  try {
    await postApiAdminRegistrationsIdReject(String(regId), { reason })
    successMsg.value = `报名 #${regId} 已驳回`
    await loadRegistrations()
  } catch (err: any) {
    error.value = err?.message ?? "驳回失败"
  }
}

onMounted(() => {
  loadRegistrations()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="活动"
      :title="`报名审核 · 赛事 #${id}`"
      :back-to="`/admin/tournaments/${id}/`"
      back-label="返回赛事详情"
    />

    <div class="b-main">
      <div v-if="successMsg" class="c-notice c-notice--success mb-4">
        <p>{{ successMsg }}</p>
      </div>
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="bg-surface border border-border rounded-lg overflow-x-auto">
        <table class="c-table w-full text-left">
          <thead>
            <tr class="border-b border-border text-xs text-fg-3">
              <th class="p-3 font-medium">队伍 / 个人</th>
              <th class="p-3 font-medium">报名类型</th>
              <th class="p-3 font-medium">状态</th>
              <th class="p-3 font-medium">提交时间</th>
              <th class="p-3 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">正在拉取报名申请...</td>
            </tr>
            <tr v-else-if="registrations.length === 0" class="border-b border-border">
              <td colspan="5" class="p-8 text-center text-fg-3">暂无待审报名</td>
            </tr>
            <tr
              v-for="reg in registrations"
              v-else
              :key="reg.id"
              class="border-b border-border hover:bg-surface-2 transition-colors"
            >
              <td class="p-3">
                <p class="font-bold text-fg">{{ reg.team_name || "临时队伍 / 散人" }}</p>
                <p class="text-xs text-fg-3">联系人：{{ reg.contact_info || "—" }}</p>
              </td>
              <td class="p-3 text-sm text-fg-2">
                {{ reg.type === 'team' ? '整队报名' : '个人拼队' }}
              </td>
              <td class="p-3 text-sm">
                <span
                  class="inline-block px-2 py-0.5 rounded text-xs"
                  :class="{
                    'bg-success-soft text-on-success-soft': reg.status === 'approved',
                    'bg-warning-soft text-on-warning-soft': reg.status === 'submitted',
                    'bg-danger-soft text-on-danger-soft': reg.status === 'rejected',
                  }"
                >
                  {{ reg.status === 'approved' ? '已通过' : reg.status === 'submitted' ? '待审核' : '已驳回' }}
                </span>
              </td>
              <td class="p-3 text-xs text-fg-3">
                {{ reg.created_at }}
              </td>
              <td class="p-3 text-right">
                <div v-if="reg.status === 'submitted'" class="inline-flex gap-2">
                  <button class="c-btn c-btn--primary c-btn--xs" @click="approve(reg.id)">通过</button>
                  <button class="c-btn c-btn--secondary c-btn--xs text-danger" @click="reject(reg.id)">驳回</button>
                </div>
                <span v-else class="text-xs text-fg-3">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
