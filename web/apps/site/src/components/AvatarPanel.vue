<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue"
import { deleteApiMeAvatar, postApiMeAvatar, ApiError } from "@sjtu-ow/api"
import CAvatar from "@sjtu-ow/ui/CAvatar.vue"
import CField from "@sjtu-ow/ui/CField.vue"
import SectionHead from "@sjtu-ow/ui/SectionHead.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { useConfirm } from "@sjtu-ow/shared/confirm"
import type { AvatarPerson } from "@sjtu-ow/ui/types"
import type { PersonalProfile } from "../pending-api"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
import { avatarDataURL } from "../upload"

defineProps<{ profile: PersonalProfile; person: AvatarPerson }>()
const emit = defineEmits<{ changed: [image: number | null] }>()
const api = useApi()
const confirm = useConfirm()
const fileInput = ref<HTMLInputElement | null>(null)
const reading = ref(false)
const fileMessage = ref("")
const notice = ref("")
const enhanced = ref(false)
onMounted(() => { enhanced.value = true })
let reader: AbortController | null = null

const upload = useMutation(
  (body: { file_name: string; data_url: string }, extras) => postApiMeAvatar(api, body, extras),
  (result) => {
    if (!result.image) throw new ApiError(0, "invalid_image_response", "头像上传结果无效，请重新打开页面确认。")
    emit("changed", result.image.id)
    notice.value = "头像已换上。"
    if (fileInput.value) fileInput.value.value = ""
  },
)

const remove = useMutation(
  (_body: Record<string, never>, extras) => deleteApiMeAvatar(api, extras),
  () => {
    emit("changed", null)
    notice.value = "已改用默认头像。"
  },
)

async function choose(): Promise<void> {
  if (reading.value || upload.pending.value || remove.pending.value || upload.uncertain.value) return
  const file = fileInput.value?.files?.[0]
  if (!file) return
  reading.value = true
  fileMessage.value = ""
  notice.value = ""
  reader = new AbortController()
  try {
    const data_url = await avatarDataURL(file, reader.signal)
    await upload.submit({ file_name: file.name, data_url })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return
    fileMessage.value = error instanceof Error ? error.message : "无法读取这张图片。"
  } finally {
    reading.value = false
    reader = null
  }
}

function removeAvatar(): void {
  if (!confirm("改用默认头像？你上传的头像会被删除。")) return
  notice.value = ""
  void remove.submit({})
}

onUnmounted(() => reader?.abort())
</script>

<template>
  <section aria-labelledby="me-avatar" class="max-w-xl">
    <SectionHead title="头像" heading-id="me-avatar" />
    <div class="flex flex-col gap-5">
      <div class="c-faces">
        <figure>
          <CAvatar :person="person" size="lg" />
          <figcaption>{{ profile.avatar_image_id ? '现在的头像' : '现在是默认头像' }}</figcaption>
        </figure>
      </div>
      <p v-if="profile.avatar_turned_down" class="text-sm text-fg-2" role="status">
        上次上传的头像{{ profile.avatar_turned_down.status === 'taken_down' ? '被管理员撤下了' : '没有通过审核' }}，原因：{{ profile.avatar_turned_down.reason_display }}<template v-if="profile.avatar_turned_down.note">（{{ profile.avatar_turned_down.note }}）</template>。可以换一张再传。
      </p>
      <form
        v-if="profile.avatar_can_upload !== false"
        method="post"
        action="/me/avatar/upload/"
        enctype="multipart/form-data"
        class="c-form"
        data-autosubmit-file
        :aria-busy="reading || upload.pending.value || undefined"
        @submit.prevent="choose"
      >
        <CField label="上传新头像" input-id="id_avatar_file" :errors="fileMessage ? [fileMessage] : upload.fields.value.file">
          <input
            id="id_avatar_file"
            ref="fileInput"
            type="file"
            name="file"
            accept="image/jpeg,image/png,image/webp"
            aria-describedby="id_avatar_file_helptext"
            :disabled="reading || upload.pending.value || upload.uncertain.value || remove.pending.value"
            @change="choose"
          >
          <template #help>
            <span id="id_avatar_file_helptext">JPG、PNG 或 WebP，不超过 5MB，至少 128×128 像素。会从中间裁成正方形，想要别的范围请先自己裁好。选好图片就上传，马上换上。</span>
          </template>
        </CField>
        <div class="c-formbar" :hidden="enhanced">
          <button type="submit" class="c-btn c-btn--primary" data-autosave-button :hidden="enhanced" :disabled="reading || !upload.canStart.value">上传</button>
        </div>
        <p v-if="reading || upload.pending.value" class="c-autosave" data-autosubmit-status role="status">正在上传，传好就换上…</p>
        <CMutationError
          :message="upload.message.value"
          :uncertain="upload.uncertain.value"
          :pending="upload.pending.value"
          @retry="upload.retry"
        />
      </form>
      <p v-else class="text-sm text-fg-2">{{ profile.avatar_denied || '你暂时无法使用此功能，如有疑问请联系管理员。' }}</p>
      <div v-if="profile.avatar_image_id" class="flex flex-wrap gap-3">
        <form method="post" action="/me/avatar/remove/" @submit.prevent="removeAvatar">
          <button
            type="submit"
            class="c-btn c-btn--secondary"
            :disabled="reading || upload.pending.value || remove.pending.value || remove.uncertain.value"
          >改用默认头像</button>
        </form>
      </div>
      <CMutationError
        :message="remove.message.value"
        :uncertain="remove.uncertain.value"
        :pending="remove.pending.value"
        @retry="remove.retry"
      />
      <p v-if="notice" class="text-sm text-fg-2" role="status">{{ notice }}</p>
    </div>
  </section>
</template>
