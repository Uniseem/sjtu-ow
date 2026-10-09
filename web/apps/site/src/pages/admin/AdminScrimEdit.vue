<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import { getApiAdminScrimsId, type GetApiAdminScrimsIdOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const route = useRoute()
const id = ref((route.params.id as string) || "")
const isNew = !id.value || id.value === "new"

const loading = ref(!isNew)
const saving = ref(false)
const title = ref("")
const format = ref("5v5")
const description = ref("")
const status = ref("draft")
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)

onMounted(async () => {
  if (!isNew) {
    try {
      const res = await getApiAdminScrimsId(id.value)
      if (res.scrim) {
        title.value = res.scrim.title
        format.value = res.scrim.format
        description.value = res.scrim.description ?? ""
        status.value = res.scrim.status
      }
    } catch (err: any) {
      error.value = err?.message ?? "加载内战失败"
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
      :title="isNew ? '新建内战' : (title || '编辑内战')"
      back-to="/admin/scrims/"
      back-label="返回内战列表"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm" :disabled="saving">
          <CIcon name="check" class="size-4 mr-1" />
          {{ isNew ? '创建内战草稿' : '保存设置' }}
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
            <label class="block text-sm font-semibold mb-1">内战标题</label>
            <input
              v-model="title"
              type="text"
              class="c-input w-full text-base font-bold"
              placeholder="例如：周六晚欢乐内战..."
            />
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-semibold mb-1">对局规格</label>
              <select v-model="format" class="c-input w-full">
                <option value="5v5">5v5 职责锁定（1重装 2输出 2支援）</option>
                <option value="6v6">6v6 怀旧模式（2重装 2输出 2支援）</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-semibold mb-1">当前状态</label>
              <input type="text" :value="status" disabled class="c-input w-full bg-surface-2 opacity-80" />
            </div>
          </div>

          <div>
            <label class="block text-sm font-semibold mb-1">内战说明 (Markdown)</label>
            <textarea
              v-model="description"
              rows="10"
              class="c-input w-full font-mono text-sm resize-y"
              placeholder="可注明房间名、密码、语音频道要求、迟到处理规则等..."
            />
          </div>
        </div>

        <aside class="b-aside flex flex-col gap-4">
          <div class="b-section p-5 rounded-lg bg-surface border border-border shadow-xs">
            <h3 class="font-bold text-sm mb-3 pb-2 border-b border-border">内战快捷通道</h3>
            <div class="space-y-2">
              <a v-if="!isNew" :href="`/admin/scrims/${id}/split/`" class="c-btn c-btn--secondary w-full c-btn--sm">
                进入分队板
              </a>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>
