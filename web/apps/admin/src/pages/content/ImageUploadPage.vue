<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { onBeforeRouteLeave } from "vue-router"
import { getApiAdminImageCollections } from "@sjtu-ow/api"
import { useAdminApi } from "../../core/api"
import { useAdminSession } from "../../core/session"
import AdminPage from "../../components/AdminPage.vue"
import ContentLoad from "../../components/content/ContentLoad.vue"
import UploadRows from "../../components/content/UploadRows.vue"
import { useContentResource } from "./use-resource"
import { useUploadQueue } from "./use-upload-queue"
import { collectionChoiceLabel } from "./collection-tree"

const api = useAdminApi()
const { user } = useAdminSession()
const collection = ref("")
const chosen = ref<File[]>([])
const input = ref<HTMLInputElement | null>(null)
const canUpload = computed(() => Boolean(user.value?.superuser || user.value?.caps.includes("images.contribute")))
const collections = useContentResource((signal) => getApiAdminImageCollections(api, { signal }))
const queue = useUploadQueue(api)
const waiting = computed(() => queue.items.value.filter((item) => item.state === "queued").length)

function files(event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) return
  chosen.value = [...(event.target.files ?? [])]
}
function enqueue(): void {
  if (!canUpload.value || !collection.value || !chosen.value.length) return
  queue.add(chosen.value, collection.value)
  chosen.value = []
  if (input.value) input.value.value = ""
}
async function upload(): Promise<void> {
  if (chosen.value.length) enqueue()
  await queue.start()
}
onBeforeRouteLeave(() => {
  if (!queue.pending.value && !queue.uncertain.value) return true
  queue.message.value = "上传尚未确认，请先完成或重试当前上传。"
  return false
})
onMounted(async () => {
  const result = await collections.load()
  collection.value = result?.collections.find(item => item.can_upload)?.key ?? ""
})
</script>
<template>
  <AdminPage title="上传图片" section="content" back-href="/admin/images/">
    <ContentLoad :pending="collections.pending.value" :message="collections.message.value" :status="collections.status.value" @retry="collections.load" />
    <form class="b-form" @submit.prevent="upload">
      <fieldset class="b-fieldset" :disabled="!canUpload || queue.pending.value || queue.uncertain.value">
        <div class="c-field">
          <label class="c-field__label" for="upload_collection">放进集合<span class="c-field__req" aria-hidden="true">*</span></label>
          <select id="upload_collection" v-model="collection" class="c-input" name="collection" required>
            <option v-for="item in (collections.data.value?.collections ?? []).filter(item => item.can_upload)" :key="item.id" :value="item.key">{{ collectionChoiceLabel(item, collections.data.value?.collections ?? []) }}</option>
          </select>
        </div>
        <div class="c-field">
          <label class="c-field__label" for="files">图片<span class="c-field__req" aria-hidden="true">*</span></label>
          <input id="files" ref="input" type="file" name="files" :required="!waiting" accept=".jpg,.jpeg,.png,.webp" multiple aria-describedby="files-help" @change="files">
          <div id="files-help" class="c-field__help">可以一次选多张。JPG、PNG、WebP，每张不超过 5 MB；JPG 和 PNG 会转成 WebP。标题先用文件名，传完可以改。</div>
        </div>
        <button v-if="chosen.length" type="button" class="c-btn c-btn--secondary c-btn--sm" @click="enqueue">加入上传列表（{{ chosen.length }} 张）</button>
      </fieldset>
      <UploadRows :items="queue.items.value" :pending="queue.pending.value" @rename="queue.rename" @remove="queue.remove" />
      <p v-if="queue.message.value" class="c-notice c-notice--error" role="alert">{{ queue.message.value }}</p>
      <p v-if="queue.items.value.length" class="b-count" role="status">已上传 {{ queue.complete.value }} / {{ queue.items.value.length }} 张</p>
      <div class="b-actions">
        <button class="c-btn c-btn--primary" :disabled="!canUpload || queue.pending.value || queue.uncertain.value">{{ queue.pending.value ? '正在上传…' : '上传' }}</button>
        <button v-if="queue.uncertain.value" type="button" class="c-btn c-btn--secondary" :disabled="queue.pending.value" @click="queue.retry">重试上次上传</button>
        <RouterLink v-if="!queue.pending.value && !queue.uncertain.value" class="c-btn c-btn--secondary" to="/admin/images/">{{ queue.complete.value ? '返回图片' : '不传了' }}</RouterLink>
      </div>
    </form>
  </AdminPage>
</template>
