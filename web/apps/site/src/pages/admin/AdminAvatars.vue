<script setup lang="ts">
import { ref, onMounted } from "vue"
import { getApiAdminAvatars, postApiAdminAvatarsIdTakeDown, type GetApiAdminAvatarsOut } from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"

const reviewSection = ADMIN_SECTIONS.find((s) => s.id === "review")
const loading = ref(true)
const avatars = ref<GetApiAdminAvatarsOut["avatars"]>([])
const error = ref<string | null>(null)
const successMsg = ref<string | null>(null)

async function loadAvatars() {
  loading.value = true
  try {
    const res = await getApiAdminAvatars()
    avatars.value = res.avatars
  } catch (err: any) {
    error.value = err?.message ?? "加载头像列表失败"
  } finally {
    loading.value = false
  }
}

async function takeDown(id: number) {
  const reason = prompt("请输入下架头像的原因：", "违反社区头像规范")
  if (!reason) return
  try {
    await postApiAdminAvatarsIdTakeDown(String(id), { reason })
    successMsg.value = `头像记录 #${id} 已下架`
    await loadAvatars()
  } catch (err: any) {
    error.value = err?.message ?? "下架头像失败"
  }
}

onMounted(() => {
  loadAvatars()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="审核"
      title="头像审核"
      :tabs="reviewSection?.tabs"
      active-tab="avatars"
    />

    <div class="b-main">
      <div v-if="successMsg" class="c-notice c-notice--success mb-4">
        <p>{{ successMsg }}</p>
      </div>
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <div v-if="loading" class="text-center py-16 text-fg-3">正在加载头像列表...</div>
      <div v-else-if="avatars.length === 0" class="text-center py-16 text-fg-3 bg-surface border border-border rounded-lg">
        暂无头像提交记录
      </div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div
          v-for="a in avatars"
          :key="a.id"
          class="bg-surface border border-border rounded-lg overflow-hidden flex flex-col p-3 items-center text-center"
        >
          <div class="size-20 rounded-full overflow-hidden bg-surface-2 border border-border mb-3 flex items-center justify-center">
            <img v-if="a.thumb_url" :src="a.thumb_url" :alt="a.nickname" class="w-full h-full object-cover" />
            <CIcon v-else name="user" class="size-8 text-fg-3" />
          </div>
          <p class="font-bold text-sm text-fg truncate w-full">{{ a.nickname }}</p>
          <p class="text-[10px] text-fg-3 mt-1">提交于 {{ a.created_at }}</p>

          <div class="mt-3 w-full">
            <button
              v-if="!a.taken_down"
              class="c-btn c-btn--danger w-full c-btn--xs"
              @click="takeDown(a.id)"
            >
              违规下架
            </button>
            <span v-else class="text-[10px] text-danger font-semibold block py-1">已下架</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
