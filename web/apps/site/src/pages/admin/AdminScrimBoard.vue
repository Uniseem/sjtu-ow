<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import {
  getApiAdminScrimsIdBoard,
  postApiAdminScrimsIdBoardGenerate,
  type GetApiAdminScrimsIdBoardOut,
} from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const route = useRoute()
const id = ref((route.params.id as string) || "")
const loading = ref(true)
const board = ref<GetApiAdminScrimsIdBoardOut | null>(null)
const error = ref<string | null>(null)
const generating = ref(false)

async function loadBoard() {
  loading.value = true
  try {
    const res = await getApiAdminScrimsIdBoard(api, id.value)
    board.value = res
  } catch (err: any) {
    error.value = err?.message ?? "加载分队板失败"
  } finally {
    loading.value = false
  }
}

async function runGenerate() {
  generating.value = true
  try {
    await postApiAdminScrimsIdBoardGenerate(api, id.value, {
      board_version: board.value?.board_version ?? 1,
    })
    await loadBoard()
  } catch (err: any) {
    error.value = err?.message ?? "生成分队失败"
  } finally {
    generating.value = false
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
      :title="`内战分队板 · 内战 #${id}`"
      :back-to="`/admin/scrims/${id}/`"
      back-label="返回内战详情"
    >
      <template #actions>
        <button class="c-btn c-btn--secondary c-btn--sm" :disabled="generating" @click="runGenerate">
          <CIcon name="settings" class="size-4 mr-1" />
          {{ generating ? '算法计算中...' : '生成自动分队' }}
        </button>
        <button class="c-btn c-btn--primary c-btn--sm">
          <CIcon name="check" class="size-4 mr-1" /> 保存分队板
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-[18rem_1fr] gap-6">
        <!-- 报名与勾选名单 -->
        <div class="bg-surface p-4 rounded-lg border border-border shadow-xs">
          <h2 class="font-bold text-sm text-fg mb-3 pb-2 border-b border-border flex justify-between items-center">
            <span>报名上场名单</span>
            <span class="text-xs bg-surface-2 px-2 py-0.5 rounded text-fg-2">
              {{ board?.signups?.length ?? 0 }} 人
            </span>
          </h2>

          <div v-if="loading" class="text-xs text-fg-3 py-6 text-center">加载名单中...</div>
          <div v-else-if="!board?.signups?.length" class="text-xs text-fg-3 py-6 text-center">
            暂无报名人员
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="s in board.signups"
              :key="s.user_id"
              class="p-2.5 rounded bg-surface-2 border border-border text-xs flex items-center justify-between"
            >
              <div>
                <p class="font-semibold text-fg">{{ s.nickname }}</p>
                <p class="text-[11px] text-fg-3">{{ s.role }} · {{ s.rank_label || "未定级" }}</p>
              </div>
              <input type="checkbox" :checked="s.selected" class="c-checkbox" />
            </div>
          </div>
        </div>

        <!-- 红蓝对局两栏 -->
        <div class="space-y-4">
          <div class="p-4 rounded-lg bg-surface border border-border shadow-xs flex justify-between items-center">
            <div>
              <h2 class="font-bold text-sm text-fg">红蓝阵营对位</h2>
              <p class="text-xs text-fg-3">支持在红队、蓝队与替补缓冲区之间相互拖拽微调</p>
            </div>
            <button class="c-btn c-btn--ghost c-btn--sm">复制分队对位文案</button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- 队伍 A (红队) -->
            <div class="bg-surface p-4 rounded-lg border border-border shadow-xs">
              <h3 class="font-bold text-sm text-primary mb-3 pb-2 border-b border-border">
                红队 (Team A)
              </h3>
              <div class="space-y-2 min-h-[160px]">
                <div
                  v-for="p in (board?.team_a ?? [])"
                  :key="p.user_id"
                  class="p-2 rounded bg-surface-2 flex items-center justify-between text-xs"
                >
                  <span class="font-medium text-fg">{{ p.nickname }}</span>
                  <span class="text-fg-3">{{ p.role_slot }}</span>
                </div>
              </div>
            </div>

            <!-- 队伍 B (蓝队) -->
            <div class="bg-surface p-4 rounded-lg border border-border shadow-xs">
              <h3 class="font-bold text-sm text-accent mb-3 pb-2 border-b border-border">
                蓝队 (Team B)
              </h3>
              <div class="space-y-2 min-h-[160px]">
                <div
                  v-for="p in (board?.team_b ?? [])"
                  :key="p.user_id"
                  class="p-2 rounded bg-surface-2 flex items-center justify-between text-xs"
                >
                  <span class="font-medium text-fg">{{ p.nickname }}</span>
                  <span class="text-fg-3">{{ p.role_slot }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
