<script setup lang="ts">
import { ref, onMounted } from "vue"
import {
  getApiAdminImages,
  getApiAdminImageCollections,
  type GetApiAdminImagesOut,
  type GetApiAdminImageCollectionsOut,
} from "@sjtu-ow/api"
import { ADMIN_SECTIONS } from "../../admin/nav"
import AdminHead from "../../admin/AdminHead.vue"
import CIcon from "../../components/CIcon.vue"
import { useApi } from "../../api"

const api = useApi()

const contentSection = ADMIN_SECTIONS.find((s) => s.id === "content")
const loading = ref(true)
const images = ref<GetApiAdminImagesOut["images"]>([])
const collections = ref<GetApiAdminImageCollectionsOut["collections"]>([])
const selectedCollection = ref("")
const search = ref("")
const error = ref<string | null>(null)

async function loadData() {
  loading.value = true
  try {
    const [imgRes, colRes] = await Promise.all([
      getApiAdminImages(api),
      getApiAdminImageCollections(api),
    ])
    images.value = imgRes.images
    collections.value = colRes.collections
  } catch (err: any) {
    error.value = err?.message ?? "加载图片失败"
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div>
    <AdminHead
      kicker="内容"
      title="图片媒体库"
      :tabs="contentSection?.tabs"
      active-tab="images"
    >
      <template #actions>
        <label class="c-btn c-btn--primary c-btn--sm cursor-pointer">
          <CIcon name="plus" class="size-4 mr-1" /> 上传图片
          <input type="file" class="sr-only" accept="image/*" />
        </label>
      </template>
    </AdminHead>

    <div class="b-main">
      <div v-if="error" class="c-notice c-notice--warning mb-4">
        <p>{{ error }}</p>
      </div>

      <!-- 集合与搜索筛选 -->
      <div class="b-filters flex flex-wrap items-center gap-3 p-3 bg-surface border border-border rounded-lg">
        <div class="flex-1 min-w-[200px]">
          <input
            v-model="search"
            type="search"
            class="c-input w-full"
            placeholder="搜索图片标题..."
          />
        </div>
        <select v-model="selectedCollection" class="c-input">
          <option value="">全部集合</option>
          <option v-for="col in collections" :key="col.id" :value="String(col.id)">
            {{ col.name }} ({{ col.image_count }})
          </option>
        </select>
        <button class="c-btn c-btn--secondary c-btn--sm" @click="loadData">刷新</button>
      </div>

      <!-- 图片网格 b-grid -->
      <div v-if="loading" class="text-center py-16 text-fg-3">正在加载图片库...</div>
      <div v-else-if="images.length === 0" class="text-center py-16 text-fg-3 bg-surface border border-border rounded-lg">
        暂无图片记录
      </div>
      <div v-else class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <div
          v-for="img in images"
          :key="img.id"
          class="group relative bg-surface border border-border rounded-lg overflow-hidden flex flex-col"
        >
          <div class="aspect-square bg-surface-2 overflow-hidden flex items-center justify-center">
            <img
              v-if="img.thumb_url"
              :src="img.thumb_url"
              :alt="img.title"
              class="w-full h-full object-cover group-hover:scale-105 transition-transform"
            />
            <CIcon v-else name="settings" class="size-8 text-fg-3" />
          </div>
          <div class="p-2 text-xs">
            <p class="font-medium text-fg truncate" :title="img.title">{{ img.title }}</p>
            <p class="text-fg-3 text-[10px] mt-0.5">
              {{ img.width }}×{{ img.height }} · {{ img.collection_name || "默认集合" }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
