<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute } from "vue-router"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const route = useRoute()
const batchId = ref((route.params.batch as string) || "")
const loading = ref(true)
const batches = ref<any[]>([])
const successMsg = ref<string | null>(null)
const errorMsg = ref<string | null>(null)

async function loadBatches() {
  loading.value = true
  try {
    const res = await fetch("/api/admin/todo")
    if (res.ok) {
      // 模拟加载批次列表或直接调用待发信接口
      batches.value = []
    }
  } catch (err: any) {
    errorMsg.value = err?.message ?? "加载失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadBatches()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="首页"
      :title="batchId ? `确认发信批次 #${batchId}` : '待发信批次确认'"
      back-to="/admin/"
      back-label="返回后台首页"
    />

    <div class="b-main">
      <div v-if="successMsg" class="c-notice c-notice--success mb-4">
        <p>{{ successMsg }}</p>
      </div>
      <div v-if="errorMsg" class="c-notice c-notice--danger mb-4">
        <p>{{ errorMsg }}</p>
      </div>

      <section class="b-section p-6 rounded-lg bg-surface border border-border shadow-xs">
        <div class="flex items-center gap-2 mb-4">
          <CIcon name="mail" class="size-5 text-accent" />
          <h2 class="text-lg font-bold">待发信批次机制</h2>
        </div>
        <p class="text-sm text-fg-2 mb-6">
          你在后台执行管理操作（如赛事通过、临时队编排、战队转让等）附带产生的通知信件会暂时冻结在待发信队列中，确认发送后才会正式投递。
        </p>

        <div v-if="batchId" class="p-4 rounded-md bg-surface-2 border border-border">
          <p class="font-medium text-fg">批次编号：{{ batchId }}</p>
          <p class="text-xs text-fg-3 mt-1">请核对将要送出的通知邮件列表</p>
          <div class="mt-4 flex gap-3">
            <button class="c-btn c-btn--primary c-btn--sm">确认并送出勾选的信件</button>
            <button class="c-btn c-btn--ghost c-btn--sm">全部跳过不发</button>
          </div>
        </div>

        <div v-else class="text-center py-12 text-fg-3">
          <CIcon name="check-circle" class="size-8 mx-auto mb-2 text-success opacity-80" />
          <p>当前没有待认领的停顿发信批次。</p>
        </div>
      </section>
    </div>
  </div>
</template>
