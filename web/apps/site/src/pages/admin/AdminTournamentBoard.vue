<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminTournamentsIdBoard, type GetApiAdminTournamentsIdBoardOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const route = useRoute()
const id = ref((route.params.id as string) || "")
const loading = ref(true)
const board = ref<GetApiAdminTournamentsIdBoardOut | null>(null)
const error = ref<string | null>(null)
const saving = ref(false)

async function loadBoard() {
  loading.value = true
  try {
    const res = await getApiAdminTournamentsIdBoard(id.value)
    board.value = res
  } catch (err: any) {
    error.value = err?.message ?? "加载编队板失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadBoard()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="活动"
      :title="`队伍编排板 · 赛事 #${id}`"
      :back-to="`/admin/tournaments/${id}/`"
      back-label="返回赛事详情"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm" :disabled="saving">
          <CIcon name="check" class="size-4 mr-1" /> 保存编队结果
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-[18rem_1fr] gap-6">
        <!-- 散人池 -->
        <div class="bg-surface p-4 rounded-lg border border-border shadow-xs">
          <h2 class="font-bold text-sm text-fg mb-3 pb-2 border-b border-border flex justify-between items-center">
            <span>散人待编排池</span>
            <span class="text-xs bg-surface-2 px-2 py-0.5 rounded text-fg-2">
              {{ board?.solo_pool?.length ?? 0 }} 人
            </span>
          </h2>

          <div v-if="loading" class="text-xs text-fg-3 py-6 text-center">加载散人池中...</div>
          <div v-else-if="!board?.solo_pool?.length" class="text-xs text-fg-3 py-6 text-center">
            暂无待编排散人
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="p in board.solo_pool"
              :key="p.user_id"
              class="p-2.5 rounded bg-surface-2 border border-border text-xs"
            >
              <p class="font-semibold text-fg">{{ p.nickname }}</p>
              <p class="text-[11px] text-fg-3">{{ p.battle_tag }} · {{ p.primary_role || "未选位置" }}</p>
            </div>
          </div>
        </div>

        <!-- 队伍列表与编排区 -->
        <div class="space-y-4">
          <div class="p-4 rounded-lg bg-surface border border-border shadow-xs flex justify-between items-center">
            <div>
              <h2 class="font-bold text-sm text-fg">参赛队伍阵容</h2>
              <p class="text-xs text-fg-3">拖拽或点击将散人分配到对应队伍</p>
            </div>
            <button class="c-btn c-btn--secondary c-btn--sm">新建临时队伍</button>
          </div>

          <div v-if="loading" class="text-center py-12 text-fg-3">正在拉取编队板阵容...</div>
          <div v-else-if="!board?.teams?.length" class="text-center py-12 bg-surface border border-border rounded-lg text-fg-3">
            暂无参赛队伍阵容
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              v-for="team in board.teams"
              :key="team.registration_id"
              class="bg-surface p-4 rounded-lg border border-border shadow-xs flex flex-col justify-between"
            >
              <div>
                <div class="flex justify-between items-center mb-2 pb-2 border-b border-border">
                  <h3 class="font-bold text-sm text-fg">{{ team.team_name }}</h3>
                  <span class="text-xs text-fg-3">{{ team.members?.length ?? 0 }} 人</span>
                </div>
                <div class="space-y-1.5">
                  <div
                    v-for="m in team.members"
                    :key="m.user_id"
                    class="p-2 rounded bg-surface-2 flex items-center justify-between text-xs"
                  >
                    <span>{{ m.nickname }}</span>
                    <span class="text-[10px] text-fg-3">{{ m.role_label }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
