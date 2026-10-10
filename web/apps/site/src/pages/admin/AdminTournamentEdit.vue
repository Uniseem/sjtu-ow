<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminTournamentsId, type GetApiAdminTournamentsIdOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const route = useRoute()
const id = ref((route.params.id as string) || "")
const isNew = !id.value || id.value === "new"

const loading = ref(!isNew)
const saving = ref(false)
const title = ref("")
const description = ref("")
const mode = ref("team")
const status = ref("draft")
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)

onMounted(async () => {
  if (!isNew) {
    try {
      const res = await getApiAdminTournamentsId(api, id.value)
      if (res.tournament) {
        title.value = res.tournament.title
        description.value = res.tournament.description ?? ""
        mode.value = res.tournament.mode
        status.value = res.tournament.status
      }
    } catch (err: any) {
      error.value = err?.message ?? "加载赛事失败"
    } finally {
      loading.value = false
    }
  }
})
</script>

<template>
  <div>
    <AdminHead
      kicker="活动"
      :title="isNew ? '新建赛事' : (title || '编辑赛事')"
      back-to="/admin/tournaments/"
      back-label="返回赛事列表"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm" :disabled="saving">
          <CIcon name="check" class="size-4 mr-1" />
          {{ isNew ? '创建赛事草稿' : '保存设置' }}
        </button>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="successMsg" class="c-notice c-notice--success mb-4">
        <p>{{ successMsg }}</p>
      </div>
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="b-split grid grid-cols-1 lg:grid-cols-[1fr_22rem] gap-6">
        <div class="flex flex-col gap-4 bg-surface p-6 rounded-lg border border-border shadow-xs">
          <div>
            <label class="block text-sm font-semibold mb-1">赛事标题</label>
            <input
              v-model="title"
              type="text"
              class="c-input w-full text-base font-bold"
              placeholder="例如：2026 SJTU-OW 新生杯秋季争霸赛..."
            />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-semibold mb-1">报名模式</label>
              <select v-model="mode" class="c-input w-full">
                <option value="team">整队报名（固定战队/自由组队）</option>
                <option value="individual">散人个人报名（由干部编队）</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">当前状态</label>
              <input type="text" :value="status" disabled class="c-input w-full bg-surface-2 opacity-80" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-semibold mb-1">赛事规程与说明 (Markdown)</label>
            <textarea
              v-model="description"
              rows="12"
              class="c-input w-full font-mono text-sm resize-y"
              placeholder="编写赛程赛制、奖品奖金、直播信息、报名限制要求等..."
            />
          </div>
        </div>

        <aside class="b-aside flex flex-col gap-4">
          <div class="b-section p-5 rounded-lg bg-surface border border-border shadow-xs">
            <h3 class="font-bold text-sm mb-3 pb-2 border-b border-border">赛事快捷通道</h3>
            <div class="space-y-2">
              <a v-if="!isNew" :href="`/admin/tournaments/${id}/board/`" class="c-btn c-btn--secondary w-full c-btn--sm">
                进入队伍编排板
              </a>
              <a v-if="!isNew" :href="`/admin/tournaments/${id}/review/`" class="c-btn c-btn--secondary w-full c-btn--sm">
                进入报名审核
              </a>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>
