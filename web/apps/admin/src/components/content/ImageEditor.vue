<script setup lang="ts">
import { formatContentTime } from "../../pages/content/types"
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { ApiError, deleteApiImagesId } from "@sjtu-ow/api"
import { imageUrl } from "@sjtu-ow/shared/media"
import { primitiveValues, readSaveReceipt } from "@sjtu-ow/shared/save-receipt"
import { useAdminApi } from "../../core/api"
import { useAdminSave } from "../../core/use-save"
import { useAdminAction } from "../../core/use-action"
import SaveStatus from "../SaveStatus.vue"
import ContentField from "./ContentField.vue"
import ContentActionMessage from "./ContentActionMessage.vue"
import ConfirmContentAction from "./ConfirmContentAction.vue"
import { saveImage, type ImageEditValues } from "../../pages/content/pending"
import { readContentCurrent } from "../../pages/content/save-values"
import { type Collection, type ImageDetail } from "../../pages/content/types"

const props = defineProps<{ image: ImageDetail; collections: Collection[] }>()
const api = useAdminApi()
const router = useRouter()
const confirmation = ref(false)
const notice = ref("")
const canManage = computed(() => props.image.can_change)
const initial: ImageEditValues = { title: props.image.title, collection_id: props.image.collection_id }
const save = useAdminSave<ImageEditValues>({
  initial,
  version: props.image.version,
  available: () => canManage.value,
  readCurrent: (value) => readContentCurrent(value, initial),
  transport: async (body, key, signal) => readSaveReceipt(await saveImage(api, props.image.id, body, {
    key, signal, unauthorized: "throw",
  }), initial, primitiveValues(initial)),
})
const values = save.values
const fields = save.fields
const deletion = useAdminAction(
  (_: null, extras) => deleteApiImagesId(api, props.image.id, extras),
  async () => { await router.push("/admin/images/") },
)
function title(event: Event): void {
  if (event.target instanceof HTMLInputElement) save.set("title", event.target.value)
}
function collection(event: Event): void {
  if (!(event.target instanceof HTMLSelectElement)) return
  const value = event.target.value ? Number(event.target.value) : null
  if (value !== null && (!Number.isSafeInteger(value) || value <= 0)) return
  save.set("collection_id", value, "choice")
}
async function saved(): Promise<void> {
  if (await save.save()) notice.value = "图片已保存。"
}
async function remove(): Promise<void> {
  if (!props.image.can_delete || !await save.flush()) return
  await deletion.submit(null)
}
</script>
<template>
  <div class="b-split">
    <form class="b-form" novalidate @submit.prevent="saved">
      <SaveStatus :snapshot="save.snapshot.value" :dirty="save.dirty.value" :pending="save.pending.value" @retry="save.save" />
      <p v-if="notice" class="c-notice c-notice--ok" role="status">{{ notice }}</p>
      <ContentActionMessage :message="deletion.message.value" :pending="deletion.pending.value" :uncertain="deletion.uncertain.value" @retry="deletion.retry" />
      <fieldset class="b-fieldset" :disabled="!canManage || deletion.pending.value || deletion.uncertain.value">
        <span class="b-grid__pic">
          <img :src="imageUrl(image.id, 'max-800x600')" alt="" loading="lazy">
        </span>
        <ContentField name="title" label="标题" required :errors="fields.title">
          <template #default="field">
            <input :id="field.id" class="c-input" name="title" :value="values.title" maxlength="255" :aria-describedby="field.describedby" @input="title">
          </template>
        </ContentField>
        <ContentField name="collection_id" label="集合" required :errors="fields.collection_id">
          <template #default="field">
            <select :id="field.id" class="c-input" name="collection" :value="values.collection_id ?? ''" :aria-describedby="field.describedby" @change="collection">
              <option v-for="item in collections.filter(item => item.can_upload)" :key="item.id" :value="item.id">{{ item.parent_id === null ? '（根）' : item.name }}</option>
            </select>
          </template>
        </ContentField>
      </fieldset>
      <div class="b-actions" hidden>
        <button hidden class="c-btn c-btn--primary" :disabled="!canManage || deletion.pending.value || deletion.uncertain.value || save.pending.value">保存</button>
      </div>
      <ConfirmContentAction
        v-if="confirmation"
        title="删除这张图片？"
        description="用到它的文章、横幅会变成默认图。删除后不能恢复。"
        :pending="deletion.pending.value"
        danger
        @confirm="remove"
        @cancel="confirmation = false"
      />
    </form>
    <aside class="b-aside">
      <section class="b-section">
        <h2 class="b-section__title">这张图</h2>
        <dl class="b-kv">
          <dt>尺寸</dt><dd>{{ image.width }}×{{ image.height }}</dd>
          <dt>上传</dt><dd>{{ formatContentTime(image.created_at) }}</dd>
<template v-if="image.uploader_nickname"><dt>上传人</dt><dd>{{ image.uploader_nickname }}</dd></template>
          <dt>预览</dt>
          <dd><a class="c-link" :href="imageUrl(image.id, 'max-800x600')" target="_blank" rel="noopener">打开</a></dd>
        </dl>
        <button v-if="image.can_delete" type="submit" class="c-btn c-btn--danger c-btn--sm" :disabled="!deletion.canStart.value" @click.prevent="confirmation = true">删除图片</button>
      </section>
    </aside>
  </div>
</template>
