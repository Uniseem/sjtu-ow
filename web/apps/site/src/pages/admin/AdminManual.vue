<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminManual, type GetApiAdminManualOut } from "@sjtu-ow/api"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const loading = ref(true)
const sections = ref<GetApiAdminManualOut["sections"]>([])
const error = ref<string | null>(null)

async function loadManual() {
  loading.value = true
  try {
    const res = await getApiAdminManual()
    sections.value = res.sections
  } catch (err: any) {
    error.value = err?.message ?? "加载干部手册失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadManual()
})
</script>

<template>
  <div>
    <AdminHead kicker="手册" title="干部操作手册" />

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div class="max-w-4xl space-y-6">
        <div v-if="loading" class="text-center py-12 text-fg-3">正在加载干部手册...</div>
        <div v-else-if="sections.length === 0" class="text-center py-12 bg-surface border border-border rounded-lg text-fg-3">
          根据当前拥有的角色能力，暂无对应的干部手册板块
        </div>
        <section
          v-for="s in sections"
          v-else
          :key="s.id"
          class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs"
        >
          <div class="flex items-center gap-2 mb-3 pb-2 border-b border-border">
            <CIcon name="info" class="size-5 text-accent" />
            <h2 class="text-base font-bold text-fg">{{ s.title }}</h2>
          </div>
          <div class="text-sm leading-relaxed text-fg-2 whitespace-pre-line font-mono">
            {{ s.content }}
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
