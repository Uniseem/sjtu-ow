<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminHomePins, putApiAdminHomePins, type GetApiAdminHomePinsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const contentSection = ADMIN_SECTIONS.find((s) => s.id === "content")
const loading = ref(true)
const saving = ref(false)
const pins = ref<GetApiAdminHomePinsOut["pins"]>([])
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)

async function loadPins() {
  loading.value = true
  try {
    const res = await getApiAdminHomePins(api)
    pins.value = res.pins
  } catch (err: any) {
    error.value = err?.message ?? "加载置顶失败"
  } finally {
    loading.value = false
  }
}

async function savePins() {
  saving.value = true
  error.value = null
  successMsg.value = null
  try {
    await putApiAdminHomePins(api, {
      article_ids: pins.value.map((p) => p.article_id),
    })
    successMsg.value = "首页置顶顺序已保存"
  } catch (err: any) {
    error.value = err?.message ?? "保存失败"
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadPins()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="内容"
      title="首页置顶文章"
      :tabs="contentSection?.tabs"
      active-tab="home_pins"
    >
      <template #actions>
        <button class="c-btn c-btn--primary c-btn--sm" :disabled="saving" @click="savePins">
          <CIcon name="check" class="size-4 mr-1" />
          {{ saving ? '正在保存...' : '保存置顶设置' }}
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

      <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs max-w-3xl">
        <h2 class="text-base font-bold text-fg mb-2">置顶文章列表（最多 3 篇）</h2>
        <p class="text-xs text-fg-3 mb-6">
          置顶文章将在网站首页顶部醒目展示。可以拖拽或调整先后顺序。
        </p>

        <div v-if="loading" class="text-center py-8 text-fg-3">正在拉取置顶数据...</div>
        <div v-else-if="pins.length === 0" class="text-center py-8 text-fg-3 border border-dashed border-border rounded-lg">
          当前暂无首页置顶文章。
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="(pin, idx) in pins"
            :key="pin.article_id"
            class="flex items-center justify-between p-3 rounded-md bg-surface-2 border border-border"
          >
            <div class="flex items-center gap-3">
              <span class="size-6 rounded-full bg-primary-soft text-on-primary-soft font-bold text-xs flex items-center justify-center">
                {{ idx + 1 }}
              </span>
              <div>
                <p class="font-bold text-sm text-fg">{{ pin.title }}</p>
                <p class="text-xs text-fg-3">编号：#{{ pin.article_id }} · 发布于 {{ pin.published_at }}</p>
              </div>
            </div>
            <button class="c-btn c-btn--ghost c-btn--xs text-danger" @click="pins.splice(idx, 1)">
              移除
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
