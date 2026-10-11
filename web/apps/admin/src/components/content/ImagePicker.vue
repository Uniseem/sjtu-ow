<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue"
import { getApiAdminImages, getApiAdminImageCollections } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSession } from "../../core/session"
import { useContentResource } from "../../pages/content/use-resource"
import { useUploadQueue } from "../../pages/content/use-upload-queue"
import { positiveID, type Image } from "../../pages/content/types"
import ImageGrid from "./ImageGrid.vue"
import ContentLoad from "./ContentLoad.vue"

const emit = defineEmits<{ select: [image: Image]; close: [] }>()
const api = useAdminApi()
const { user } = useAdminSession()
const dialog = ref<HTMLDialogElement | null>(null)
const search = ref("")
const collection = ref("")
const uploadCollection = ref("")
const file = ref<File | null>(null)
const page = ref(1)
const submitted = ref({ q: "", collection: "" })
const canUpload = computed(() => Boolean(user.value?.superuser || user.value?.caps.includes("images.contribute")))
const collections = useContentResource((signal) => getApiAdminImageCollections(api, { signal }))
const images = useContentResource((signal) => getApiAdminImages(api, {
  q: submitted.value.q,
  collection_id: positiveID(submitted.value.collection) ?? undefined,
  page: page.value,
  page_size: 48,
}, { signal }))
const pages = computed(() => Math.max(1, Math.ceil((images.data.value?.total ?? 0) / 48)))
const upload = useUploadQueue(api, (image) => emit("select", image))
let priorFocus: HTMLElement | null = null

function filter(): void {
  submitted.value = { q: search.value.trim().slice(0, 50), collection: collection.value }
  page.value = 1
  void images.load()
}

function go(value: number): void {
  if (value < 1 || value > pages.value || images.pending.value) return
  page.value = value
  void images.load()
}

function selectedFile(event: Event): void {
  if (event.target instanceof HTMLInputElement) file.value = event.target.files?.[0] ?? null
}

function uploadSelected(): void {
  if (!file.value || upload.pending.value || upload.uncertain.value) return
  upload.add([file.value], uploadCollection.value)
  void upload.start()
}

function close(): void {
  if (upload.pending.value || upload.uncertain.value) return
  emit("close")
}

function cancel(event: Event): void {
  event.preventDefault()
  close()
}

function key(event: KeyboardEvent): void {
  if (event.key !== "Tab" || !dialog.value) return
  const controls = [...dialog.value.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href]")]
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
}

onMounted(async () => {
  priorFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
  await nextTick()
  dialog.value?.showModal()
  dialog.value?.querySelector<HTMLInputElement>("input[type=search]")?.focus()
  void images.load()
  const result = await collections.load()
  uploadCollection.value = result?.collections[0]?.key ?? ""
})
onBeforeUnmount(() => { dialog.value?.close(); priorFocus?.focus() })
</script>
<template>
  <dialog ref="dialog" class="b-dialog" aria-labelledby="image-picker-title" @cancel="cancel" @keydown="key">
    <div class="c-panel__head">
      <h2 id="image-picker-title" class="b-section__title">选择图片</h2>
      <button type="button" class="c-btn c-btn--quiet c-btn--sm" :disabled="upload.pending.value || upload.uncertain.value" @click="close">关闭</button>
    </div>
    <form class="b-filters" role="search" @submit.prevent="filter">
      <input v-model="search" class="c-input" type="search" maxlength="50" placeholder="搜标题" aria-label="搜标题">
      <select v-model="collection" class="c-input" aria-label="集合" @change="filter">
        <option value="">全部集合</option>
        <option v-for="item in collections.data.value?.collections ?? []" :key="item.id" :value="String(item.id)">{{ item.name }}</option>
      </select>
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="images.pending.value">筛选</button>
    </form>
    <ContentLoad :pending="collections.pending.value" :message="collections.message.value" :status="collections.status.value" @retry="collections.load" />
    <form v-if="canUpload" class="b-filters" @submit.prevent="uploadSelected">
      <select v-model="uploadCollection" class="c-input" aria-label="放进集合" :disabled="upload.pending.value || upload.uncertain.value">
        <option v-for="item in collections.data.value?.collections ?? []" :key="item.id" :value="item.key">{{ item.name }}</option>
      </select>
      <input type="file" accept=".jpg,.jpeg,.png,.webp" required aria-label="选一张图片" :disabled="upload.pending.value || upload.uncertain.value" @change="selectedFile">
      <button class="c-btn c-btn--secondary c-btn--sm" :disabled="!file || !uploadCollection || upload.pending.value || upload.uncertain.value">上传并选用</button>
      <span class="b-count" role="status">{{ upload.pending.value ? '正在上传…' : '' }}</span>
    </form>
    <div v-if="upload.message.value || upload.items.value.some(item => item.state === 'failed' || item.state === 'uncertain')" class="c-notice c-notice--error" role="alert">
      <p>{{ upload.message.value || upload.items.value.find(item => item.state === 'failed' || item.state === 'uncertain')?.message }}</p>
      <button v-if="upload.uncertain.value" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="upload.pending.value" @click="upload.retry">重试上次上传</button>
    </div>
    <ContentLoad :pending="images.pending.value" :message="images.message.value" :status="images.status.value" @retry="images.load" />
    <ImageGrid v-if="images.data.value" :images="images.data.value.items" :collections="collections.data.value?.collections" choose :disabled="upload.pending.value || upload.uncertain.value" @select="$emit('select', $event)" />
    <p v-if="images.data.value && !images.data.value.items.length" class="b-section__text">没有能选的图片。<span v-if="canUpload">上传一张吧。</span></p>
    <nav v-if="pages > 1" class="c-pager" aria-label="图片分页">
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="page <= 1 || images.pending.value" @click="go(page - 1)">上一页</button>
      <span class="c-pager__pos"><strong>{{ page }}</strong> / {{ pages }}</span>
      <button type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="page >= pages || images.pending.value" @click="go(page + 1)">下一页</button>
    </nav>
  </dialog>
</template>
