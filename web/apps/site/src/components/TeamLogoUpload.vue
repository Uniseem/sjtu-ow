<script setup lang="ts">
import { onUnmounted, ref } from "vue"
import { postApiTeamsIdLogo, ApiError } from "@sjtu-ow/api"
import {prepareTeamLogo} from "../team-editor"
import CField from "@sjtu-ow/ui/CField.vue"
import CMutationError from "@sjtu-ow/ui/CMutationError.vue"
import { imageUrl } from "@sjtu-ow/shared/media"
import { avatarDataURL } from "../upload"
import { useApi } from "../api"
import { useMutation } from "../use-mutation"
const props = defineProps<{ teamId?: number; imageId: number | null; beforeUpload?: () => Promise<boolean>; disabled?: boolean }>()
const emit = defineEmits<{ changed: [id: number]; busy: [busy: boolean] }>()
const api = useApi()
const input = ref<HTMLInputElement | null>(null)
const reading = ref(false)
const error = ref("")
let reader: AbortController | null = null
const upload = useMutation((body: { file_name: string; data_url: string }, extras) => props.teamId
  ? postApiTeamsIdLogo(api, props.teamId, body, extras)
  : prepareTeamLogo(api,body,extras), result => {
    if (!result.image) throw new ApiError(0, "invalid_receipt", "队标上传结果无效，请重新打开页面确认。")
    emit("changed", result.image.id)
    if (input.value) input.value.value = ""
  })
async function choose(): Promise<void> {
  if (props.disabled || reading.value || !upload.canStart.value) return
  const file = input.value?.files?.[0]
  if (!file) return
  error.value = ""
  reading.value = true
  emit("busy", true)
  reader = new AbortController()
  try {
    if (props.beforeUpload && !await props.beforeUpload()) { error.value = "请先解决资料保存的问题，再上传队标。"; return }
    const data_url = await avatarDataURL(file, reader.signal)
    await upload.submit({ file_name: file.name, data_url })
  } catch (failure) {
    if (failure instanceof DOMException && failure.name === "AbortError") return
    error.value = failure instanceof Error ? failure.message : "图片读取失败。"
  } finally { reading.value = false; reader = null; emit("busy", false) }
}
onUnmounted(() => reader?.abort())
</script>
<template>
  <img v-if="imageId && !teamId" :src="imageUrl(imageId, 'fill-176x176')" class="c-teams__logo" alt="所选队标">
  <CField label="队标" input-id="id_logo_file" :errors="error ? [error] : upload.fields.value.file">
    <input id="id_logo_file" ref="input" type="file" name="logo_file" accept="image/jpeg,image/png,image/webp" :disabled="disabled || reading || !upload.canStart.value" aria-describedby="id_logo_file_helptext" @change="choose">
    <template #help><span id="id_logo_file_helptext">JPG、PNG 或 WebP，不超过 5MB，显示时裁剪为正方形。</span></template>
  </CField>
  <p v-if="reading || upload.pending.value" class="c-autosave" role="status">正在上传，传好就换上…</p>
  <CMutationError :message="upload.message.value" :uncertain="upload.uncertain.value" :pending="upload.pending.value" @retry="upload.retry" />
</template>
